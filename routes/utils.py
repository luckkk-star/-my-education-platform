from flask import request, jsonify, g
import jwt
from functools import wraps
from db.connect import get_db


# JWT认证装饰器
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # 从请求头获取令牌
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({'success': False, 'message': '令牌缺失！'}), 401

        try:
            # 从app导入配置（避免循环导入，实际项目可优化为全局配置）
            from app import app
            # 解码令牌
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_data = payload['user']

            # 验证用户是否存在于数据库
            db = get_db()
            cursor = db.cursor()
            cursor.execute(
                "SELECT id, username, role FROM users WHERE id = %s AND role = %s",
                (current_user_data['id'], current_user_data['role'])
            )
            current_user = cursor.fetchone()
            cursor.close()

            if not current_user:
                return jsonify({'success': False, 'message': '令牌无效，用户不存在！'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': '令牌已过期！'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'message': '无效的令牌！'}), 401
        except Exception as e:
            return jsonify({'success': False, 'message': f'认证失败：{str(e)}'}), 500

        # 将当前用户信息传入视图函数
        return f(current_user, *args, **kwargs)

    return decorated