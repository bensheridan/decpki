"""CLI commands: enrol-sign, enrol-promote, enrol-revoke."""
import hashlib
import json
import shutil
import time
from pathlib import Path

import cbor2
import click

from decpki.models import IdentityLog, IdentityRecord, ValidatorNode


def _signing_payload(request_id: str, did: str, public_key_hex: str) -> bytes:
    payload = {"did": did, "id": request_id, "pubkey": public_key_hex}
    return hashlib.sha256(cbor2.dumps(payload, canonical=True)).digest()


def _enrolment_dir() -> Path:
    import os
    return Path(os.environ.get("ENROLMENT_DIR", "/tmp/decpki-enrolments"))


@click.command("enrol-sign")
@click.option("--request", "request_path", required=True, help="Path to enrolment request JSON")
@click.option("--validator", "validator_path", required=True, help="Validator key file path")
def enrol_sign(request_path, validator_path):
    """Co-sign a pending enrolment request as a validator."""
    path = Path(request_path)
    if not path.exists():
        click.echo(f"Error: request file not found: {request_path}", err=True)
        raise SystemExit(1)

    req = json.loads(path.read_text())

    if req["status"] != "pending":
        click.echo(f"Error: request {req['id']} is not pending (status: {req['status']})", err=True)
        raise SystemExit(1)

    if int(time.time()) > req["expires_at"]:
        click.echo(f"Error: Request {req['id']} has expired and cannot be signed.", err=True)
        raise SystemExit(1)

    validator = ValidatorNode.from_key_file(validator_path)
    existing = [s["validator_name"] for s in req["signatures"]]
    if validator.did in existing:
        click.echo(f"Validator {validator.did} has already signed this request.", err=True)
        raise SystemExit(1)

    payload = _signing_payload(req["id"], req["did"], req["public_key_hex"])
    sig = validator.sign(payload)

    req["signatures"].append({
        "validator_name": validator.did,
        "signature_hex": sig.hex(),
        "signed_at": int(time.time()),
    })
    path.write_text(json.dumps(req, indent=2))

    count = len(req["signatures"])
    threshold = req.get("threshold", 2)
    click.echo(f"Signatures: {count}/{threshold} — {'quorum reached. Ready to promote.' if count >= threshold else 'waiting for more signatures.'}")


@click.command("enrol-promote")
@click.option("--request", "request_path", required=True, help="Path to enrolment request JSON")
@click.option("--threshold", default=2, type=int, help="Minimum signatures required")
@click.option("--log", "log_path", default="identity_log.json", help="Identity log path")
@click.option("--validator", "validator_paths", multiple=True, help="Validator key file (repeat to provide multiple; overrides automatic lookup)")
def enrol_promote(request_path, threshold, log_path, validator_paths):
    """Promote a fully co-signed enrolment request to the identity ledger."""
    path = Path(request_path)
    if not path.exists():
        click.echo(f"Error: request file not found: {request_path}", err=True)
        raise SystemExit(1)

    req = json.loads(path.read_text())

    if req["status"] != "pending":
        click.echo(f"Error: request {req['id']} is not pending (status: {req['status']})", err=True)
        raise SystemExit(1)

    if int(time.time()) > req["expires_at"]:
        click.echo(f"Error: Request {req['id']} has expired.", err=True)
        raise SystemExit(1)

    # Build explicit key map if --validator flags provided; otherwise fall back to auto-lookup
    explicit_keys: dict[str, Path] = {}
    for vp in validator_paths:
        vp = Path(vp)
        if not vp.exists():
            click.echo(f"Error: validator key not found: {vp}", err=True)
            raise SystemExit(1)
        node = ValidatorNode.from_key_file(vp)
        explicit_keys[node.did] = vp

    valid_sigs = []
    payload = _signing_payload(req["id"], req["did"], req["public_key_hex"])
    for sig_entry in req["signatures"]:
        try:
            validator_did = sig_entry["validator_name"]
            if explicit_keys:
                pubkey_path = explicit_keys.get(validator_did)
                if pubkey_path is None:
                    click.echo(f"Warning: no --validator key provided for {validator_did}, skipping", err=True)
                    continue
            else:
                pubkey_path = _find_validator_key(validator_did)
                if pubkey_path is None:
                    click.echo(f"Warning: cannot find key for {validator_did}, skipping", err=True)
                    continue
            node = ValidatorNode.from_key_file(pubkey_path)
            if node.verify(bytes.fromhex(sig_entry["signature_hex"]), payload):
                valid_sigs.append(validator_did)
            else:
                click.echo(f"Warning: signature invalid for {validator_did}", err=True)
        except Exception as e:
            click.echo(f"Warning: signature verification failed for {sig_entry['validator_name']}: {e}", err=True)

    if len(valid_sigs) < threshold:
        click.echo(f"Error: only {len(valid_sigs)} of {threshold} signatures are valid.", err=True)
        raise SystemExit(3)

    log = IdentityLog.load(log_path) if Path(log_path).exists() else IdentityLog.empty()
    record = IdentityRecord(
        did=req["did"],
        public_key=bytes.fromhex(req["public_key_hex"]),
        issued_at=log.next_block,
        issued_by=valid_sigs,
        metadata={"credential_id": req.get("credential_id", ""), "enrolment_id": req["id"]},
    )
    try:
        log.add(record)
    except Exception:
        pass
    log.save(log_path)

    req["status"] = "promoted"
    path.write_text(json.dumps(req, indent=2))
    promoted_dir = _enrolment_dir() / "promoted"
    promoted_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(promoted_dir / path.name))

    click.echo(f"Promoted: {req['did']}")
    click.echo(f"  Block:       {record.issued_at}")
    click.echo(f"  Signed by:   {', '.join(valid_sigs)}")
    click.echo(f"  Log updated: {log_path}")


def _find_validator_key(validator_did: str) -> Path | None:
    name = validator_did.replace("did:local:validator-", "")
    candidates = [
        Path(f"{name}.key.json"),
        Path(f"/tmp/{name}.key.json"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


@click.command("enrol-revoke")
@click.option("--did", required=True, help="DID whose credential to revoke")
@click.option("--log", "log_path", default="identity_log.json", help="Identity log path")
@click.option("--validator", "validator_paths", multiple=True, required=True, help="Validator key file (repeat for each)")
@click.option("--threshold", default=2, type=int, help="Minimum validator signatures required")
def enrol_revoke(did, log_path, validator_paths, threshold):
    """Revoke an identity credential by writing a revocation record to the ledger."""
    if len(validator_paths) < threshold:
        click.echo(f"Error: need at least {threshold} validator(s), got {len(validator_paths)}", err=True)
        raise SystemExit(3)

    log = IdentityLog.load(log_path) if Path(log_path).exists() else IdentityLog.empty()
    record = log.get(did)
    if record is None:
        click.echo(f"Error: DID not found in ledger: {did}", err=True)
        raise SystemExit(4)

    if record.revoked_at is not None:
        click.echo(f"DID {did} is already revoked (block {record.revoked_at}).")
        raise SystemExit(0)

    record.revoked_at = log.next_block
    log.save(log_path)
    click.echo(f"Revoked: {did}")
    click.echo(f"  Revocation block: {record.revoked_at}")
    click.echo(f"  Log updated:      {log_path}")
    click.echo("Run 'decpki bundle ...' to publish the revocation in a new trust bundle.")
