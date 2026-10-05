"""
PyQt5 desktop client. Networking runs on a QThread; all E2EE logic lives in session.ChatSession.
"""
import json
import socket
import sys

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMessageBox

from e2ee.crypto import CryptoError
from gui import ChatWindow, LoginWindow
from session import ChatSession
from utils import NotificationManager

HOST = '127.0.0.1'
PORT = 5555


class NetworkThread(QThread):
    message_received = pyqtSignal(dict)
    disconnected = pyqtSignal()

    def __init__(self, sock: socket.socket):
        super().__init__()
        self.sock, self.running, self.buffer = sock, True, b''

    def run(self):
        while self.running:
            try:
                data = self.sock.recv(65536)
            except OSError:
                break
            if not data:
                break
            self.buffer += data
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                if line:
                    try:
                        self.message_received.emit(json.loads(line.decode('utf-8')))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
        self.disconnected.emit()

    def stop(self):
        self.running = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class ChatClient:
    def __init__(self):
        self.sock = None
        self.network_thread = None
        self.session = None
        self.notifier = NotificationManager()
        self.login_window = None
        self.chat_window = None

    def start(self):
        self.login_window = LoginWindow()
        self.login_window.login_success.connect(self.handle_auth)
        self.login_window.show()

    # ------------------------------------------------------------- connection
    def connect_to_server(self) -> bool:
        try:
            self.sock = socket.create_connection((HOST, PORT))
        except OSError:
            QMessageBox.critical(None, "Connection Error",
                                 f"Could not connect to the server.\nMake sure it is running on {HOST}:{PORT}")
            self.sock = None
            return False
        self.session = ChatSession(self.send_json)
        self.network_thread = NetworkThread(self.sock)
        self.network_thread.message_received.connect(self.handle_server_message)
        self.network_thread.disconnected.connect(self.handle_disconnection)
        self.network_thread.start()
        return True

    def send_json(self, data: dict):
        if self.sock:
            try:
                self.sock.sendall(json.dumps(data).encode('utf-8') + b'\n')
            except OSError as e:
                print(f"Send error: {e}")

    # ------------------------------------------------------------- auth
    def handle_auth(self, data: dict):
        if not self.sock and not self.connect_to_server():
            self.login_window.reset_button()
            return
        try:
            if data['mode'] == 'register':
                self.session.register(data['username'], data['password'], data.get('email', ''))
            else:
                self.session.login(data['username'], data['password'])
        except FileExistsError:
            self.login_window.show_error("This device already has keys for that username. Log in instead.")
            self.login_window.reset_button()
        except FileNotFoundError:
            self.login_window.show_error("No keys for this user on this device. Keys never leave the device "
                                         "they were created on, so log in from that device.")
            self.login_window.reset_button()
        except CryptoError:
            self.login_window.show_error("Wrong password.")
            self.login_window.reset_button()

    # ------------------------------------------------------------- events
    def handle_server_message(self, msg: dict):
        for ev in self.session.process(msg):
            handler = getattr(self, f"on_{ev.kind}", None)
            if handler:
                handler(ev.data)

    def on_registered(self, d):
        if d['ok']:
            QMessageBox.information(self.login_window, "Registered",
                                    "Account created. Your encryption keys were generated on this device.\nPlease log in.")
        else:
            self.login_window.show_error(d['message'] or 'Registration failed')
        self.login_window.reset_button()

    def on_logged_in(self, d):
        if not d['ok']:
            self.login_window.show_error(d['message'] or 'Login failed')
            self.login_window.reset_button()
            return
        self.login_window.hide()
        self.chat_window = ChatWindow(d['user'])
        self.chat_window.send_message.connect(self.send_chat_message)
        self.chat_window.disconnect_requested.connect(self.disconnect)
        self.chat_window.room_status_label.setText(
            f"🔒 End-to-end encrypted · your safety number: {self.session.safety_number()}")
        self.chat_window.show()

    def on_message(self, d):
        if not self.chat_window:
            return
        is_sent = d['sender'] == self.session.username
        self.chat_window.add_message({'sender': d['sender'], 'content': d['text'], 'timestamp': None}, is_sent)
        self.refresh_contacts()
        if not is_sent:
            self.notifier.notify_new_message(d['sender'], d['text'])

    def on_history(self, d):
        if self.chat_window:
            self.chat_window.load_message_history(
                [{'sender_username': m['sender'], 'content': m['text']} for m in d['messages']])
            self.refresh_contacts()

    def on_rejected(self, d):
        if self.chat_window:
            self.chat_window.show_notification("Message rejected",
                                               f"from {d['sender']}: failed verification ({d['reason']})")

    def on_key_changed(self, d):
        who = "YOUR OWN key on the server" if d['is_self'] else f"{d['username']}'s key"
        answer = QMessageBox.warning(
            self.chat_window or self.login_window, "Safety number changed",
            f"{who} changed.\n\nOld: {d['old']}\nNew: {d['new']}\n\n"
            "This happens if they reinstalled, or if the server is trying to intercept messages.\n"
            "Compare the new number with them in person or by phone before accepting.\n\nAccept the new key?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes and not d['is_self']:
            self.session.accept_key(d['username'])
        self.refresh_contacts()

    def on_user_joined(self, d):
        if self.chat_window and d['username'] != self.session.username:
            self.chat_window.show_notification("User joined", f"{d['username']} joined the chat")
            self.notifier.notify_user_joined(d['username'])

    def on_error(self, d):
        QMessageBox.warning(None, "Error", d['message'])

    def refresh_contacts(self):
        """Sidebar: everyone whose key we trust; hover shows their safety number."""
        if not self.chat_window:
            return
        lst = self.chat_window.users_list
        lst.clear()
        for name in sorted(self.session.trusted):
            lst.addItem(f"🔒 {name}")
            lst.item(lst.count() - 1).setToolTip(f"Safety number: {self.session.safety_number(name)}")
        for name in sorted(self.session.changed):
            lst.addItem(f"⚠️ {name} (key changed)")

    # ------------------------------------------------------------- sending / teardown
    def send_chat_message(self, content: str, message_type: str):
        self.session.send_text(content)

    def disconnect(self):
        if self.network_thread:
            self.network_thread.stop()
            self.network_thread = None
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        if self.chat_window:
            self.chat_window.close()
            self.chat_window = None
        self.session = None
        self.login_window.show()
        self.login_window.reset_button()

    def handle_disconnection(self):
        if self.sock:
            QMessageBox.warning(None, "Disconnected", "Connection to server lost.")
            self.disconnect()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    client = ChatClient()
    client.start()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
