"""FIDO2 Enrolment BFF — FastAPI application."""
import base64
import hashlib
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from cose import extract_ed25519_pubkey
from enrolment import DuplicateCredentialError, EnrolmentStore


_THRESHOLD = int(os.environ.get("THRESHOLD", "2"))
_RP_ID = os.environ.get("RP_ID", "localhost")
_RP_NAME = os.environ.get("RP_NAME", "DecPKI Prototype")
_ORIGIN = os.environ.get("ORIGIN", f"http://{_RP_ID}")

_store: EnrolmentStore | None = None
_challenges: dict[str, dict] = {}
_nonces: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store
    _store = EnrolmentStore(threshold=_THRESHOLD)
    yield


app = FastAPI(title="DecPKI FIDO2 Enrolment BFF", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    s = s.replace("-", "+").replace("_", "/")
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.b64decode(s)


@app.get("/")
def root():
    return {"service": "decpki-enrolment-bff", "version": "0.1.0"}


@app.post("/enrolment/start")
def start_registration(did: str | None = Query(default=None)):
    """Begin a WebAuthn registration ceremony."""
    raw_challenge = secrets.token_bytes(32)
    challenge_b64 = _b64url(raw_challenge)

    if did is not None:
        req = _store.get(did) if _store else None
        promoted = None
        if _store:
            for r in _store.list_pending():
                if r.did == did and r.status == "promoted":
                    promoted = r
        if promoted is None:
            existing_dir = Path(os.environ.get("ENROLMENT_DIR", "/tmp/decpki-enrolments")) / "promoted"
            for p in existing_dir.glob("*.json"):
                try:
                    data = json.loads(p.read_text())
                    if data.get("did") == did:
                        promoted = data
                        break
                except Exception:
                    pass
        if promoted is None:
            raise HTTPException(status_code=404, detail=f"DID not found: {did}")

        nonce = _b64url(secrets.token_bytes(32))
        _nonces[did] = {"nonce": nonce, "expires_at": int(time.time()) + 60}
        pending_did = did

        _challenges[pending_did] = {
            "raw": raw_challenge,
            "b64": challenge_b64,
            "pending_did": pending_did,
            "request_type": "add_credential",
        }
        return {
            "challenge": challenge_b64,
            "rp": {"name": _RP_NAME, "id": _RP_ID},
            "user": {
                "id": _b64url(pending_did.encode()),
                "name": "user",
                "displayName": "User",
            },
            "pubKeyCredParams": [{"type": "public-key", "alg": -8}],
            "timeout": 60000,
            "attestation": "none",
            "request_type": "add_credential",
            "pending_did": pending_did,
            "ownership_nonce": nonce,
        }

    pending_did = f"did:local:{uuid.uuid4()}"
    _challenges[pending_did] = {
        "raw": raw_challenge,
        "b64": challenge_b64,
        "pending_did": pending_did,
        "request_type": "new",
    }

    return {
        "challenge": challenge_b64,
        "rp": {"name": _RP_NAME, "id": _RP_ID},
        "user": {
            "id": _b64url(pending_did.encode()),
            "name": "user",
            "displayName": "User",
        },
        "pubKeyCredParams": [{"type": "public-key", "alg": -8}],
        "timeout": 60000,
        "attestation": "none",
        "request_type": "new",
        "pending_did": pending_did,
    }


class SubmitRequest(BaseModel):
    pending_did: str
    credential: dict[str, Any]
    ownership_assertion: dict[str, Any] | None = None


@app.post("/enrolment/submit", status_code=201)
def submit_registration(body: SubmitRequest):
    """Submit a WebAuthn credential for enrolment."""
    pending_did = body.pending_did
    stored = _challenges.pop(pending_did, None)
    if stored is None:
        raise HTTPException(status_code=422, detail="Unknown or expired challenge for this DID.")

    client_data_json_b64 = (
        body.credential.get("response", {}).get("clientDataJSON", "")
    )
    try:
        client_data = json.loads(_b64url_decode(client_data_json_b64))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid clientDataJSON: {e}")

    if client_data.get("type") != "webauthn.create":
        raise HTTPException(status_code=422, detail="clientDataJSON type must be 'webauthn.create'")

    recv_challenge = client_data.get("challenge", "")
    if recv_challenge != stored["b64"]:
        raise HTTPException(status_code=422, detail="Challenge mismatch.")

    attestation_object_b64 = body.credential.get("response", {}).get("attestationObject", "")
    try:
        att_bytes = _b64url_decode(attestation_object_b64)
        pubkey_bytes = extract_ed25519_pubkey(att_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    public_key_hex = pubkey_bytes.hex()

    credential_id = body.credential.get("id", "")
    if not credential_id:
        raise HTTPException(status_code=422, detail="Missing credential id.")

    if stored["request_type"] == "add_credential":
        if body.ownership_assertion is None:
            raise HTTPException(status_code=422, detail="Ownership proof required for add_credential flow.")
        nonce_entry = _nonces.get(pending_did)
        if nonce_entry is None or int(time.time()) > nonce_entry["expires_at"]:
            raise HTTPException(status_code=422, detail="Ownership nonce expired or not found.")
        _nonces.pop(pending_did, None)

    try:
        req = _store.create(
            did=pending_did,
            public_key_hex=public_key_hex,
            credential_id=credential_id,
            public_key_cose_b64=attestation_object_b64[:100],
            request_type=stored["request_type"],
            existing_did=pending_did if stored["request_type"] == "add_credential" else None,
            metadata={"user_agent": ""},
        )
    except DuplicateCredentialError as e:
        raise HTTPException(status_code=409, detail="Credential ID already registered.")

    return {
        "request_id": req.id,
        "did": req.did,
        "status": req.status,
        "signatures_collected": len(req.signatures),
        "threshold": req.threshold,
        "expires_at": req.expires_at,
    }


@app.get("/enrolment/")
def list_requests():
    """List all pending enrolment requests."""
    requests = _store.list_pending()
    return [
        {
            "request_id": r.id,
            "did": r.did,
            "status": r.status,
            "signatures_collected": len(r.signatures),
            "threshold": r.threshold,
            "submitted_at": r.submitted_at,
            "expires_at": r.expires_at,
        }
        for r in requests
    ]


@app.get("/enrolment/{request_id}")
def get_request(request_id: str):
    """Get status of an enrolment request."""
    req = _store.get(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail=f"Request not found: {request_id}")
    return {
        "request_id": req.id,
        "did": req.did,
        "status": req.status,
        "signatures_collected": len(req.signatures),
        "threshold": req.threshold,
        "expires_at": req.expires_at,
    }
