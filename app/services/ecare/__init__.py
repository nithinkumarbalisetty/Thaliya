"""
E-Care service modules for healthcare chat functionality
"""

from .ecare_service import ECareService
from .session_manager import ECareSessionManager
from .auth.core_handler import ECareAuthHandler  # Updated to use modular auth system
from .chat_handler import ECareChatHandler
from .user_manager import ECareUserManager
from .parsers import ECareDataParsers

__all__ = [
    'ECareService',
    'ECareSessionManager', 
    'ECareAuthHandler',
    'ECareChatHandler',
    'ECareUserManager',
    'ECareDataParsers'
]
