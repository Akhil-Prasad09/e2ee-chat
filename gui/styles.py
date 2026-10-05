"""
Modern styles and themes for PyQt5 GUI
"""

# Color palette
COLORS = {
    'primary': '#6C5CE7',
    'primary_dark': '#5B4CD3',
    'secondary': '#00CEC9',
    'background': '#1E1E2E',
    'surface': '#2A2A3E',
    'surface_light': '#35354A',
    'text': '#FFFFFF',
    'text_secondary': '#A0A0B0',
    'error': '#FF6B6B',
    'success': '#51CF66',
    'warning': '#FFD93D',
    'message_sent': '#6C5CE7',
    'message_received': '#35354A',
    'border': '#404050',
    'hover': '#45455A'
}

# Main stylesheet
MAIN_STYLE = f"""
QWidget {{
    background-color: {COLORS['background']};
    color: {COLORS['text']};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}}

QPushButton {{
    background-color: {COLORS['primary']};
    color: {COLORS['text']};
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    font-weight: bold;
    font-size: 14px;
}}

QPushButton:hover {{
    background-color: {COLORS['primary_dark']};
}}

QPushButton:pressed {{
    background-color: {COLORS['primary_dark']};
    padding: 13px 23px;
}}

QPushButton:disabled {{
    background-color: {COLORS['surface']};
    color: {COLORS['text_secondary']};
}}

QLineEdit, QTextEdit {{
    background-color: {COLORS['surface']};
    color: {COLORS['text']};
    border: 2px solid {COLORS['border']};
    border-radius: 8px;
    padding: 10px 15px;
    font-size: 14px;
}}

QLineEdit:focus, QTextEdit:focus {{
    border: 2px solid {COLORS['primary']};
}}

QLabel {{
    color: {COLORS['text']};
    background: transparent;
}}

QScrollBar:vertical {{
    background-color: {COLORS['surface']};
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['primary']};
    border-radius: 6px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['primary_dark']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QListWidget {{
    background-color: {COLORS['surface']};
    border: none;
    border-radius: 8px;
    padding: 5px;
}}

QListWidget::item {{
    background-color: transparent;
    color: {COLORS['text']};
    padding: 10px;
    border-radius: 6px;
    margin: 2px;
}}

QListWidget::item:hover {{
    background-color: {COLORS['hover']};
}}

QListWidget::item:selected {{
    background-color: {COLORS['primary']};
    color: {COLORS['text']};
}}

QScrollArea {{
    border: none;
    background-color: {COLORS['background']};
}}

QToolButton {{
    background-color: {COLORS['surface']};
    border: none;
    border-radius: 8px;
    padding: 10px;
}}

QToolButton:hover {{
    background-color: {COLORS['hover']};
}}

QToolButton:pressed {{
    background-color: {COLORS['primary']};
}}
"""

# Login window specific styles
LOGIN_STYLE = MAIN_STYLE + """
QFrame#loginFrame {
    background-color: %s;
    border-radius: 20px;
}

QLabel#titleLabel {
    font-size: 32px;
    font-weight: bold;
    color: %s;
}

QLabel#subtitleLabel {
    font-size: 14px;
    color: %s;
}

QPushButton#switchButton {
    background-color: transparent;
    color: %s;
    text-decoration: underline;
    font-weight: normal;
}

QPushButton#switchButton:hover {
    color: %s;
}
""" % (
    COLORS['surface'], 
    COLORS['primary'], 
    COLORS['text_secondary'],
    COLORS['secondary'],
    COLORS['primary']
)

# Chat window specific styles
CHAT_STYLE = MAIN_STYLE + """
QFrame#sidebarFrame {
    background-color: %s;
    border-right: 1px solid %s;
}

QFrame#chatFrame {
    background-color: %s;
}

QFrame#inputFrame {
    background-color: %s;
    border-top: 1px solid %s;
}

QLabel#headerLabel {
    font-size: 18px;
    font-weight: bold;
}

QLabel#statusLabel {
    font-size: 12px;
    color: %s;
}

QPushButton#sendButton {
    background-color: %s;
    min-width: 60px;
}

QPushButton#attachButton {
    background-color: %s;
    border-radius: 20px;
    padding: 10px;
    min-width: 40px;
    max-width: 40px;
}
""" % (
    COLORS['surface'],
    COLORS['border'],
    COLORS['background'],
    COLORS['surface'],
    COLORS['border'],
    COLORS['text_secondary'],
    COLORS['primary'],
    COLORS['surface_light']
)

def get_message_style(is_sent: bool) -> str:
    """Get style for message bubble"""
    bg_color = COLORS['message_sent'] if is_sent else COLORS['message_received']
    align = 'right' if is_sent else 'left'
    
    return f"""
        QFrame {{
            background-color: {bg_color};
            border-radius: 15px;
            padding: 10px 15px;
            margin: 5px;
        }}
        QLabel {{
            background: transparent;
            color: {COLORS['text']};
        }}
    """
