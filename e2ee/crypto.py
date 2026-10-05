"""
End-to-end encryption for group messages.

Identity (per user, generated and kept on the user's device):
  X25519 key pair    key agreement
  Ed25519 key pair   signatures
The public bundle {x, ed, bind} is published through the server; `bind` is the Ed25519
signature over the X25519 public key, so the two keys can't be mixed and matched.

Sending a message (seal):
  1. random 256-bit message key K; AES-256-GCM encrypts the text under K, with the header
     (version, sender, room, message id, timestamp, recipient list) as associated data
  2. a fresh ephemeral X25519 key E; for each recipient R:
       wrap key = HKDF-SHA256(X25519(E, R.x), salt = E.pub || R.x, info = "e2ee-chat wrap v1" || id)
       AES-256-GCM(wrap key) encrypts K, with R's name and the message id as associated data
  3. Ed25519 signature by the sender over the whole envelope

Receiving (open): verify the signature with the sender's pinned Ed25519 key, unwrap K
with our X25519 key, decrypt. Any modification makes one of these steps fail.

The server only ever sees public keys and envelopes.
"""
import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

VERSION = 1
WRAP_INFO = b"e2ee-chat wrap v1"
RAW = dict(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)


class CryptoError(Exception):
    """A message failed verification or decryption. Never display its contents."""


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _raw_private(key) -> bytes:
    return key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                             serialization.NoEncryption())


@dataclass
class Identity:
    x: X25519PrivateKey
    ed: Ed25519PrivateKey

    @classmethod
    def generate(cls) -> "Identity":
        return cls(X25519PrivateKey.generate(), Ed25519PrivateKey.generate())

    def public_bundle(self) -> dict:
        x_pub = self.x.public_key().public_bytes(**RAW)
        ed_pub = self.ed.public_key().public_bytes(**RAW)
        return {"x": b64(x_pub), "ed": b64(ed_pub), "bind": b64(self.ed.sign(b"x25519:" + x_pub))}

    # --- storage: private keys encrypted under a key derived from the user's password ---
    def to_encrypted_json(self, password: str) -> str:
        salt, nonce = os.urandom(16), os.urandom(12)
        key = Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(password.encode("utf-8"))
        secret = _raw_private(self.x) + _raw_private(self.ed)
        return json.dumps({"v": VERSION, "kdf": "scrypt-n32768-r8-p1", "salt": b64(salt), "nonce": b64(nonce),
                           "ct": b64(AESGCM(key).encrypt(nonce, secret, b"e2ee-chat identity"))})

    @classmethod
    def from_encrypted_json(cls, text: str, password: str) -> "Identity":
        d = json.loads(text)
        key = Scrypt(salt=unb64(d["salt"]), length=32, n=2 ** 15, r=8, p=1).derive(password.encode("utf-8"))
        try:
            secret = AESGCM(key).decrypt(unb64(d["nonce"]), unb64(d["ct"]), b"e2ee-chat identity")
        except InvalidTag:
            raise CryptoError("wrong password for this identity file") from None
        return cls(X25519PrivateKey.from_private_bytes(secret[:32]), Ed25519PrivateKey.from_private_bytes(secret[32:]))


def verify_bundle(bundle: dict) -> bool:
    """True if the bundle is well-formed and its X25519 key is signed by its Ed25519 key."""
    try:
        x_pub, ed_pub = unb64(bundle["x"]), unb64(bundle["ed"])
        if len(x_pub) != 32 or len(ed_pub) != 32:
            return False
        Ed25519PublicKey.from_public_bytes(ed_pub).verify(unb64(bundle["bind"]), b"x25519:" + x_pub)
        return True
    except (KeyError, ValueError, TypeError, InvalidSignature):
        return False


def fingerprint(bundle: dict) -> str:
    """Safety number for one identity: 30 digits in groups of five, derived from both public keys."""
    digest = hashlib.sha256(b"e2ee-chat fingerprint v1" + unb64(bundle["ed"]) + unb64(bundle["x"])).digest()
    digits = "".join(f"{int.from_bytes(digest[i:i + 5], 'big') % 100000:05d}" for i in range(0, 30, 5))
    return " ".join(digits[i:i + 5] for i in range(0, 30, 5))


def _wrap_key(shared: bytes, eph_pub: bytes, recipient_x: bytes, msg_id: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=eph_pub + recipient_x,
                info=WRAP_INFO + msg_id).derive(shared)


def seal(text: str, sender: str, sender_id: Identity, room: int, recipients: dict[str, dict]) -> dict:
    """Encrypt `text` so only `recipients` ({username: public bundle}) can read it."""
    if not recipients:
        raise ValueError("no recipients")
    msg_id, msg_key, nonce = os.urandom(16), AESGCM.generate_key(256), os.urandom(12)
    header = {"v": VERSION, "sender": sender, "room": room, "id": b64(msg_id), "ts": int(time.time()),
              "to": sorted(recipients)}
    ct = AESGCM(msg_key).encrypt(nonce, text.encode("utf-8"), canonical(header))

    eph = X25519PrivateKey.generate()
    eph_pub = eph.public_key().public_bytes(**RAW)
    keys = {}
    for name in sorted(recipients):
        rx = unb64(recipients[name]["x"])
        wk = _wrap_key(eph.exchange(X25519PublicKey.from_public_bytes(rx)), eph_pub, rx, msg_id)
        wnonce = os.urandom(12)
        keys[name] = {"n": b64(wnonce), "k": b64(AESGCM(wk).encrypt(wnonce, msg_key, name.encode() + msg_id))}

    envelope = {**header, "eph": b64(eph_pub), "nonce": b64(nonce), "ct": b64(ct), "keys": keys}
    envelope["sig"] = b64(sender_id.ed.sign(canonical(envelope)))
    return envelope


def open_envelope(envelope: dict, me: str, my_id: Identity, sender_bundle: dict) -> str:
    """Verify and decrypt. Raises CryptoError on any tampering, forgery or if we aren't a recipient."""
    try:
        body = {k: v for k, v in envelope.items() if k != "sig"}
        Ed25519PublicKey.from_public_bytes(unb64(sender_bundle["ed"])).verify(unb64(envelope["sig"]), canonical(body))
        if envelope["v"] != VERSION:
            raise CryptoError("unsupported version")
        if me not in envelope["keys"] or sorted(envelope["keys"]) != envelope["to"]:
            raise CryptoError("not addressed to this user")
        msg_id, eph_pub = unb64(envelope["id"]), unb64(envelope["eph"])
        my_x = my_id.x.public_key().public_bytes(**RAW)
        wk = _wrap_key(my_id.x.exchange(X25519PublicKey.from_public_bytes(eph_pub)), eph_pub, my_x, msg_id)
        mine = envelope["keys"][me]
        msg_key = AESGCM(wk).decrypt(unb64(mine["n"]), unb64(mine["k"]), me.encode() + msg_id)
        header = {k: envelope[k] for k in ("v", "sender", "room", "id", "ts", "to")}
        return AESGCM(msg_key).decrypt(unb64(envelope["nonce"]), unb64(envelope["ct"]), canonical(header)).decode("utf-8")
    except CryptoError:
        raise
    except (InvalidSignature, InvalidTag, KeyError, ValueError, TypeError) as e:
        raise CryptoError(f"message rejected: {type(e).__name__}") from None
