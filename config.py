import os
from datetime import timedelta


class Config:
    # Core
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

    # Database
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL')
        or 'postgresql://postgres:Postgres123@localhost/cor_amans_db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Payment (Paystack)
    PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY')
    PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY')
    COURSE_PRICE_KOBO = 5_000_000  # ₦50,000 in kobo

    # Clerk Authentication Scaffold
    # Set these when you create a Clerk project at https://clerk.com
    CLERK_PUBLISHABLE_KEY = os.environ.get('CLERK_PUBLISHABLE_KEY')
    CLERK_SECRET_KEY = os.environ.get('CLERK_SECRET_KEY')
    CLERK_WEBHOOK_SECRET = os.environ.get('CLERK_WEBHOOK_SECRET')
    # True when Clerk keys are configured
    CLERK_ENABLED = bool(os.environ.get('CLERK_PUBLISHABLE_KEY'))

    # Email (Flask-Mail)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'COR AMANS <noreply@coramans.org>')
    MAIL_ENABLED = bool(os.environ.get('MAIL_USERNAME'))

    # File Uploads
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB

    # Session & Cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    REMEMBER_COOKIE_DURATION = timedelta(days=7)

    # App URL (used in emails)
    APP_URL = os.environ.get('APP_URL', 'http://localhost:5000')
