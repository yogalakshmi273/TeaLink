import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'tlink_super_secret_key_1337')
    # Default to SQLite, easily configured via DATABASE_URL environment variable for MySQL/PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///tlink.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload limits and folders
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'uploads')
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
