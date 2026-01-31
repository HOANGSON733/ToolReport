import sys
import json
import os
import socket
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QHBoxLayout, QPushButton, QFormLayout, QMessageBox, QCheckBox
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont
import hashlib


class LoginDialog(QDialog):
    """Dialog đăng nhập/đăng ký"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.users_file = 'users.json'
        self.mode = 'login'  # 'login' hoặc 'register'
        self.logged_in_user = None  # Để lưu username sau khi đăng nhập thành công
        self.init_ui()

    def init_ui(self):
        """Khởi tạo giao diện dialog"""
        self.setWindowTitle("Đăng nhập - Công cụ Tìm kiếm Từ khóa")
        self.setModal(True)
        self.setFixedSize(400, 300)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QLabel("🔐 Đăng nhập vào hệ thống")
        title_label.setFont(QFont('Arial', 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Form layout
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # Username
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nhập tên đăng nhập...")
        self.username_input.setMinimumHeight(35)
        form_layout.addRow("👤 Tên đăng nhập:", self.username_input)

        # Password
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Nhập mật khẩu...")
        self.password_input.setMinimumHeight(35)
        form_layout.addRow("🔑 Mật khẩu:", self.password_input)

        # Remember me checkbox
        self.remember_me_checkbox = QCheckBox("Ghi nhớ đăng nhập")
        self.remember_me_checkbox.setFont(QFont('Arial', 9))
        self.remember_me_checkbox.setMinimumHeight(25)
        form_layout.addRow("", self.remember_me_checkbox)

        # Confirm password (chỉ hiện khi đăng ký)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input.setPlaceholderText("Nhập lại mật khẩu...")
        self.confirm_password_input.setMinimumHeight(35)
        self.confirm_password_label = QLabel("🔒 Xác nhận mật khẩu:")
        form_layout.addRow(self.confirm_password_label, self.confirm_password_input)
        self.confirm_password_label.setVisible(False)
        self.confirm_password_input.setVisible(False)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.login_button = QPushButton("🔓 Đăng nhập")
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.login_button.clicked.connect(self.login)
        button_layout.addWidget(self.login_button)

        self.register_button = QPushButton("📝 Đăng ký")
        self.register_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.register_button.clicked.connect(self.switch_to_register)
        button_layout.addWidget(self.register_button)

        layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; font-size: 10px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

        # Load users
        self.load_users()

    def load_users(self):
        """Tải danh sách người dùng"""
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
            except:
                self.users = {}
        else:
            self.users = {}

    def save_users(self):
        """Lưu danh sách người dùng"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể lưu thông tin người dùng: {str(e)}")

    def hash_password(self, password):
        """Hash mật khẩu"""
        return hashlib.sha256(password.encode()).hexdigest()

    def switch_to_register(self):
        """Chuyển sang chế độ đăng ký"""
        if self.mode == 'login':
            self.mode = 'register'
            self.setWindowTitle("Đăng ký - Công cụ Tìm kiếm Từ khóa")
            self.login_button.setText("📝 Tạo tài khoản")
            self.register_button.setText("🔙 Quay lại đăng nhập")
            self.confirm_password_label.setVisible(True)
            self.confirm_password_input.setVisible(True)
            self.status_label.setText("Chế độ đăng ký - Tạo tài khoản mới")
        else:
            self.mode = 'login'
            self.setWindowTitle("Đăng nhập - Công cụ Tìm kiếm Từ khóa")
            self.login_button.setText("🔓 Đăng nhập")
            self.register_button.setText("📝 Đăng ký")
            self.confirm_password_label.setVisible(False)
            self.confirm_password_input.setVisible(False)
            self.status_label.setText("")

    def login(self):
        """Xử lý đăng nhập hoặc đăng ký"""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self.status_label.setText("❌ Vui lòng nhập đầy đủ thông tin!")
            self.status_label.setStyleSheet("color: #f44336; font-size: 10px;")
            return

        if self.mode == 'login':
            # Đăng nhập
            if username in self.users and self.users[username] == self.hash_password(password):
                self.logged_in_user = username  # Lưu username đã đăng nhập
                self.status_label.setText("✅ Đăng nhập thành công!")
                self.status_label.setStyleSheet("color: #4CAF50; font-size: 10px;")
                # Lưu thông tin đăng nhập nếu chọn "Ghi nhớ đăng nhập"
                if self.remember_me_checkbox.isChecked():
                    self.save_remember_me_session(username)
                QTimer.singleShot(1000, self.accept)  # Đóng dialog sau 1 giây
            else:
                self.status_label.setText("❌ Sai tên đăng nhập hoặc mật khẩu!")
                self.status_label.setStyleSheet("color: #f44336; font-size: 10px;")
        else:
            # Đăng ký
            confirm_password = self.confirm_password_input.text()

            if password != confirm_password:
                self.status_label.setText("❌ Mật khẩu xác nhận không khớp!")
                self.status_label.setStyleSheet("color: #f44336; font-size: 10px;")
                return

            if username in self.users:
                self.status_label.setText("❌ Tên đăng nhập đã tồn tại!")
                self.status_label.setStyleSheet("color: #f44336; font-size: 10px;")
                return

            # Tạo tài khoản mới
            self.users[username] = self.hash_password(password)
            self.save_users()
            self.logged_in_user = username  # Lưu username đã đăng ký
            self.status_label.setText("✅ Đăng ký thành công! Đang vào công cụ...")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 10px;")
            QTimer.singleShot(1500, self.accept)  # Vào công cụ sau 1.5 giây

    def save_remember_me_session(self, username):
        """Lưu phiên đăng nhập để ghi nhớ"""
        from datetime import datetime
        session_data = {
            'username': username,
            'timestamp': datetime.now().isoformat()  # Lưu thời gian đăng nhập
        }
        try:
            with open('session.json', 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Lỗi khi lưu phiên đăng nhập: {str(e)}")

    def load_remember_me_session(self):
        """Tải phiên đăng nhập đã lưu"""
        session_file = 'session.json'
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                return session_data.get('username')
            except:
                return None
        return None

    def clear_remember_me_session(self):
        """Xóa phiên đăng nhập đã lưu"""
        session_file = 'session.json'
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except:
                pass
