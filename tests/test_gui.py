"""Headless smoke test of the PyQt client: two windows chat through a real server."""
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PyQt5.QtWidgets")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_two_gui_clients_chat(tmp_path, monkeypatch):
    monkeypatch.setenv("E2EE_CHAT_HOME", str(tmp_path / "devices"))
    for name in ("information", "warning", "critical"):                 # modal dialogs would block headless runs
        monkeypatch.setattr(QtWidgets.QMessageBox, name, staticmethod(lambda *a, **k: QtWidgets.QMessageBox.No))

    import client
    from server import ChatServer
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    threading.Thread(target=ChatServer("127.0.0.1", port, str(tmp_path / "s.db")).start, daemon=True).start()
    time.sleep(0.2)
    monkeypatch.setattr(client, "PORT", port)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def spin(cond, timeout=5):
        end = time.time() + timeout
        while time.time() < end and not cond():
            app.processEvents()
            time.sleep(0.01)
        assert cond()

    received = {}
    users = {}
    for name in ("alice", "bob"):
        c = client.ChatClient()
        c.start()
        c.handle_auth({"mode": "register", "username": name, "password": "pw", "email": ""})
        spin(lambda: (Path(tmp_path / "devices" / f"{name}.identity")).exists())
        time.sleep(0.2)
        c.handle_auth({"mode": "login", "username": name, "password": "pw"})
        spin(lambda: c.chat_window is not None)
        received[name] = []
        orig = c.chat_window.add_message
        c.chat_window.add_message = lambda m, sent, orig=orig, n=name: (received[n].append(m), orig(m, sent))
        users[name] = c

    alice, bob = users["alice"], users["bob"]
    spin(lambda: "bob" in alice.session.trusted)
    assert "safety number" in alice.chat_window.room_status_label.text()

    alice.send_chat_message("<b>hello</b> bob", "text")
    spin(lambda: any(m["content"] == "<b>hello</b> bob" for m in received["bob"]))

    from PyQt5.QtCore import Qt
    labels = [w for w in bob.chat_window.findChildren(QtWidgets.QLabel) if w.text() == "<b>hello</b> bob"]
    assert labels and all(w.textFormat() == Qt.PlainText for w in labels)   # shown literally, never rendered as HTML
    for c in users.values():
        c.disconnect()
