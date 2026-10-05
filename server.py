"""
Multithreaded chat relay for end-to-end encrypted messages.

The server authenticates users, stores each user's *public* key bundle, hands out the
key directory, and stores/relays message envelopes it cannot read. It never sees a
private key or a plaintext message.
"""
import json
import socket
import threading
from typing import Dict, Tuple

from database import DatabaseHandler, Message
from e2ee.crypto import verify_bundle
from utils.passwords import hash_password, verify_password

HOST = '127.0.0.1'
PORT = 5555
MAX_LINE = 256 * 1024          # one JSON message per line; envelopes grow with the number of recipients


class ClientThread(threading.Thread):
    def __init__(self, conn: socket.socket, addr: Tuple[str, int], server: 'ChatServer'):
        super().__init__(daemon=True)
        self.conn, self.addr, self.server = conn, addr, server
        self.user_id = None
        self.username = None
        self.send_lock = threading.Lock()

    def send(self, payload: dict):
        try:
            with self.send_lock:
                self.conn.sendall(json.dumps(payload).encode('utf-8') + b'\n')
        except OSError:
            self.server.disconnect_client(self)

    def run(self):
        buffer = b''
        try:
            while True:
                data = self.conn.recv(65536)
                if not data:
                    break
                buffer += data
                if len(buffer) > MAX_LINE and b'\n' not in buffer:
                    break                                   # oversized message: drop the client
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if line:
                        try:
                            self.handle(json.loads(line.decode('utf-8')))
                        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
                            self.send({'type': 'error', 'message': 'Malformed request'})
        except OSError:
            pass
        self.server.disconnect_client(self)

    def handle(self, msg: dict):
        action = msg.get('action')
        s = self.server
        if action == 'register':
            s.handle_register(self, msg.get('username', ''), msg.get('password', ''), msg.get('email'), msg.get('bundle'))
        elif action == 'login':
            s.handle_login(self, msg.get('username', ''), msg.get('password', ''))
        elif not self.user_id:
            self.send({'type': 'error', 'message': 'Not authenticated'})
        elif action == 'get_keys':
            self.send({'type': 'keys', 'keys': s.public_keys()})
        elif action == 'send_message':
            s.handle_send_message(self, int(msg.get('room_id', 1)), msg.get('envelope'))
        elif action == 'get_history':
            s.handle_get_history(self, int(msg.get('room_id', 1)), int(msg.get('limit', 100)))
        else:
            self.send({'type': 'error', 'message': 'Unknown action'})


class ChatServer:
    def __init__(self, host: str, port: int, db_path: str = 'chat_app.db'):
        self.host, self.port = host, port
        self.db = DatabaseHandler(db_path)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients: Dict[int, ClientThread] = {}
        self.lock = threading.Lock()

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(50)
        print(f"E2EE chat relay listening on {self.host}:{self.port}")
        try:
            while True:
                conn, addr = self.server_socket.accept()
                ClientThread(conn, addr, self).start()
        finally:
            self.server_socket.close()

    def broadcast(self, payload: dict):
        with self.lock:
            clients = list(self.clients.values())
        for c in clients:
            c.send(payload)

    def disconnect_client(self, client: ClientThread):
        with self.lock:
            if client.user_id in self.clients and self.clients[client.user_id] is client:
                del self.clients[client.user_id]
                self.db.update_user_status(client.user_id, False)
        try:
            client.conn.close()
        except OSError:
            pass

    def public_keys(self) -> dict:
        return {name: json.loads(b) for name, b in self.db.get_public_bundles().items()}

    # --- handlers ---
    def handle_register(self, client, username, password, email, bundle):
        if not username or not password:
            client.send({'type': 'register', 'success': False, 'message': 'Username and password required'})
            return
        if not isinstance(bundle, dict) or not verify_bundle(bundle):
            client.send({'type': 'register', 'success': False, 'message': 'Missing or invalid public keys'})
            return
        user_id = self.db.create_user(username, hash_password(password), email)
        if user_id is None:
            client.send({'type': 'register', 'success': False, 'message': 'Username already exists'})
            return
        self.db.set_public_bundle(user_id, json.dumps(bundle))
        client.send({'type': 'register', 'success': True, 'message': 'Registration successful'})
        self.broadcast({'type': 'key_update', 'username': username, 'bundle': bundle})

    def handle_login(self, client, username, password):
        user = self.db.get_user_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            client.send({'type': 'login', 'success': False, 'message': 'Invalid username or password'})
            return
        client.user_id, client.username = user.user_id, user.username
        with self.lock:
            self.clients[user.user_id] = client
        self.db.update_user_status(user.user_id, True)
        client.send({'type': 'login', 'success': True, 'user': user.to_dict()})
        self.broadcast({'type': 'user_joined', 'room_id': 1, 'username': user.username})

    def handle_send_message(self, client, room_id, envelope):
        # The server can't read the envelope; it only checks the routing fields it relies on.
        if not isinstance(envelope, dict) or envelope.get('sender') != client.username or envelope.get('room') != room_id:
            client.send({'type': 'error', 'message': 'Malformed or spoofed envelope'})
            return
        msg_id = self.db.save_message(Message(sender_id=client.user_id, sender_username=client.username, room_id=room_id,
                                              content=json.dumps(envelope), message_type='e2ee', is_encrypted=True))
        self.broadcast({'type': 'message', 'message_id': msg_id, 'room_id': room_id, 'envelope': envelope})

    def handle_get_history(self, client, room_id, limit):
        envelopes = [{'message_id': m.message_id, 'envelope': json.loads(m.content)}
                     for m in self.db.get_room_messages(room_id, min(limit, 500)) if m.message_type == 'e2ee']
        client.send({'type': 'history', 'room_id': room_id, 'messages': envelopes})


if __name__ == '__main__':
    ChatServer(HOST, PORT).start()
