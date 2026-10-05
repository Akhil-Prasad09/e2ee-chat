"""
Desktop notifications via plyer. Silently does nothing where notifications are unavailable.
"""
try:
    from plyer import notification
except ImportError:  # plyer is optional
    notification = None


class NotificationManager:
    def __init__(self, app_name: str = 'Chat Application'):
        self.app_name = app_name

    def _notify(self, title: str, message: str):
        if notification is None:
            return
        try:
            notification.notify(title=title, message=message[:200], app_name=self.app_name, timeout=5)
        except Exception:
            pass  # no notification backend on this system

    def notify_new_message(self, sender: str, text: str):
        self._notify(f'New message from {sender}', text)

    def notify_user_joined(self, username: str):
        self._notify('User joined', f'{username} joined the chat')
