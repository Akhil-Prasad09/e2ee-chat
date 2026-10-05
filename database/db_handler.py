"""
Database handler for SQLite operations
"""
import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple
from .models import User, Message, ChatRoom, RoomMembership


class DatabaseHandler:
    """Handles all database operations"""
    
    def __init__(self, db_path: str = "chat_app.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP,
                is_online BOOLEAN DEFAULT 0,
                public_bundle TEXT
            )
        ''')
        
        # Chat rooms table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_rooms (
                room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_private BOOLEAN DEFAULT 0,
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_encrypted BOOLEAN DEFAULT 1,
                FOREIGN KEY (sender_id) REFERENCES users(user_id),
                FOREIGN KEY (room_id) REFERENCES chat_rooms(room_id)
            )
        ''')
        
        # Room memberships table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS room_memberships (
                membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                role TEXT DEFAULT 'member',
                UNIQUE(user_id, room_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (room_id) REFERENCES chat_rooms(room_id)
            )
        ''')
        
        # Create default general room
        cursor.execute('''
            INSERT OR IGNORE INTO chat_rooms (room_id, room_name, description, created_by)
            VALUES (1, 'General', 'Default chat room for everyone', NULL)
        ''')
        
        conn.commit()
        conn.close()
    
    # Public keys (E2EE): the server stores and hands out public bundles, never private keys
    def set_public_bundle(self, user_id: int, bundle_json: str):
        conn = self.get_connection()
        conn.execute('UPDATE users SET public_bundle = ? WHERE user_id = ?', (bundle_json, user_id))
        conn.commit()
        conn.close()

    def get_public_bundles(self) -> dict:
        """username -> public bundle JSON, for every registered user"""
        conn = self.get_connection()
        rows = conn.execute('SELECT username, public_bundle FROM users WHERE public_bundle IS NOT NULL').fetchall()
        conn.close()
        return {r['username']: r['public_bundle'] for r in rows}

    # User operations
    def create_user(self, username: str, password_hash: str, email: Optional[str] = None) -> Optional[int]:
        """Create a new user"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)',
                (username, password_hash, email)
            )
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(
                user_id=row['user_id'],
                username=row['username'],
                password_hash=row['password_hash'],
                email=row['email'],
                created_at=row['created_at'],
                last_seen=row['last_seen'],
                is_online=bool(row['is_online'])
            )
        return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(
                user_id=row['user_id'],
                username=row['username'],
                password_hash=row['password_hash'],
                email=row['email'],
                created_at=row['created_at'],
                last_seen=row['last_seen'],
                is_online=bool(row['is_online'])
            )
        return None
    
    def update_user_status(self, user_id: int, is_online: bool):
        """Update user online status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET is_online = ?, last_seen = CURRENT_TIMESTAMP WHERE user_id = ?',
            (is_online, user_id)
        )
        conn.commit()
        conn.close()
    
    def get_online_users(self) -> List[User]:
        """Get all online users"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE is_online = 1')
        rows = cursor.fetchall()
        conn.close()
        
        return [User(
            user_id=row['user_id'],
            username=row['username'],
            email=row['email'],
            is_online=True
        ) for row in rows]
    
    # Message operations
    def save_message(self, message: Message) -> Optional[int]:
        """Save a message to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO messages (sender_id, room_id, content, message_type, is_encrypted)
               VALUES (?, ?, ?, ?, ?)''',
            (message.sender_id, message.room_id, message.content, message.message_type, message.is_encrypted)
        )
        message_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return message_id
    
    def get_room_messages(self, room_id: int, limit: int = 100) -> List[Message]:
        """Get messages from a room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT m.*, u.username as sender_username 
               FROM messages m
               JOIN users u ON m.sender_id = u.user_id
               WHERE m.room_id = ?
               ORDER BY m.message_id DESC
               LIMIT ?''',
            (room_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            messages.append(Message(
                message_id=row['message_id'],
                sender_id=row['sender_id'],
                sender_username=row['sender_username'],
                room_id=row['room_id'],
                content=row['content'],
                message_type=row['message_type'],
                timestamp=row['timestamp'],
                is_encrypted=bool(row['is_encrypted'])
            ))
        
        return list(reversed(messages))  # Return in chronological order
    
    def get_user_messages(self, user_id: int, limit: int = 50) -> List[Message]:
        """Get messages sent by a user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT m.*, u.username as sender_username 
               FROM messages m
               JOIN users u ON m.sender_id = u.user_id
               WHERE m.sender_id = ?
               ORDER BY m.message_id DESC
               LIMIT ?''',
            (user_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [Message(
            message_id=row['message_id'],
            sender_id=row['sender_id'],
            sender_username=row['sender_username'],
            room_id=row['room_id'],
            content=row['content'],
            message_type=row['message_type'],
            timestamp=row['timestamp'],
            is_encrypted=bool(row['is_encrypted'])
        ) for row in rows]
    
    # Room operations
    def create_room(self, room_name: str, created_by: int, description: Optional[str] = None, is_private: bool = False) -> Optional[int]:
        """Create a new chat room"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO chat_rooms (room_name, description, created_by, is_private) VALUES (?, ?, ?, ?)',
                (room_name, description, created_by, is_private)
            )
            room_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return room_id
        except sqlite3.IntegrityError:
            return None
    
    def get_room_by_id(self, room_id: int) -> Optional[ChatRoom]:
        """Get room by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM chat_rooms WHERE room_id = ?', (room_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return ChatRoom(
                room_id=row['room_id'],
                room_name=row['room_name'],
                description=row['description'],
                created_by=row['created_by'],
                created_at=row['created_at'],
                is_private=bool(row['is_private'])
            )
        return None
    
    def get_all_rooms(self) -> List[ChatRoom]:
        """Get all chat rooms"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM chat_rooms ORDER BY room_name')
        rows = cursor.fetchall()
        conn.close()
        
        return [ChatRoom(
            room_id=row['room_id'],
            room_name=row['room_name'],
            description=row['description'],
            created_by=row['created_by'],
            created_at=row['created_at'],
            is_private=bool(row['is_private'])
        ) for row in rows]
    
    def get_user_rooms(self, user_id: int) -> List[ChatRoom]:
        """Get rooms a user is a member of"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT r.* FROM chat_rooms r
               JOIN room_memberships m ON r.room_id = m.room_id
               WHERE m.user_id = ?
               ORDER BY r.room_name''',
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [ChatRoom(
            room_id=row['room_id'],
            room_name=row['room_name'],
            description=row['description'],
            created_by=row['created_by'],
            created_at=row['created_at'],
            is_private=bool(row['is_private'])
        ) for row in rows]
    
    # Room membership operations
    def add_user_to_room(self, user_id: int, room_id: int, role: str = "member") -> bool:
        """Add user to a room"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO room_memberships (user_id, room_id, role) VALUES (?, ?, ?)',
                (user_id, room_id, role)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def remove_user_from_room(self, user_id: int, room_id: int) -> bool:
        """Remove user from a room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM room_memberships WHERE user_id = ? AND room_id = ?',
            (user_id, room_id)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    def get_room_members(self, room_id: int) -> List[User]:
        """Get all members of a room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT u.* FROM users u
               JOIN room_memberships m ON u.user_id = m.user_id
               WHERE m.room_id = ?''',
            (room_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [User(
            user_id=row['user_id'],
            username=row['username'],
            email=row['email'],
            is_online=bool(row['is_online'])
        ) for row in rows]
    
    def is_user_in_room(self, user_id: int, room_id: int) -> bool:
        """Check if user is in a room"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT 1 FROM room_memberships WHERE user_id = ? AND room_id = ?',
            (user_id, room_id)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None
