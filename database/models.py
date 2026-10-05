"""
Database models for chat application
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """User model"""
    user_id: Optional[int] = None
    username: str = ""
    password_hash: str = ""
    email: Optional[str] = None
    created_at: Optional[str] = None
    last_seen: Optional[str] = None
    is_online: bool = False
    
    def to_dict(self):
        """Convert user to dictionary"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at,
            'last_seen': self.last_seen,
            'is_online': self.is_online
        }


@dataclass
class Message:
    """Message model"""
    message_id: Optional[int] = None
    sender_id: int = 0
    sender_username: str = ""
    room_id: int = 1
    content: str = ""
    message_type: str = "text"  # text, image, file, emoji
    timestamp: Optional[str] = None
    is_encrypted: bool = True
    
    def to_dict(self):
        """Convert message to dictionary"""
        return {
            'message_id': self.message_id,
            'sender_id': self.sender_id,
            'sender_username': self.sender_username,
            'room_id': self.room_id,
            'content': self.content,
            'message_type': self.message_type,
            'timestamp': self.timestamp,
            'is_encrypted': self.is_encrypted
        }


@dataclass
class ChatRoom:
    """Chat room model"""
    room_id: Optional[int] = None
    room_name: str = ""
    description: Optional[str] = None
    created_by: int = 0
    created_at: Optional[str] = None
    is_private: bool = False
    
    def to_dict(self):
        """Convert room to dictionary"""
        return {
            'room_id': self.room_id,
            'room_name': self.room_name,
            'description': self.description,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'is_private': self.is_private
        }


@dataclass
class RoomMembership:
    """Room membership model"""
    membership_id: Optional[int] = None
    user_id: int = 0
    room_id: int = 0
    joined_at: Optional[str] = None
    role: str = "member"  # member, admin, moderator
    
    def to_dict(self):
        """Convert membership to dictionary"""
        return {
            'membership_id': self.membership_id,
            'user_id': self.user_id,
            'room_id': self.room_id,
            'joined_at': self.joined_at,
            'role': self.role
        }
