"""
用户认证路由模块
处理用户注册、登录、令牌刷新等认证相关功能
"""
from flask import Blueprint, jsonify, request
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from db.connect import get_db

# 创建认证蓝图
auth_bp = Blueprint('auth', __name__)


# ==================== 工具函数 ====================
def generate_token(user):
    """
    生成JWT令牌
    
    功能：
    1. 创建包含用户信息的JWT载荷
    2. 设置令牌有效期（1天）
    3. 使用密钥签名生成令牌
    
    Args:
        user: 用户信息字典，包含id、username、role
        
    Returns:
        str: JWT令牌字符串
    """
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),  # 有效期1天
        'iat': datetime.datetime.utcnow(),  # 签发时间
        'user': {
            'id': user['id'],
            'username': user['username'],
            'role': user['role']
        }
    }
    from app import app  # 避免循环导入
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    return token


# ==================== 用户认证路由 ====================
@auth_bp.route('/register', methods=['POST'])
def register():
    """
    用户注册接口
    
    功能：
    1. 验证注册信息的完整性和合法性
    2. 检查用户名、邮箱、身份ID是否已存在
    3. 对密码进行哈希加密
    4. 创建新用户并生成JWT令牌
    
    请求体：
        {
            "username": "用户名",
            "email": "邮箱",
            "password": "密码",
            "role": "student" 或 "teacher",
            "student_id": "学号" (学生必填),
            "teacher_id": "教师编号" (教师必填)
        }
        
    Returns:
        JSON: 注册结果，包含token和用户信息
    """
    data = request.get_json()

    # 验证必要字段是否都存在
    required_fields = ['username', 'email', 'password', 'role']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'message': f'缺少必要字段: {field}'}), 400

    # 验证角色必须是student或teacher
    if data['role'] not in ['student', 'teacher']:
        return jsonify({'success': False, 'message': '角色必须是student或teacher'}), 400

    # 根据角色验证身份ID
    if data['role'] == 'student' and 'student_id' not in data:
        return jsonify({'success': False, 'message': '学生必须提供学号'}), 400
    if data['role'] == 'teacher' and 'teacher_id' not in data:
        return jsonify({'success': False, 'message': '教师必须提供教师编号'}), 400

    db = get_db()
    cursor = db.cursor()

    try:
        # 检查用户名是否已被使用
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (data['username'],)
        )
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '用户名已存在'}), 400

        # 检查邮箱是否已被注册
        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (data['email'],)
        )
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '邮箱已被注册'}), 400

        # 检查身份ID（学号或教师编号）是否已被使用
        id_field = 'student_id' if data['role'] == 'student' else 'teacher_id'
        cursor.execute(
            f"SELECT id FROM users WHERE {id_field} = %s",
            (data[data['role'] + '_id'],)
        )
        if cursor.fetchone():
            return jsonify({'success': False, 'message': f'{id_field}已被使用'}), 400

        # 对密码进行哈希加密（使用werkzeug的安全哈希函数）
        hashed_password = generate_password_hash(data['password'])
        
        # 插入新用户到数据库
        cursor.execute(
            f"""INSERT INTO users 
                (username, email, password, role, {id_field}, created_at) 
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)""",
            (data['username'], data['email'], hashed_password, data['role'],
             data[data['role'] + '_id'])
        )
        db.commit()

        # 获取新创建的用户信息（不包含密码）
        user_id = cursor.lastrowid
        cursor.execute("SELECT id, username, email, role FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        # 生成JWT令牌，用户注册后自动登录
        token = generate_token(user)

        return jsonify({
            'success': True,
            'message': '注册成功',
            'token': token,
            'user': user
        }), 201

    except Exception as e:
        # 发生错误时回滚事务
        db.rollback()
        return jsonify({'success': False, 'message': f'注册失败: {str(e)}'}), 500
    finally:
        cursor.close()


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录接口
    
    功能：
    1. 验证用户名、密码和角色
    2. 检查密码是否正确（使用哈希比较）
    3. 生成JWT令牌
    
    请求体：
        {
            "username": "用户名",
            "password": "密码",
            "role": "student" 或 "teacher"
        }
        
    Returns:
        JSON: 登录结果，包含token和用户信息
    """
    data = request.get_json()

    # 验证必要字段
    if not all(k in data for k in ['username', 'password', 'role']):
        return jsonify({'success': False, 'message': '缺少必要字段'}), 400

    db = get_db()
    cursor = db.cursor()

    try:
        # 根据用户名和角色查询用户（角色用于区分同名但不同角色的用户）
        cursor.execute(
            "SELECT id, username, password, role FROM users WHERE username = %s AND role = %s",
            (data['username'], data['role'])
        )
        user = cursor.fetchone()

        # 验证用户存在且密码正确
        # check_password_hash用于比较明文密码和哈希密码
        if not user or not check_password_hash(user['password'], data['password']):
            return jsonify({'success': False, 'message': '用户名、密码或角色不正确'}), 401

        # 生成JWT令牌
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


@auth_bp.route('/refresh-token', methods=['POST', 'GET'])
def refresh_token():
    """
    刷新JWT令牌接口
    
    功能：
    1. 验证旧令牌的有效性（即使已过期也允许刷新）
    2. 验证用户是否仍然存在
    3. 生成新的令牌（延长有效期）
    
    使用场景：
    - 前端定期刷新令牌，避免用户频繁登录
    - 令牌即将过期时自动刷新
    
    Returns:
        JSON: 新的JWT令牌
    """
    token = None
    # 从请求头提取令牌
    if 'Authorization' in request.headers:
        token = request.headers['Authorization'].split(" ")[1]

    if not token:
        return jsonify({'success': False, 'message': '令牌缺失'}), 401

    try:
        from app import app  # 避免循环导入
        # 解码令牌，但不验证过期时间（verify_exp=False），允许过期令牌刷新
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"], options={"verify_exp": False})
        user_data = payload['user']

        # 验证用户是否仍然存在于数据库中
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

        # 生成新的令牌（重新设置有效期）
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


@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    """
    获取当前登录用户信息接口
    
    功能：
    1. 从JWT令牌中提取用户ID
    2. 从数据库查询用户的详细信息
    3. 返回用户信息（不包含密码）
    
    使用场景：
    - 前端获取当前登录用户的详细信息
    - 验证用户登录状态
    
    Returns:
        JSON: 用户详细信息
    """
    token = None
    # 从请求头提取令牌
    if 'Authorization' in request.headers:
        token = request.headers['Authorization'].split(" ")[1]

    if not token:
        return jsonify({'success': False, 'message': '令牌缺失'}), 401

    try:
        from app import app
        # 解码并验证令牌（验证过期时间）
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        user_data = payload['user']

        # 从数据库查询用户详细信息
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

        # 移除敏感信息（密码），确保不会泄露
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
