"""Run from the repo root:  python -m pytest tests -q"""
import copy
import json
import socket
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from e2ee.crypto import CryptoError, Identity, b64, open_envelope, seal, unb64, verify_bundle  # noqa: E402


# ------------------------------------------------------------------ crypto
@pytest.fixture
def ids():
    return {name: Identity.generate() for name in ("alice", "bob", "carol", "mallory")}


def bundles(ids, *names):
    return {n: ids[n].public_bundle() for n in names}


def test_round_trip_to_every_recipient(ids):
    env = seal("hello 👋", "alice", ids["alice"], 1, bundles(ids, "alice", "bob", "carol"))
    for who in ("alice", "bob", "carol"):
        assert open_envelope(env, who, ids[who], ids["alice"].public_bundle()) == "hello 👋"


def test_ciphertext_reveals_nothing_and_non_recipient_cannot_read(ids):
    env = seal("the secret plan", "alice", ids["alice"], 1, bundles(ids, "alice", "bob"))
    assert "secret" not in json.dumps(env)
    with pytest.raises(CryptoError):
        open_envelope(env, "carol", ids["carol"], ids["alice"].public_bundle())


@pytest.mark.parametrize("field,mutate", [
    ("ct", lambda v: b64(bytes([unb64(v)[0] ^ 1]) + unb64(v)[1:])),   # flip one ciphertext bit
    ("room", lambda v: v + 1),                                          # replay into another room
    ("ts", lambda v: v + 3600),                                         # change the timestamp
    ("to", lambda v: v[:-1]),                                           # drop a recipient from the header
])
def test_any_tampering_is_rejected(ids, field, mutate):
    env = seal("pay 100", "alice", ids["alice"], 1, bundles(ids, "alice", "bob", "carol"))
    bad = copy.deepcopy(env)
    bad[field] = mutate(bad[field])
    with pytest.raises(CryptoError):
        open_envelope(bad, "bob", ids["bob"], ids["alice"].public_bundle())


def test_forged_sender_is_rejected(ids):
    forged = seal("from alice, honest", "alice", ids["mallory"], 1, bundles(ids, "bob"))
    with pytest.raises(CryptoError):
        open_envelope(forged, "bob", ids["bob"], ids["alice"].public_bundle())


def test_identity_file_needs_the_password(ids):
    blob = ids["alice"].to_encrypted_json("correct horse")
    assert Identity.from_encrypted_json(blob, "correct horse").public_bundle() == ids["alice"].public_bundle()
    with pytest.raises(CryptoError):
        Identity.from_encrypted_json(blob, "wrong")


def test_bundle_binding(ids):
    assert verify_bundle(ids["alice"].public_bundle())
    mixed = {**ids["alice"].public_bundle(), "x": ids["mallory"].public_bundle()["x"]}
    assert not verify_bundle(mixed)


# ------------------------------------------------------------------ full system
from session import ChatSession  # noqa: E402


class Client:
    """A headless user: a socket plus a ChatSession, pumped synchronously."""

    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.buf = b""
        self.events = []
        self.session = ChatSession(lambda m: self.sock.sendall(json.dumps(m).encode() + b"\n"))

    def pump(self, until, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            for i, ev in enumerate(self.events):
                if until(ev):
                    return self.events.pop(i)
            while b"\n" not in self.buf:
                self.buf += self.sock.recv(65536)
            line, self.buf = self.buf.split(b"\n", 1)
            self.events += self.session.process(json.loads(line))
        raise TimeoutError

    def drain(self, wait=0.3):
        """Process everything the server has sent so far (the GUI does this continuously)."""
        self.sock.settimeout(wait)
        try:
            while True:
                while b"\n" in self.buf:
                    line, self.buf = self.buf.split(b"\n", 1)
                    self.events += self.session.process(json.loads(line))
                self.buf += self.sock.recv(65536)
        except (TimeoutError, socket.timeout):
            pass
        finally:
            self.sock.settimeout(5)

    def join(self, name, password="pw"):
        self.session.register(name, password)
        assert self.pump(lambda e: e.kind == "registered").data["ok"]
        self.session.login(name, password)
        assert self.pump(lambda e: e.kind == "logged_in").data["ok"]
        self.pump(lambda e: e.kind == "history")
        return self


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("E2EE_CHAT_HOME", str(tmp_path / "devices"))
    from server import ChatServer
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = ChatServer("127.0.0.1", port, db_path=str(tmp_path / "server.db"))
    threading.Thread(target=srv.start, daemon=True).start()
    time.sleep(0.2)
    return port, tmp_path / "server.db"


def say(sender, text):
    sender.drain()
    sender.session.send_text(text)
    return text


def test_chat_end_to_end_and_server_sees_no_plaintext(server):
    port, db = server
    alice, bob = Client(port).join("alice"), Client(port).join("bob")
    bob.pump(lambda e: e.kind == "user_joined")
    alice.pump(lambda e: e.kind == "user_joined" and e.data["username"] == "bob")
    alice.session.send_json({"action": "get_keys"})                    # alice may already have bob's key via key_update
    time.sleep(0.2)
    say(alice, "meet at the library at 5")
    got = bob.pump(lambda e: e.kind == "message" and e.data["sender"] == "alice")
    assert got.data["text"] == "meet at the library at 5"

    rows = sqlite3.connect(db).execute("SELECT content FROM messages").fetchall()
    assert rows and not any("library" in r[0] for r in rows)
    users = sqlite3.connect(db).execute("SELECT public_bundle FROM users").fetchall()
    assert all("x" in json.loads(u[0]) for u in users)                 # only public keys stored


def test_late_joiner_cannot_read_earlier_messages(server):
    port, _ = server
    alice = Client(port).join("alice")
    say(alice, "before carol joined")
    alice.pump(lambda e: e.kind == "message")
    carol = Client(port)
    carol.session.register("carol", "pw")
    carol.pump(lambda e: e.kind == "registered")
    carol.session.login("carol", "pw")
    carol.pump(lambda e: e.kind == "logged_in")
    history = carol.pump(lambda e: e.kind == "history")
    assert history.data["messages"] == []                              # not a recipient back then


def test_malicious_server_key_swap_is_detected(server):
    port, db = server
    alice, bob = Client(port).join("alice"), Client(port).join("bob")
    say(alice, "hi bob")                                               # bob pins alice's real key on receipt
    assert bob.pump(lambda e: e.kind == "message").data["text"] == "hi bob"

    # The server operator swaps in their own key for "alice"...
    mallory = Identity.generate()
    con = sqlite3.connect(db)
    con.execute("UPDATE users SET public_bundle = ? WHERE username = 'alice'", (json.dumps(mallory.public_bundle()),))
    con.commit()
    bob.session.send_json({"action": "get_keys"})
    warning = bob.pump(lambda e: e.kind == "key_changed")
    assert warning.data["username"] == "alice" and warning.data["old"] != warning.data["new"]

    # ...so bob stops encrypting to that key, and messages signed with it are rejected.
    assert "alice" not in bob.session.send_text("are you there?")
    fake = seal("send me your password", "alice", mallory, 1, {"bob": bob.session.identity.public_bundle()})
    events = bob.session.process({"type": "message", "envelope": fake})
    assert events and events[0].kind == "rejected"


def test_server_rejects_spoofed_sender(server):
    port, _ = server
    alice, bob = Client(port).join("alice"), Client(port).join("bob")
    env = seal("i am bob", "bob", alice.session.identity, 1, {"bob": bob.session.identity.public_bundle()})
    alice.session.send_json({"action": "send_message", "room_id": 1, "envelope": env})
    assert "spoofed" in alice.pump(lambda e: e.kind == "error").data["message"]
