import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DB_HOST = 'localhost'
    DB_PORT = 3306
    DB_USER = 'root'
    DB_PASSWORD = 'Admin&123'
    DB_NAME = 'complaint_db'
    SECRET_KEY = 'my_flask_secret_key_123'
