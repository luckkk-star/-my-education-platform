"""
数据库连接模块
提供数据库连接的获取、关闭和初始化功能
使用Flask的g对象实现请求级别的数据库连接管理
"""
import pymysql
from pymysql.cursors import DictCursor
from flask import g
from config import Config


def get_db():
    """
    获取数据库连接
    
    功能：
    1. 检查当前请求是否已有数据库连接（使用Flask的g对象）
    2. 如果没有，创建新的数据库连接
    3. 使用DictCursor返回字典格式的结果，便于使用
    
    说明：
    - 使用Flask的g对象存储请求级别的数据
    - 同一个请求中多次调用get_db()会返回同一个连接
    - 不同请求之间使用不同的连接，保证线程安全
    
    Returns:
        pymysql.connections.Connection: 数据库连接对象
    """
    # 检查g对象中是否已有数据库连接
    if 'db' not in g:
        # 创建新的数据库连接
        g.db = pymysql.connect(
            host=Config.MYSQL_HOST,  # 数据库主机
            user=Config.MYSQL_USER,  # 数据库用户名
            password=Config.MYSQL_PASSWORD,  # 数据库密码
            db=Config.MYSQL_DB,  # 数据库名称
            cursorclass=DictCursor  # 使用字典游标，返回字典格式的结果
        )
    return g.db


def close_db(e=None):
    """
    关闭数据库连接
    
    功能：
    1. 从g对象中获取数据库连接
    2. 如果连接存在，关闭它
    3. 清理g对象中的连接
    
    说明：
    - 这个函数会在请求结束时自动调用（通过teardown_appcontext注册）
    - 参数e是异常对象（如果有），Flask会自动传入
    
    Args:
        e: 异常对象（可选），Flask自动传入
    """
    # 从g对象中移除并获取数据库连接
    db = g.pop('db', None)
    # 如果连接存在，关闭它
    if db is not None:
        db.close()


def init_app(app):
    """
    初始化应用，注册数据库清理函数
    
    功能：
    1. 将close_db函数注册为应用上下文清理函数
    2. 确保每个请求结束后自动关闭数据库连接
    
    说明：
    - teardown_appcontext会在请求结束时自动调用注册的函数
    - 这样可以确保数据库连接被正确关闭，避免连接泄漏
    
    Args:
        app: Flask应用实例
    """
    # 注册清理函数，请求结束时自动调用close_db
    app.teardown_appcontext(close_db)
