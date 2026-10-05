"""
Local key storage: this device's identity, and pinned public keys of everyone we've seen.

Pinning (trust on first use): the first public key we see for a username is remembered.
If the server later presents a different key for that name, `check` returns "changed"
and the session refuses to use it until the user compares safety numbers and accepts.
That is what stops a malicious server from silently swapping in its own key.

Files live in $E2EE_CHAT_HOME (default ~/.e2ee_chat):
  <user>.identity    private keys, encrypted with the user's password
  <user>.pins.json   username -> pinned public bundle
"""
import json
import os
from pathlib import Path

from .crypto import Identity, fingerprint, verify_bundle


def home() -> Path:
    path = Path(os.environ.get("E2EE_CHAT_HOME", Path.home() / ".e2ee_chat"))
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def identity_path(user: str) -> Path:
    return home() / f"{user}.identity"


def create_identity(user: str, password: str) -> Identity:
    path = identity_path(user)
    if path.exists():
        raise FileExistsError(f"an identity for {user!r} already exists on this device")
    ident = Identity.generate()
    path.write_text(ident.to_encrypted_json(password))
    path.chmod(0o600)
    return ident


def load_identity(user: str, password: str) -> Identity:
    path = identity_path(user)
    if not path.exists():
        raise FileNotFoundError(f"no identity for {user!r} on this device (keys never leave the device they were made on)")
    return Identity.from_encrypted_json(path.read_text(), password)


class Pins:
    def __init__(self, me: str):
        self.path = home() / f"{me}.pins.json"
        self.pins: dict[str, dict] = json.loads(self.path.read_text()) if self.path.exists() else {}

    def check(self, user: str, bundle: dict) -> str:
        """'new' (now pinned), 'match', 'changed', or 'invalid'."""
        if not verify_bundle(bundle):
            return "invalid"
        pinned = self.pins.get(user)
        if pinned is None:
            self.accept(user, bundle)
            return "new"
        return "match" if fingerprint(pinned) == fingerprint(bundle) else "changed"

    def accept(self, user: str, bundle: dict):
        self.pins[user] = bundle
        self.path.write_text(json.dumps(self.pins, indent=1))
        self.path.chmod(0o600)

    def get(self, user: str) -> dict | None:
        return self.pins.get(user)
