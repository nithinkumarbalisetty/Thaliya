"""
E-Care Service - Importing from modular structure

This file serves as a compatibility layer for existing imports.
The actual implementation is now modularized in app.services.ecare package.
"""

# Import the refactored ECareService from the ecare module
from app.services.ecare import ECareService

# Re-export for backward compatibility
__all__ = ['ECareService']
