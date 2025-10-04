#!/usr/bin/env python3
"""
Platform Authentication Manager
Handles login/logout for the trading platform
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json

class PlatformAuth:
    """Manages platform-level authentication"""
    
    def __init__(self):
        self.sessions_file = "config/active_sessions.json"
        self.platform_password = os.getenv('PLATFORM_PASSWORD', 'trading123')  # Default for development
        self.session_timeout_hours = 24  # 24-hour session timeout
        self.ensure_sessions_file()
    
    def ensure_sessions_file(self):
        """Ensure sessions file exists"""
        os.makedirs(os.path.dirname(self.sessions_file), exist_ok=True)
        if not os.path.exists(self.sessions_file):
            with open(self.sessions_file, 'w') as f:
                json.dump({}, f)
    
    def hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = "nifty_trading_platform_salt"
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    def verify_password(self, password: str) -> bool:
        """Verify platform password"""
        return self.hash_password(password) == self.hash_password(self.platform_password)
    
    def create_session(self, user_ip: str = "unknown") -> str:
        """Create new session and return session token"""
        session_token = secrets.token_urlsafe(32)
        session_data = {
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=self.session_timeout_hours)).isoformat(),
            'user_ip': user_ip,
            'last_activity': datetime.now().isoformat()
        }
        
        # Load existing sessions
        sessions = self.load_sessions()
        sessions[session_token] = session_data
        
        # Save sessions
        with open(self.sessions_file, 'w') as f:
            json.dump(sessions, f, indent=2)
        
        return session_token
    
    def verify_session(self, session_token: str) -> bool:
        """Verify if session token is valid"""
        if not session_token:
            return False
        
        sessions = self.load_sessions()
        
        if session_token not in sessions:
            return False
        
        session_data = sessions[session_token]
        expires_at = datetime.fromisoformat(session_data['expires_at'])
        
        if datetime.now() > expires_at:
            # Session expired, remove it
            del sessions[session_token]
            with open(self.sessions_file, 'w') as f:
                json.dump(sessions, f, indent=2)
            return False
        
        # Update last activity
        session_data['last_activity'] = datetime.now().isoformat()
        sessions[session_token] = session_data
        
        with open(self.sessions_file, 'w') as f:
            json.dump(sessions, f, indent=2)
        
        return True
    
    def invalidate_session(self, session_token: str) -> bool:
        """Invalidate/logout a session"""
        if not session_token:
            return False
        
        sessions = self.load_sessions()
        
        if session_token in sessions:
            del sessions[session_token]
            with open(self.sessions_file, 'w') as f:
                json.dump(sessions, f, indent=2)
            return True
        
        return False
    
    def load_sessions(self) -> Dict[str, Any]:
        """Load active sessions from file"""
        try:
            with open(self.sessions_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        sessions = self.load_sessions()
        valid_sessions = 0
        
        for session_token, session_data in list(sessions.items()):
            expires_at = datetime.fromisoformat(session_data['expires_at'])
            if datetime.now() <= expires_at:
                valid_sessions += 1
            else:
                # Clean up expired session
                del sessions[session_token]
        
        # Save cleaned sessions
        with open(self.sessions_file, 'w') as f:
            json.dump(sessions, f, indent=2)
        
        return valid_sessions
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        sessions = self.load_sessions()
        cleaned_sessions = {}
        
        for session_token, session_data in sessions.items():
            expires_at = datetime.fromisoformat(session_data['expires_at'])
            if datetime.now() <= expires_at:
                cleaned_sessions[session_token] = session_data
        
        with open(self.sessions_file, 'w') as f:
            json.dump(cleaned_sessions, f, indent=2)

# Global auth manager instance
platform_auth = PlatformAuth()