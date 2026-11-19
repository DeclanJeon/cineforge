"""Sign a local proposal, never an execution grant. Run as python -m cineforge.host_sign REQUEST BODY."""
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

from .receipts import atomic_text


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def sign(request, body, key: bytes):
    if len(key) < 32:
        raise ValueError("host key must contain at least 32 bytes")
    digest = hashlib.sha256(canonical(request)).hexdigest()
    signature = hmac.digest(key, canonical(["cineforge-pi-v1", digest, body]), "sha256").hex()
    return {"request_digest": digest, "body": body, "signature": signature}


if __name__ == "__main__":
    req = Path(sys.argv[1]).resolve()
    request = json.loads(req.read_text())
    body = json.loads(Path(sys.argv[2]).read_text())
    response = req.parent.parent / "responses" / req.name
    atomic_text(response, json.dumps(sign(request, body, Path(os.environ["CINEFORGE_HOST_KEY_FILE"]).read_bytes()), ensure_ascii=False))
