"""
GUI package for chat application
"""
from .login_window import LoginWindow
from .chat_window import ChatWindow
from .styles import COLORS, LOGIN_STYLE, CHAT_STYLE

__all__ = ['LoginWindow', 'ChatWindow', 'COLORS', 'LOGIN_STYLE', 'CHAT_STYLE']
