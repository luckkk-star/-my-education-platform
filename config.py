"""
应用配置文件
包含数据库连接配置和密钥配置
"""
import os


class Config:
    """
    应用配置类
    存储数据库连接信息、密钥等配置项
    """
    # JWT令牌加密密钥，优先使用环境变量，否则使用默认开发密钥
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-development'
    
    # MySQL数据库连接配置
    MYSQL_HOST = 'localhost'  # 数据库主机地址
    MYSQL_USER = 'root'  # 数据库用户名
    MYSQL_PASSWORD = ''  # 数据库密码
    MYSQL_DB = 'homework'  # 数据库名称
    MYSQL_CURSORCLASS = 'DictCursor'  # 游标类型，返回字典格式的结果
