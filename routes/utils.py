"""
路由工具模块
提供JWT认证装饰器等通用功能
"""
from flask import request, jsonify
import jwt
from functools import wraps
from db.connect import get_db


def token_required(f):
    """
    JWT认证装饰器
    用于保护需要登录才能访问的路由
    
    功能：
    1. 从请求头中提取JWT令牌
    2. 验证令牌的有效性（是否过期、是否被篡改）
    3. 验证用户是否存在于数据库中
    4. 将用户信息传递给被装饰的函数
    
    使用方式：
        @token_required
        def my_route(current_user):
            # current_user 包含用户信息（id, username, role）
            pass
    
    Args:
        f: 被装饰的视图函数
        
    Returns:
        装饰后的函数，如果认证失败返回401错误，成功则调用原函数并传入用户信息
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # 从请求头中提取JWT令牌
        # 格式：Authorization: Bearer <token>
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]

        # 如果没有令牌，返回401未授权错误
        if not token:
            return jsonify({'success': False, 'message': '令牌缺失！'}), 401

        try:
            # 从app导入配置（避免循环导入）
            from app import app
            # 解码并验证JWT令牌
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_data = payload['user']

            # 验证用户是否存在于数据库中（防止用户被删除但令牌仍有效的情况）
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "SELECT id, username, role FROM users WHERE id = %s AND role = %s",
                (current_user_data['id'], current_user_data['role'])
            )
            current_user = cursor.fetchone()
            cursor.close()

            # 如果用户不存在，返回401错误
            if not current_user:
                return jsonify({'success': False, 'message': '令牌无效，用户不存在！'}), 401

        except jwt.ExpiredSignatureError:
            # 令牌已过期
            return jsonify({'success': False, 'message': '令牌已过期！'}), 401
        except jwt.InvalidTokenError:
            # 令牌格式错误或签名无效
            return jsonify({'success': False, 'message': '无效的令牌！'}), 401
        except Exception as e:
            # 其他未知错误
            return jsonify({'success': False, 'message': f'认证失败：{str(e)}'}), 500

        # 认证成功，将用户信息作为第一个参数传递给被装饰的函数
        return f(current_user, *args, **kwargs)

    return decorated
