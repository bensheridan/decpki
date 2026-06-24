import datetime
import os
import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decpki import (
    generate_bundle,
    register_identity,
    verify,
    IdentityLog,
    IdentityRecord,
    ValidatorNode,
    Outcome,
    QuorumError,
    DuplicateDIDError,
    BundleDecodeError,
)
from decpki.bundle import deserialise_bundle


def _parse_grace(value: str) -> int:
    value = value.strip()
    if value.endswith("d"):
        return int(value[:-1]) * 86400
    if value.endswith("h"):
        return int(value[:-1]) * 3600
    if value.endswith("s"):
        return int(value[:-1])
    raise click.BadParameter(f"Unknown format '{value}'. Use 24h, 7d, or 3600s.")


@click.group()
@click.option("--log", default="identity_log.json", help="Path to identity log file")
@click.option("--verbose", is_flag=True, default=False)
@click.pass_context
def cli(ctx, log, verbose):
    ctx.ensure_object(dict)
    ctx.obj["log_path"] = log
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option("--name", required=True, help="Short validator name (e.g. alpha)")
@click.option("--out", default=None, help="Output key file path")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing key file")
def keygen(name, out, force):
    """Generate a validator keypair."""
    out = out or f"{name}.key.json"
    path = Path(out)
    if path.exists() and not force:
        click.echo(f"Error: key file '{out}' already exists. Use --force to overwrite.", err=True)
        sys.exit(1)
    did = f"did:local:validator-{name}"
    node = ValidatorNode.generate(did)
    node.save_key_file(path)
    click.echo(f"Validator DID:  {did}")
    click.echo(f"Public key:     {node.public_key.hex()}")
    click.echo(f"Key file:       {out}")


@cli.command()
@click.option("--did", required=True, help="DID of the identity to register")
@click.option("--pubkey", required=True, help="ed25519 public key hex (64 chars)")
@click.option("--validator", "validator_paths", multiple=True, required=True,
              help="Validator key file path (repeat for each)")
@click.option("--meta", "meta_pairs", multiple=True, help="Metadata key=value (repeatable)")
@click.option("--valid-until-block", default=None, type=int)
@click.pass_context
def register(ctx, did, pubkey, validator_paths, meta_pairs, valid_until_block):
    """Register an identity in the quorum."""
    log_path = ctx.obj["log_path"]
    log = IdentityLog.load(log_path) if Path(log_path).exists() else IdentityLog.empty()

    validators = [ValidatorNode.from_key_file(p) for p in validator_paths]
    threshold = 2

    metadata = {}
    for pair in meta_pairs:
        k, _, v = pair.partition("=")
        metadata[k] = v

    record = IdentityRecord(
        did=did,
        public_key=bytes.fromhex(pubkey),
        issued_at=0,
        issued_by=[],
        valid_until=valid_until_block,
        metadata=metadata,
    )

    try:
        completed = register_identity(log, record, validators, threshold)
    except DuplicateDIDError:
        click.echo(f"Error: DID already registered: {did}", err=True)
        sys.exit(2)
    except QuorumError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(3)

    log.save(log_path)
    click.echo(f"Registered: {did}")
    click.echo(f"  Block:       {completed.issued_at}")
    click.echo(f"  Signed by:   {', '.join(completed.issued_by)}")
    click.echo(f"  Log updated: {log_path}")


@cli.command()
@click.option("--validator", "validator_paths", multiple=True, required=True,
              help="Validator key file path (repeat for each)")
@click.option("--threshold", default=2, type=int, help="Minimum signatures required")
@click.option("--grace", default="24h", help="Bundle validity window (e.g. 24h, 7d, 3600s)")
@click.option("--out", default="bundle.cbor", help="Output bundle file path")
@click.pass_context
def bundle(ctx, validator_paths, threshold, grace, out):
    """Generate a signed trust bundle."""
    log_path = ctx.obj["log_path"]
    log = IdentityLog.load(log_path) if Path(log_path).exists() else IdentityLog.empty()
    validators = [ValidatorNode.from_key_file(p) for p in validator_paths]

    try:
        grace_secs = _parse_grace(grace)
    except click.BadParameter as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    try:
        raw = generate_bundle(log, validators, threshold, grace_secs)
    except QuorumError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(3)

    Path(out).write_bytes(raw)
    b = deserialise_bundle(raw)
    expires = datetime.datetime.fromtimestamp(b.expires_at, tz=datetime.timezone.utc)
    sigs_str = ", ".join(f"{s.validator_did} (✓)" for s in b.signatures)
    click.echo("Bundle generated:")
    click.echo(f"  Snapshot block:  {b.snapshot_block}")
    click.echo(f"  Merkle root:     {b.snapshot_root.hex()}")
    click.echo(f"  Identities:      {len(b.identities)}")
    click.echo(f"  Expires:         {expires.isoformat()}")
    click.echo(f"  Signed by:       {sigs_str}")
    click.echo(f"  Written to:      {out}  ({len(raw) / 1024:.1f} KB)")


_OUTCOME_EXIT_CODES = {
    Outcome.VALID: 0,
    Outcome.NOT_FOUND: 4,
    Outcome.EXPIRED: 5,
    Outcome.TAMPERED: 6,
    Outcome.INVALID: 7,
    Outcome.QUORUM_FAILURE: 8,
}


@cli.command()
@click.option("--bundle", "bundle_path", required=True, help="Path to .cbor bundle file")
@click.option("--did", required=True, help="DID to verify")
def verify_cmd(bundle_path, did):
    """Verify a DID against a trust bundle. Zero network calls."""
    try:
        result = verify(bundle_path, did)
    except BundleDecodeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(9)
    click.echo(result.message)
    sys.exit(_OUTCOME_EXIT_CODES[result.outcome])


# Register the verify command under the name "verify"
cli.add_command(verify_cmd, name="verify")


@cli.command()
@click.option("--bundle", "bundle_path", required=True, help="Path to .cbor bundle file")
def inspect(bundle_path):
    """Print human-readable bundle summary."""
    try:
        raw = Path(bundle_path).read_bytes()
        b = deserialise_bundle(raw)
    except BundleDecodeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(9)
    except FileNotFoundError:
        click.echo(f"Error: file not found: {bundle_path}", err=True)
        sys.exit(9)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    issued = datetime.datetime.fromtimestamp(b.issued_at, tz=datetime.timezone.utc)
    expires = datetime.datetime.fromtimestamp(b.expires_at, tz=datetime.timezone.utc)
    remaining = expires - now
    remaining_str = (
        f"{int(remaining.total_seconds() // 3600)}h {int((remaining.total_seconds() % 3600) // 60)}m remaining"
        if remaining.total_seconds() > 0
        else "EXPIRED"
    )
    quorum_str = "✓ quorum met" if len(b.signatures) >= b.threshold else "✗ quorum NOT met"

    click.echo(f"Bundle: {bundle_path}")
    click.echo(f"  Format version: {b.format_version}")
    click.echo(f"  Snapshot block: {b.snapshot_block}")
    click.echo(f"  Merkle root:    {b.snapshot_root.hex()}")
    click.echo(f"  Issued:         {issued.isoformat()}")
    click.echo(f"  Expires:        {expires.isoformat()}  ({remaining_str})")
    click.echo(f"  Threshold:      {b.threshold}")
    click.echo(f"  Validator set:  {', '.join(b.validator_set)}")
    click.echo(f"  Signatures:     {len(b.signatures)} ({quorum_str})")
    click.echo(f"  Identities:     {len(b.identities)}")
    for i, entry in enumerate(b.identities, 1):
        r = entry.record
        click.echo(f"\n  Identity {i}: {r.did}")
        click.echo(f"    Public key:   {r.public_key.hex()}")
        click.echo(f"    Issued block: {r.issued_at}")
        click.echo(f"    Issued by:    {', '.join(r.issued_by)}")
        click.echo(f"    Expires:      {'block ' + str(r.valid_until) if r.valid_until else '(indefinite)'}")
        click.echo(f"    Revoked:      {'yes (block ' + str(r.revoked_at) + ')' if r.revoked_at else 'no'}")
        if r.metadata:
            meta_str = ", ".join(f"{k}={v}" for k, v in r.metadata.items())
            click.echo(f"    Metadata:     {meta_str}")


if __name__ == "__main__":
    cli()
