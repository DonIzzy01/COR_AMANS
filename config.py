import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # PostgreSQL connection
    # Replace 'your_password' with your actual PostgreSQL password
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:Postgres123@localhost/cor_amans_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False