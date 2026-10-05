"""
Client-side protocol + E2EE state, independent of the GUI (the PyQt client and the tests both use it).

    session = ChatSession(send_json)          # send_json(dict) writes one request to the server
    session.register(user, password)          # creates this device's identity, publishes public keys
    session.login(user, password)             # unlocks the identity, then fetches keys and history
    session.send_text("hi")                   # sealed to every user whose key we trust (and ourselves)
    for event in session.process(server_msg): ...
"""
from dataclasses import dataclass, field

from e2ee import keystore
from e2ee.crypto import CryptoError, Identity, fingerprint, open_envelope, seal


@dataclass
class Event:
    kind: str                     # registered, logged_in, message, history, rejected, key_changed, user_joined, error
    data: dict = field(default_factory=dict)


class ChatSession:
    def __init__(self, send_json):
        self.send_json = send_json
        self.username: str | None = None
        self.identity: Identity | None = None
        self.pins: keystore.Pins | None = None
        self.trusted: dict[str, dict] = {}       # username -> bundle we will encrypt to / accept signatures from
        self.changed: dict[str, dict] = {}       # username -> new, unaccepted bundle the server presented
        self.pending: list[dict] = []            # envelopes from senders whose key we haven't fetched yet
        self._registering: tuple[str, str] | None = None

    # ---------------------------------------------------------------- requests
    def register(self, username: str, password: str, email: str = ''):
        identity = keystore.create_identity(username, password)
        self._registering = (username, password)
        self.send_json({'action': 'register', 'username': username, 'password': password,
                        'email': email, 'bundle': identity.public_bundle()})

    def login(self, username: str, password: str):
        self.identity = keystore.load_identity(username, password)   # raises before anything is sent
        self.username = username
        self.pins = keystore.Pins(username)
        self.pins.accept(username, self.identity.public_bundle())
        self.send_json({'action': 'login', 'username': username, 'password': password})

    def send_text(self, text: str, room: int = 1) -> list[str]:
        """Encrypt to everyone we trust; returns the recipients so the UI can show who can read it."""
        recipients = {**self.trusted, self.username: self.identity.public_bundle()}
        envelope = seal(text, self.username, self.identity, room, recipients)
        self.send_json({'action': 'send_message', 'room_id': room, 'envelope': envelope})
        return sorted(recipients)

    def accept_key(self, username: str):
        """User compared safety numbers out of band and accepts the new key."""
        bundle = self.changed.pop(username)
        self.pins.accept(username, bundle)
        self.trusted[username] = bundle

    def safety_number(self, username: str | None = None) -> str:
        if username in (None, self.username):
            return fingerprint(self.identity.public_bundle())
        bundle = self.trusted.get(username) or self.changed.get(username)
        return fingerprint(bundle) if bundle else ''

    # ---------------------------------------------------------------- responses
    def process(self, msg: dict) -> list[Event]:
        kind = msg.get('type')
        if kind == 'register':
            user, _ = self._registering or (None, None)
            if not msg.get('success') and user:
                keystore.identity_path(user).unlink(missing_ok=True)   # don't keep keys for a name we didn't get
            self._registering = None
            return [Event('registered', {'ok': bool(msg.get('success')), 'message': msg.get('message', '')})]
        if kind == 'login':
            if msg.get('success'):
                self.send_json({'action': 'get_keys'})
                self.send_json({'action': 'get_history', 'room_id': 1, 'limit': 100})
            return [Event('logged_in', {'ok': bool(msg.get('success')), 'message': msg.get('message', ''),
                                        'user': msg.get('user', {})})]
        if kind == 'keys':
            events = []
            for user, bundle in msg.get('keys', {}).items():
                events += self._learn_key(user, bundle)
            return events + self._retry_pending()
        if kind == 'key_update':
            return self._learn_key(msg['username'], msg['bundle']) + self._retry_pending()
        if kind == 'message':
            return self._open(msg['envelope'], msg.get('message_id'))
        if kind == 'history':
            shown, events = [], []
            for item in msg.get('messages', []):
                for ev in self._open(item['envelope'], item.get('message_id'), history=True):
                    (shown if ev.kind == 'message' else events).append(ev)
            return events + [Event('history', {'messages': [e.data for e in shown]})]
        if kind == 'user_joined':
            return [Event('user_joined', {'username': msg.get('username')})]
        if kind == 'error':
            return [Event('error', {'message': msg.get('message', '')})]
        return []

    # ---------------------------------------------------------------- internals
    def _learn_key(self, user: str, bundle: dict) -> list[Event]:
        status = self.pins.check(user, bundle)
        if status in ('new', 'match'):
            if user != self.username:
                self.trusted[user] = bundle
            return []
        if status == 'changed':
            self.trusted.pop(user, None)
            self.changed[user] = bundle
            return [Event('key_changed', {'username': user, 'old': fingerprint(self.pins.get(user)),
                                          'new': fingerprint(bundle), 'is_self': user == self.username})]
        return []                                                    # invalid bundle: ignore it

    def _open(self, envelope: dict, message_id=None, history: bool = False) -> list[Event]:
        sender = envelope.get('sender') if isinstance(envelope, dict) else None
        if sender == self.username:
            bundle = self.identity.public_bundle()
        else:
            bundle = self.trusted.get(sender)
        if bundle is None:
            if sender in self.changed:
                return [Event('rejected', {'sender': sender, 'reason': "sender's key changed and isn't accepted yet"})]
            if not history:
                self.pending.append(envelope)
                self.send_json({'action': 'get_keys'})
            return []
        if self.username not in envelope.get('to', []):
            return []                                                # sent before we were a recipient
        try:
            text = open_envelope(envelope, self.username, self.identity, bundle)
        except CryptoError as e:
            return [Event('rejected', {'sender': sender, 'reason': str(e)})]
        return [Event('message', {'sender': sender, 'text': text, 'message_id': message_id, 'ts': envelope.get('ts')})]

    def _retry_pending(self) -> list[Event]:
        waiting, self.pending = self.pending, []
        events = []
        for env in waiting:
            if env.get('sender') in self.trusted:
                events += self._open(env)
            else:
                self.pending.append(env)
        return events
