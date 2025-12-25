import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-development'
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = '520413LDld'
    MYSQL_DB = 'homework'
    MYSQL_CURSORCLASS = 'DictCursor'