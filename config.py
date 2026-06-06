import os
import secrets

class Config:
    # Fix #11: Use a strong random key if SECRET_KEY env var is not set.
    # WARNING: Set SECRET_KEY environment variable in production!
    _default_key = os.environ.get('SECRET_KEY')
    if not _default_key:
        # Generate a random key for development — sessions reset on restart
        import warnings
        warnings.warn(
            "[SECURITY] SECRET_KEY not set in environment. Using a random key. "
            "Set SECRET_KEY env variable in production to keep sessions persistent.",
            stacklevel=2
        )
    SECRET_KEY = _default_key or secrets.token_hex(32)
    
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
    DB_NAME = os.environ.get('DB_NAME', 'red_studio_billing')
    # Default warning threshold for stock levels
    LOW_STOCK_THRESHOLD = 10
