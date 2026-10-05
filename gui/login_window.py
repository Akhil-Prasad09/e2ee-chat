"""
Login and registration window with animations
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QFrame, QGraphicsOpacityEffect)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QPoint
from PyQt5.QtGui import QFont
from .styles import LOGIN_STYLE, COLORS


class LoginWindow(QWidget):
    """Login/Register window with smooth transitions"""
    
    login_success = pyqtSignal(dict)  # Emits user data on successful login
    
    def __init__(self):
        super().__init__()
        self.is_login_mode = True
        self.init_ui()
        
    def init_ui(self):
        """Initialize UI components"""
        self.setWindowTitle("Chat Application")
        self.setFixedSize(500, 650)
        self.setStyleSheet(LOGIN_STYLE)
        
        # Center window on screen
        from PyQt5.QtWidgets import QDesktopWidget
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(50, 50, 50, 50)
        main_layout.setAlignment(Qt.AlignCenter)
        
        # Login frame
        self.login_frame = QFrame()
        self.login_frame.setObjectName("loginFrame")
        frame_layout = QVBoxLayout()
        frame_layout.setContentsMargins(40, 40, 40, 40)
        frame_layout.setSpacing(20)
        
        # Title
        self.title_label = QLabel("Welcome Back")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.title_label)
        
        # Subtitle
        self.subtitle_label = QLabel("Sign in to continue")
        self.subtitle_label.setObjectName("subtitleLabel")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(self.subtitle_label)
        
        frame_layout.addSpacing(20)
        
        # Username field
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.username_input.setMinimumHeight(45)
        frame_layout.addWidget(self.username_input)
        
        # Email field (hidden in login mode)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email (optional)")
        self.email_input.setMinimumHeight(45)
        self.email_input.hide()
        frame_layout.addWidget(self.email_input)
        
        # Password field
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(45)
        self.password_input.returnPressed.connect(self.handle_submit)
        frame_layout.addWidget(self.password_input)
        
        frame_layout.addSpacing(10)
        
        # Submit button
        self.submit_button = QPushButton("Sign In")
        self.submit_button.setMinimumHeight(50)
        self.submit_button.setCursor(Qt.PointingHandCursor)
        self.submit_button.clicked.connect(self.handle_submit)
        frame_layout.addWidget(self.submit_button)
        
        # Error label
        self.error_label = QLabel()
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")
        self.error_label.hide()
        frame_layout.addWidget(self.error_label)
        
        frame_layout.addSpacing(10)
        
        # Switch mode layout
        switch_layout = QHBoxLayout()
        switch_layout.setAlignment(Qt.AlignCenter)
        
        self.switch_text = QLabel("Don't have an account?")
        self.switch_text.setObjectName("subtitleLabel")
        switch_layout.addWidget(self.switch_text)
        
        self.switch_button = QPushButton("Sign Up")
        self.switch_button.setObjectName("switchButton")
        self.switch_button.setCursor(Qt.PointingHandCursor)
        self.switch_button.clicked.connect(self.toggle_mode)
        switch_layout.addWidget(self.switch_button)
        
        frame_layout.addLayout(switch_layout)
        
        self.login_frame.setLayout(frame_layout)
        main_layout.addWidget(self.login_frame)
        
        self.setLayout(main_layout)
        
        # Setup animations
        self.setup_animations()
        
    def setup_animations(self):
        """Setup fade and slide animations"""
        # Fade in animation
        self.fade_effect = QGraphicsOpacityEffect()
        self.login_frame.setGraphicsEffect(self.fade_effect)
        
        self.fade_animation = QPropertyAnimation(self.fade_effect, b"opacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setStartValue(0)
        self.fade_animation.setEndValue(1)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Start fade in
        self.fade_animation.start()
        
    def toggle_mode(self):
        """Toggle between login and register modes with animation"""
        self.is_login_mode = not self.is_login_mode
        
        # Fade out animation
        fade_out = QPropertyAnimation(self.fade_effect, b"opacity")
        fade_out.setDuration(200)
        fade_out.setStartValue(1)
        fade_out.setEndValue(0)
        fade_out.setEasingCurve(QEasingCurve.InOutQuad)
        fade_out.finished.connect(self.update_mode_ui)
        fade_out.start()
        
        # Store animation to prevent garbage collection
        self._current_animation = fade_out
        
    def update_mode_ui(self):
        """Update UI elements based on current mode"""
        if self.is_login_mode:
            self.title_label.setText("Welcome Back")
            self.subtitle_label.setText("Sign in to continue")
            self.submit_button.setText("Sign In")
            self.switch_text.setText("Don't have an account?")
            self.switch_button.setText("Sign Up")
            self.email_input.hide()
        else:
            self.title_label.setText("Create Account")
            self.subtitle_label.setText("Sign up to get started")
            self.submit_button.setText("Sign Up")
            self.switch_text.setText("Already have an account?")
            self.switch_button.setText("Sign In")
            self.email_input.show()
        
        # Clear inputs
        self.username_input.clear()
        self.password_input.clear()
        self.email_input.clear()
        self.error_label.hide()
        
        # Fade in animation
        fade_in = QPropertyAnimation(self.fade_effect, b"opacity")
        fade_in.setDuration(200)
        fade_in.setStartValue(0)
        fade_in.setEndValue(1)
        fade_in.setEasingCurve(QEasingCurve.InOutQuad)
        fade_in.start()
        
        # Store animation
        self._current_animation = fade_in
        
    def handle_submit(self):
        """Handle login/register submission"""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        # Validation
        if not username or not password:
            self.show_error("Please fill in all fields")
            return
        
        if len(username) < 3:
            self.show_error("Username must be at least 3 characters")
            return
        
        if len(password) < 6:
            self.show_error("Password must be at least 6 characters")
            return
        
        # Prepare data
        data = {
            'username': username,
            'password': password,
            'mode': 'login' if self.is_login_mode else 'register'
        }
        
        if not self.is_login_mode:
            data['email'] = self.email_input.text().strip()
        
        # Disable button during processing
        self.submit_button.setEnabled(False)
        self.submit_button.setText("Processing...")
        
        # Emit signal with data
        self.login_success.emit(data)
        
    def show_error(self, message: str):
        """Show error message with animation"""
        self.error_label.setText(message)
        self.error_label.show()
        
        # Shake animation
        original_pos = self.login_frame.pos()
        shake_anim = QPropertyAnimation(self.login_frame, b"pos")
        shake_anim.setDuration(400)
        shake_anim.setKeyValueAt(0, original_pos)
        shake_anim.setKeyValueAt(0.1, original_pos + QPoint(-10, 0))
        shake_anim.setKeyValueAt(0.3, original_pos + QPoint(10, 0))
        shake_anim.setKeyValueAt(0.5, original_pos + QPoint(-10, 0))
        shake_anim.setKeyValueAt(0.7, original_pos + QPoint(10, 0))
        shake_anim.setKeyValueAt(0.9, original_pos + QPoint(-5, 0))
        shake_anim.setKeyValueAt(1, original_pos)
        shake_anim.start()
        
        # Store animation
        self._shake_animation = shake_anim
        
    def reset_button(self):
        """Reset submit button state"""
        self.submit_button.setEnabled(True)
        self.submit_button.setText("Sign In" if self.is_login_mode else "Sign Up")
