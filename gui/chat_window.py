"""
Main chat window with animations, multimedia support, and advanced features
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTextEdit, QScrollArea, QFrame, QListWidget, QFileDialog,
                             QGraphicsOpacityEffect, QSizePolicy, QToolButton)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QPixmap, QIcon
import emoji
from datetime import datetime
from .styles import CHAT_STYLE, COLORS, get_message_style


class MessageBubble(QFrame):
    """Animated message bubble widget"""
    
    def __init__(self, message: dict, is_sent: bool, parent=None):
        super().__init__(parent)
        self.message = message
        self.is_sent = is_sent
        self.init_ui()
        self.animate_in()
        
    def init_ui(self):
        """Initialize message bubble UI"""
        self.setStyleSheet(get_message_style(self.is_sent))
        self.setMaximumWidth(500)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Sender name (only for received messages)
        if not self.is_sent:
            # Support both 'sender' and 'sender_username' keys
            sender_name = self.message.get('sender') or self.message.get('sender_username', 'Unknown')
            sender_label = QLabel(sender_name)
            sender_label.setTextFormat(Qt.PlainText)   # never render peer-supplied text as HTML
            sender_label.setStyleSheet(f"color: {COLORS['secondary']}; font-weight: bold; font-size: 12px;")
            layout.addWidget(sender_label)
        
        # Message content
        content_label = QLabel()
        content = self.message.get('content', '')
        
        # Process emojis
        content = emoji.emojize(content, language='alias')
        
        content_label.setTextFormat(Qt.PlainText)      # message text is attacker-controlled: no rich text
        content_label.setText(content)
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(content_label)
        
        # Timestamp
        timestamp = self.message.get('timestamp', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%I:%M %p')
            except:
                time_str = timestamp
        else:
            time_str = datetime.now().strftime('%I:%M %p')
            
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 10px;")
        time_label.setAlignment(Qt.AlignRight if self.is_sent else Qt.AlignLeft)
        layout.addWidget(time_label)
        
        self.setLayout(layout)
        
    def animate_in(self):
        """Animate message bubble entrance"""
        # Fade in effect
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim.start()


class ChatWindow(QWidget):
    """Main chat window with all features"""
    
    send_message = pyqtSignal(str, str)  # content, message_type
    disconnect_requested = pyqtSignal()
    
    def __init__(self, user_data: dict):
        super().__init__()
        self.user_data = user_data
        self.current_room_id = 1
        self.messages_container = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize chat window UI"""
        self.setWindowTitle(f"Chat - {self.user_data.get('username', 'User')}")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(CHAT_STYLE)
        
        # Center window
        from PyQt5.QtWidgets import QDesktopWidget
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )
        
        # Main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)
        
        # Chat area
        chat_area = self.create_chat_area()
        main_layout.addWidget(chat_area)
        
        self.setLayout(main_layout)
        
        # Fade in animation
        self.setup_entrance_animation()
        
    def create_sidebar(self) -> QFrame:
        """Create sidebar with rooms and users"""
        sidebar = QFrame()
        sidebar.setObjectName("sidebarFrame")
        sidebar.setFixedWidth(280)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(15)
        
        # User info
        user_frame = QFrame()
        user_layout = QVBoxLayout()
        user_layout.setSpacing(5)
        
        username_label = QLabel(self.user_data.get('username', 'User'))
        username_label.setObjectName("headerLabel")
        user_layout.addWidget(username_label)
        
        status_label = QLabel("● Online")
        status_label.setObjectName("statusLabel")
        status_label.setStyleSheet(f"color: {COLORS['success']};")
        user_layout.addWidget(status_label)
        
        user_frame.setLayout(user_layout)
        layout.addWidget(user_frame)
        
        # Rooms section
        rooms_label = QLabel("Chat Rooms")
        rooms_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        layout.addWidget(rooms_label)
        
        self.rooms_list = QListWidget()
        self.rooms_list.addItem("General")
        self.rooms_list.setCurrentRow(0)
        layout.addWidget(self.rooms_list)
        
        # Online users section
        users_label = QLabel("Online Users")
        users_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        layout.addWidget(users_label)
        
        self.users_list = QListWidget()
        layout.addWidget(self.users_list)
        
        # Settings button
        settings_btn = QPushButton("Settings")
        settings_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(settings_btn)
        
        # Disconnect button
        disconnect_btn = QPushButton("Disconnect")
        disconnect_btn.setStyleSheet(f"background-color: {COLORS['error']};")
        disconnect_btn.setCursor(Qt.PointingHandCursor)
        disconnect_btn.clicked.connect(self.disconnect_requested.emit)
        layout.addWidget(disconnect_btn)
        
        sidebar.setLayout(layout)
        return sidebar
        
    def create_chat_area(self) -> QFrame:
        """Create main chat area"""
        chat_frame = QFrame()
        chat_frame.setObjectName("chatFrame")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = self.create_header()
        layout.addWidget(header)
        
        # Messages area
        self.messages_scroll = QScrollArea()
        self.messages_scroll.setWidgetResizable(True)
        self.messages_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        messages_widget = QWidget()
        self.messages_layout = QVBoxLayout()
        self.messages_layout.setContentsMargins(20, 20, 20, 20)
        self.messages_layout.setSpacing(10)
        self.messages_layout.addStretch()
        messages_widget.setLayout(self.messages_layout)
        
        self.messages_scroll.setWidget(messages_widget)
        layout.addWidget(self.messages_scroll)
        
        # Input area
        input_frame = self.create_input_area()
        layout.addWidget(input_frame)
        
        chat_frame.setLayout(layout)
        return chat_frame
        
    def create_header(self) -> QFrame:
        """Create chat header"""
        header = QFrame()
        header.setStyleSheet(f"background-color: {COLORS['surface']}; border-bottom: 1px solid {COLORS['border']};")
        header.setFixedHeight(70)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(25, 15, 25, 15)
        
        # Room info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        self.room_name_label = QLabel("General")
        self.room_name_label.setObjectName("headerLabel")
        info_layout.addWidget(self.room_name_label)
        
        self.room_status_label = QLabel("Everyone can chat here")
        self.room_status_label.setObjectName("statusLabel")
        info_layout.addWidget(self.room_status_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Action buttons
        emoji_btn = QToolButton()
        emoji_btn.setText("😊")
        emoji_btn.setToolTip("Emoji Picker")
        emoji_btn.setCursor(Qt.PointingHandCursor)
        emoji_btn.clicked.connect(self.show_emoji_picker)
        layout.addWidget(emoji_btn)
        
        header.setLayout(layout)
        return header
        
    def create_input_area(self) -> QFrame:
        """Create message input area"""
        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        input_frame.setFixedHeight(100)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)
        
        # Attach button
        attach_btn = QPushButton("📎")
        attach_btn.setObjectName("attachButton")
        attach_btn.setToolTip("Attach file or image")
        attach_btn.setCursor(Qt.PointingHandCursor)
        attach_btn.clicked.connect(self.attach_file)
        layout.addWidget(attach_btn)
        
        # Message input
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.setMaximumHeight(70)
        self.message_input.setTabChangesFocus(True)
        layout.addWidget(self.message_input)
        
        # Send button
        send_btn = QPushButton("Send")
        send_btn.setObjectName("sendButton")
        send_btn.setFixedWidth(100)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.clicked.connect(self.send_message_handler)
        layout.addWidget(send_btn)
        
        input_frame.setLayout(layout)
        return input_frame
        
    def send_message_handler(self):
        """Handle sending message"""
        content = self.message_input.toPlainText().strip()
        if not content:
            return
        
        # Emit signal
        self.send_message.emit(content, 'text')
        
        # Clear input with animation
        self.message_input.clear()
        
    def add_message(self, message: dict, is_sent: bool = False):
        """Add message to chat with animation"""
        # Create message bubble
        bubble = MessageBubble(message, is_sent)
        
        # Wrapper for alignment
        wrapper = QHBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        
        if is_sent:
            wrapper.addStretch()
            wrapper.addWidget(bubble)
        else:
            wrapper.addWidget(bubble)
            wrapper.addStretch()
        
        # Insert before stretch
        count = self.messages_layout.count()
        self.messages_layout.insertLayout(count - 1, wrapper)
        
        # Scroll to bottom with delay
        QTimer.singleShot(100, self.scroll_to_bottom)
        
    def scroll_to_bottom(self):
        """Scroll chat to bottom"""
        scrollbar = self.messages_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def load_message_history(self, messages: list):
        """Load message history"""
        current_user = self.user_data.get('username', '')
        
        for msg in messages:
            is_sent = msg.get('sender_username') == current_user
            self.add_message(msg, is_sent)
            
    def update_online_users(self, users: list):
        """Update online users list"""
        self.users_list.clear()
        for user in users:
            username = user.get('username', '')
            if username != self.user_data.get('username'):
                self.users_list.addItem(f"● {username}")
                
    def show_emoji_picker(self):
        """Show emoji picker (simplified)"""
        common_emojis = ['😊', '😂', '❤️', '👍', '🎉', '🔥', '💯', '✨', '🚀', '👀']
        emoji_text = ' '.join(common_emojis)
        
        current_text = self.message_input.toPlainText()
        self.message_input.setPlainText(current_text + emoji_text)
        
    def attach_file(self):
        """Handle file attachment"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Images (*.png *.jpg *.jpeg *.gif);;All Files (*.*)"
        )
        
        if file_path:
            # For now, just show the filename
            filename = file_path.split('/')[-1].split('\\')[-1]
            current_text = self.message_input.toPlainText()
            self.message_input.setPlainText(f"{current_text}\n[File: {filename}]")
            
    def setup_entrance_animation(self):
        """Setup entrance animation"""
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        
        self.entrance_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.entrance_anim.setDuration(500)
        self.entrance_anim.setStartValue(0)
        self.entrance_anim.setEndValue(1)
        self.entrance_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.entrance_anim.start()
        
    def show_notification(self, title: str, message: str):
        """Show in-app notification"""
        # Simple notification label that fades out
        notif = QLabel(f"{title}: {message}")
        notif.setStyleSheet(f"""
            background-color: {COLORS['surface']};
            color: {COLORS['text']};
            padding: 15px;
            border-radius: 10px;
            border: 2px solid {COLORS['primary']};
        """)
        notif.setFixedSize(300, 80)
        notif.setWordWrap(True)
        notif.setParent(self)
        notif.move(self.width() - 320, 20)
        notif.show()
        
        # Fade out after 3 seconds
        QTimer.singleShot(3000, lambda: self.fade_out_notification(notif))
        
    def fade_out_notification(self, notif: QLabel):
        """Fade out notification"""
        effect = QGraphicsOpacityEffect()
        notif.setGraphicsEffect(effect)
        
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(500)
        anim.setStartValue(1)
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        anim.finished.connect(notif.deleteLater)
        anim.start()
        
        # Store to prevent garbage collection
        self._notif_anim = anim
