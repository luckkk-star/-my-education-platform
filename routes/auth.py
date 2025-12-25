from flask import Blueprint, jsonify, request, g
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from db.connect import get_db
from functools import wraps

auth_bp = Blueprint('auth', __name__)


# 生成JWT令牌
def generate_token(user):
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),  # 有效期1天
        'iat': datetime.datetime.utcnow(),
        'user': {
            'id': user['id'],
            'username': user['username'],
            'role': user['role']
        }
    }
    from app import app  # 避免循环导入
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    return token


# 用户注册
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    # 验证必要字段
    required_fields = ['username', 'email', 'password', 'role']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'message': f'缺少必要字段: {field}'}), 400

    # 验证角色合法性
    if data['role'] not in ['student', 'teacher']:
        return jsonify({'success': False, 'message': '角色必须是student或teacher'}), 400

    # 验证身份ID
    if data['role'] == 'student' and 'student_id' not in data:
        return jsonify({'success': False, 'message': '学生必须提供学号'}), 400
    if data['role'] == 'teacher' and 'teacher_id' not in data:
        return jsonify({'success': False, 'message': '教师必须提供教师编号'}), 400

    db = get_db()
    cursor = db.cursor()

    try:
        # 检查用户名是否已存在
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (data['username'],)
        )
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '用户名已存在'}), 400

        # 检查邮箱是否已存在
        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (data['email'],)
        )
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '邮箱已被注册'}), 400

        # 检查身份ID是否已存在
        id_field = 'student_id' if data['role'] == 'student' else 'teacher_id'
        cursor.execute(
            f"SELECT id FROM users WHERE {id_field} = %s",
            (data[data['role'] + '_id'],)
        )
        if cursor.fetchone():
            return jsonify({'success': False, 'message': f'{id_field}已被使用'}), 400

        # 插入新用户
        hashed_password = generate_password_hash(data['password'])
        cursor.execute(
            f"""INSERT INTO users 
                (username, email, password, role, {id_field}, created_at) 
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)""",
            (data['username'], data['email'], hashed_password, data['role'],
             data[data['role'] + '_id'])
        )
        db.commit()

        # 获取新创建的用户信息
        user_id = cursor.lastrowid
        cursor.execute("SELECT id, username, email, role FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        # 生成令牌
        token = generate_token(user)

        return jsonify({
            'success': True,
            'message': '注册成功',
            'token': token,
            'user': user
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'注册失败: {str(e)}'}), 500
    finally:
        cursor.close()


# 用户登录
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    # 验证必要字段
    if not all(k in data for k in ['username', 'password', 'role']):
        return jsonify({'success': False, 'message': '缺少必要字段'}), 400

    db = get_db()
    cursor = db.cursor()

    try:
        # 查询用户
        cursor.execute(
            "SELECT id, username, password, role FROM users WHERE username = %s AND role = %s",
            (data['username'], data['role'])
        )
        user = cursor.fetchone()

        # 验证用户存在且密码正确
        if not user or not check_password_hash(user['password'], data['password']):
            return jsonify({'success': False, 'message': '用户名、密码或角色不正确'}), 401

        # 生成令牌
        token = generate_token(user)

        return jsonify({
            'success': True,
            'message': '登录成功',
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role']
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'登录失败: {str(e)}'}), 500
    finally:
        cursor.close()


# 刷新令牌
@auth_bp.route('/refresh-token', methods=['POST','GET'])
def refresh_token():
    token = None
    if 'Authorization' in request.headers:
        token = request.headers['Authorization'].split(" ")[1]

    if not token:
        return jsonify({'success': False, 'message': '令牌缺失'}), 401

    try:
        from app import app  # 避免循环导入
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"], options={"verify_exp": False})
        user_data = payload['user']

        # 验证用户是否存在
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, username, role FROM users WHERE id = %s AND username = %s AND role = %s",
            (user_data['id'], user_data['username'], user_data['role'])
        )
        user = cursor.fetchone()
        cursor.close()

        if not user:
            return jsonify({'success': False, 'message': '用户不存在'}), 401

        # 生成新令牌
        new_token = generate_token(user)
        return jsonify({
            'success': True,
            'token': new_token
        })

    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'message': '令牌已过期'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'message': '无效的令牌'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': f'刷新令牌失败: {str(e)}'}), 500


# 获取当前用户信息
@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    token = None
    if 'Authorization' in request.headers:
        token = request.headers['Authorization'].split(" ")[1]

    if not token:
        return jsonify({'success': False, 'message': '令牌缺失'}), 401

    try:
        from app import app
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        user_data = payload['user']

        # 查询用户详细信息
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, username, email, role, student_id, teacher_id FROM users WHERE id = %s",
            (user_data['id'],)
        )
        user = cursor.fetchone()
        cursor.close()

        if not user:
            return jsonify({'success': False, 'message': '用户不存在'}), 401

        # 移除敏感信息
        user.pop('password', None)
        return jsonify({
            'success': True,
            'user': user
        })

    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'message': '令牌已过期'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'message': '无效的令牌'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取用户信息失败: {str(e)}'}), 500