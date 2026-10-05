# E2EE Chat

An end-to-end encrypted group chat in Python: a PyQt5 desktop client and a multithreaded relay server that **stores and forwards messages it cannot read**. Each user's keys are generated and kept on their own device; the server only ever sees public keys and encrypted envelopes.

It grew out of my [internship chat app](https://github.com/Akhil-Prasad09/OIBSP/tree/main/Chat%20Application), which encrypted messages with one key the server held. This version removes the server from the trust boundary for message content.

## How it works

**Identity.** At registration the client generates an X25519 key pair (key agreement) and an Ed25519 key pair (signatures). Only the public halves go to the server, as a bundle in which the Ed25519 key signs the X25519 key so the two can't be mixed and matched. The private keys are stored on disk encrypted with AES-256-GCM under a key derived from the user's password (scrypt, N=2^15).

**Sending a message** (`e2ee/crypto.py`):
1. Generate a random 256-bit message key and encrypt the text with **AES-256-GCM**. The header (sender, room, message ID, timestamp, recipient list) is bound as associated data.
2. Generate a fresh **ephemeral X25519** key. For each recipient, derive a wrapping key with HKDF-SHA256 from the ECDH result and use it to encrypt the message key.
3. **Sign** the whole envelope with the sender's Ed25519 key.

**Receiving:** verify the signature against the sender's *pinned* key, unwrap the message key, then decrypt. Any change to any byte (ciphertext, header, recipient list) fails one of these checks, and the message is rejected rather than displayed.

**Trusting keys.** The classic attack on E2EE is the server handing out *its own* public key for someone. Clients defend against it the way Signal does:
- **Pinning (trust on first use):** the first key seen for each user is remembered on the device (`e2ee/keystore.py`).
- **Change warnings:** if the server later presents a different key, the client stops encrypting to it, rejects messages signed with it, and shows a "safety number changed" warning with both numbers.
- **Safety numbers:** a 30-digit fingerprint per user (shown in the chat header, and for each contact on hover in the sidebar), which two people can compare in person or by phone.

## What the tests prove

`python -m pytest tests -q` runs 14 tests, including:

| Property | Test |
|---|---|
| Every recipient can decrypt; the envelope contains no plaintext | `test_round_trip_to_every_recipient`, `test_ciphertext_reveals_nothing_and_non_recipient_cannot_read` |
| A non-recipient can't decrypt | same |
| Flipping a ciphertext bit, moving a message to another room, changing its timestamp, or dropping a recipient is rejected | `test_any_tampering_is_rejected` |
| A message signed by someone else but claiming to be from Alice is rejected | `test_forged_sender_is_rejected` |
| The private key file is useless without the password | `test_identity_file_needs_the_password` |
| Over a real server: the database holds only ciphertext and public keys | `test_chat_end_to_end_and_server_sees_no_plaintext` |
| Someone who joins later can't read earlier messages | `test_late_joiner_cannot_read_earlier_messages` |
| **A server that swaps a user's public key is detected; the client stops encrypting to it and rejects messages signed with it** | `test_malicious_server_key_swap_is_detected` |
| A logged-in user can't send as someone else | `test_server_rejects_spoofed_sender` |
| The GUI end to end: two windows chat; message text is shown literally, never rendered as HTML | `test_two_gui_clients_chat` |

## Threat model and limitations

Protected against a server operator, or anyone with the server's database: they can't read messages, forge messages from a user, alter messages undetected, or silently substitute keys after first contact.

Not protected, stated plainly:
- **No forward secrecy for long-term keys.** Each message uses a fresh ephemeral sender key, but if a *recipient's* long-term private key is stolen, every message ever sent to them can be decrypted. Signal's double ratchet fixes this; it isn't implemented here.
- **First contact is trust-on-first-use.** A server that lies about a key *before* you first see it isn't caught unless you compare safety numbers.
- **Metadata is visible to the server:** who sends, when, to whom, and roughly how long each message is.
- **One device per user.** Keys never leave the device that created them, so there's no multi-device support or key recovery.
- **Transport isn't TLS.** Message content is protected end to end, but the login password reaches the server in the clear over the socket. Put the server behind TLS before using it across a network.
- **Group membership is "everyone registered".** There's a single room; per-room membership and removal aren't implemented.
- Not audited. This is a learning project, not a replacement for Signal.

## Run

Python 3.10+.

```bash
pip install -r requirements.txt
python server.py            # relay on localhost:5555
python client.py            # one window per user: register, then log in
```

On Windows you can double-click `1_Start_Server.bat` and then `2_Start_Client.bat`. Keys are stored in `~/.e2ee_chat/` (override with `E2EE_CHAT_HOME`).

## Layout

```
e2ee/crypto.py      identities, seal/open, fingerprints
e2ee/keystore.py    password-encrypted identity files, key pinning
session.py          client protocol + E2EE state (shared by the GUI and the tests)
client.py           PyQt5 client
server.py           relay: accounts, public-key directory, envelope storage
database/           SQLite
gui/                login and chat windows
tests/              crypto, protocol and GUI tests
```
