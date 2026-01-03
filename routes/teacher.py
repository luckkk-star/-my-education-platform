"""
教师功能路由模块
处理教师相关的所有功能：创建班级、管理学生、发布作业、批改作业等
"""
from flask import Blueprint, jsonify, request
from db.connect import get_db
from datetime import datetime
import random
import string
from .utils import token_required

# 创建教师功能蓝图
teacher_bp = Blueprint('teacher', __name__)


# ==================== 工具函数 ====================
def generate_class_code():
    """
    生成6位随机班级代码
    
    功能：
    1. 生成包含大写字母和数字的6位随机字符串
    2. 用于学生加入班级时的唯一标识
    
    Returns:
        str: 6位随机班级代码（例如：ABC123）
    """
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ==================== 班级管理路由 ====================
@teacher_bp.route('/classes', methods=['POST'])
@token_required
def create_class(current_user):
    """
    创建新班级接口
    
    功能：
    1. 验证教师身份
    2. 生成唯一的6位班级代码
    3. 创建班级记录
    4. 返回班级信息（包含班级代码）
    
    请求体：
        {
            "name": "班级名称",
            "description": "班级描述（可选）"
        }
        
    Returns:
        JSON: 创建的班级信息，包含班级代码
    """
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    data = request.get_json()
    db = get_db()
    cursor = db.cursor()

    try:
        # 生成唯一的班级代码
        code = generate_class_code()
        # 确保代码唯一
        while True:
            cursor.execute("SELECT id FROM classes WHERE code = %s", (code,))
            if not cursor.fetchone():
                break
            code = generate_class_code()

        cursor.execute(
            "INSERT INTO classes (name, code, teacher_id, description) VALUES (%s, %s, %s, %s)",
            (data.get('name'), code, current_user['id'], data.get('description', ''))
        )
        class_id = cursor.lastrowid
        db.commit()

        # 返回创建的班级信息
        cursor.execute("SELECT * FROM classes WHERE id = %s", (class_id,))
        class_info = cursor.fetchone()
        cursor.close()

        return jsonify({
            'success': True,
            'message': '班级创建成功',
            'class': class_info
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()


@teacher_bp.route('/classes', methods=['GET'])
@token_required
def get_teacher_classes(current_user):
    """
    获取教师创建的所有班级列表
    
    功能：
    1. 查询当前教师创建的所有班级
    2. 统计每个班级的学生人数
    3. 按创建时间倒序排列
    
    Returns:
        JSON: 班级列表，包含学生人数统计
    """
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """SELECT c.*, COUNT(sc.student_id) as student_count 
           FROM classes c 
           LEFT JOIN student_classes sc ON c.id = sc.class_id 
           WHERE c.teacher_id = %s 
           GROUP BY c.id 
           ORDER BY c.created_at DESC""",
        (current_user['id'],)
    )
    classes = cursor.fetchall()
    cursor.close()

    return jsonify(classes)


@teacher_bp.route('/classes/<int:class_id>/students', methods=['GET'])
@token_required
def get_class_students(current_user, class_id):
    """
    获取班级的学生列表
    
    功能：
    1. 验证班级是否属于当前教师
    2. 查询班级中的所有学生
    3. 返回学生信息（姓名、学号、邮箱、加入时间等）
    
    Args:
        class_id: 班级ID
        
    Returns:
        JSON: 学生列表
    """
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    # 验证班级是否属于该教师
    cursor.execute(
        "SELECT id FROM classes WHERE id = %s AND teacher_id = %s",
        (class_id, current_user['id'])
    )
    if not cursor.fetchone():
        cursor.close()
        return jsonify({'message': '班级不存在或无权访问'}), 404

    # 获取班级学生列表
    cursor.execute(
        """SELECT u.id, u.username, u.email, u.student_id, sc.joined_at 
           FROM student_classes sc 
           JOIN users u ON sc.student_id = u.id 
           WHERE sc.class_id = %s 
           ORDER BY sc.joined_at DESC""",
        (class_id,)
    )
    students = cursor.fetchall()
    cursor.close()

    return jsonify(students)


@teacher_bp.route('/classes/<int:class_id>/students/<int:student_id>', methods=['DELETE'])
@token_required
def remove_student_from_class(current_user, class_id, student_id):
    """
    从班级中移除学生接口
    
    功能：
    1. 验证班级是否属于当前教师
    2. 验证学生是否在该班级中
    3. 删除该学生在该班级的所有作业提交记录
    4. 删除学生与班级的关联关系
    
    Args:
        class_id: 班级ID
        student_id: 学生ID
        
    Returns:
        JSON: 移除结果
    """
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    try:
        # 验证班级是否属于该教师
        cursor.execute(
            "SELECT id FROM classes WHERE id = %s AND teacher_id = %s",
            (class_id, current_user['id'])
        )
        if not cursor.fetchone():
            cursor.close()
            return jsonify({'success': False, 'message': '班级不存在或无权访问'}), 404

        # 验证学生是否在该班级中
        cursor.execute(
            "SELECT id FROM student_classes WHERE class_id = %s AND student_id = %s",
            (class_id, student_id)
        )
        if not cursor.fetchone():
            cursor.close()
            return jsonify({'success': False, 'message': '该学生不在该班级中'}), 404

        # 删除该学生在该班级的所有作业提交记录
        # 通过JOIN找到该班级的所有作业，然后删除该学生对这些作业的提交
        cursor.execute(
            """DELETE s FROM submissions s
               INNER JOIN assignments a ON s.assignment_id = a.id
               WHERE s.student_id = %s AND a.class_id = %s""",
            (student_id, class_id)
        )
        deleted_submissions = cursor.rowcount

        # 删除学生与班级的关联
        cursor.execute(
            "DELETE FROM student_classes WHERE class_id = %s AND student_id = %s",
            (class_id, student_id)
        )
        db.commit()
        cursor.close()

        message = '学生已从班级中移除'

        return jsonify({
            'success': True,
            'message': message
        }), 200

    except Exception as e:
        db.rollback()
        cursor.close()
        return jsonify({'success': False, 'message': f'移除失败：{str(e)}'}), 500


@teacher_bp.route('/classes/<int:class_id>', methods=['DELETE'])
@token_required
def delete_class(current_user, class_id):
    """
    解散班级接口
    
    功能：
    1. 验证班级是否属于当前教师
    2. 删除班级（由于外键约束，会自动删除相关的学生关联和作业）
    3. 警告：此操作不可恢复
    
    Args:
        class_id: 班级ID
        
    Returns:
        JSON: 解散结果
    """
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    try:
        # 验证班级是否属于该教师
        cursor.execute(
            "SELECT id, name FROM classes WHERE id = %s AND teacher_id = %s",
            (class_id, current_user['id'])
        )
        class_info = cursor.fetchone()
        if not class_info:
            cursor.close()
            return jsonify({'success': False, 'message': '班级不存在或无权访问'}), 404

        # 删除班级（由于外键约束，会自动删除相关的学生关联和作业）
        cursor.execute(
            "DELETE FROM classes WHERE id = %s",
            (class_id,)
        )
        db.commit()
        cursor.close()

        return jsonify({
            'success': True,
            'message': f'班级"{class_info["name"]}"已解散'
        }), 200

    except Exception as e:
        db.rollback()
        cursor.close()
        return jsonify({'success': False, 'message': f'解散失败：{str(e)}'}), 500


# ==================== 作业管理路由 ====================
@teacher_bp.route('/assignments', methods=['POST'])
@token_required
def create_assignment(current_user):
    """
    发布新作业接口
    
    功能：
    1. 验证教师身份
    2. 验证班级是否属于当前教师
    3. 创建作业记录
    4. 设置作业标题、描述、截止时间等
    
    请求体：
        {
            "title": "作业标题",
            "description": "作业描述",
            "class_id": 班级ID,
            "deadline": "截止时间（ISO格式）"
        }
        
    Returns:
        JSON: 创建结果
    """
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    data = request.get_json()
    db = get_db()
    cursor = db.cursor()

    try:
        # 验证class_id是否存在且属于该教师
        class_id = data.get('class_id')
        if class_id:
            cursor.execute(
                "SELECT id FROM classes WHERE id = %s AND teacher_id = %s",
                (class_id, current_user['id'])
            )
            if not cursor.fetchone():
                return jsonify({'success': False, 'message': '班级不存在或无权访问'}), 404

        cursor.execute(
            "INSERT INTO assignments (title, description, teacher_id, class_id, deadline) VALUES (%s, %s, %s, %s, %s)",
            (data['title'], data['description'], current_user['id'], class_id, data['deadline'])
        )
        db.commit()
        return jsonify({'success': True, 'message': '作业发布成功'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()


@teacher_bp.route('/assignments', methods=['GET'])
@token_required
def get_teacher_assignments(current_user):
    """
    获取教师发布的所有作业列表
    
    功能：
    1. 查询当前教师发布的所有作业
    2. 按创建时间倒序排列（最新的在前）
    
    Returns:
        JSON: 作业列表
    """
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM assignments WHERE teacher_id = %s ORDER BY created_at DESC",
        (current_user['id'],)
    )
    assignments = cursor.fetchall()
    cursor.close()

    return jsonify(assignments)


@teacher_bp.route('/assignments/<int:assignment_id>', methods=['DELETE'])
@token_required
def delete_assignment(current_user, assignment_id):
    """
    删除作业接口
    
    功能：
    1. 验证作业是否属于当前教师
    2. 删除该作业的所有学生提交记录
    3. 删除作业本身
    4. 警告：此操作不可恢复
    
    Args:
        assignment_id: 作业ID
        
    Returns:
        JSON: 删除结果
    """
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    try:
        # 验证作业是否存在且属于当前教师
        cursor.execute(
            "SELECT id FROM assignments WHERE id = %s AND teacher_id = %s",
            (assignment_id, current_user['id'])
        )
        if not cursor.fetchone():
            return jsonify({'message': '作业不存在或无权限删除'}), 404

        # 先删除关联的提交记录
        cursor.execute(
            "DELETE FROM submissions WHERE assignment_id = %s",
            (assignment_id,)
        )

        # 再删除作业本身
        cursor.execute(
            "DELETE FROM assignments WHERE id = %s",
            (assignment_id,)
        )
        db.commit()
        return jsonify({'message': '作业已删除'}), 200

    except Exception as e:
        db.rollback()
        return jsonify({'message': f'删除失败：{str(e)}'}), 500
    finally:
        cursor.close()


# ==================== 批改相关路由 ====================
@teacher_bp.route('/assignments/<int:assignment_id>/submissions', methods=['GET'])
@token_required
def get_submissions(current_user, assignment_id):
    """
    获取作业的提交情况接口
    
    功能：
    1. 验证作业是否属于当前教师
    2. 查询该作业的所有学生提交
    3. 统计提交情况（总人数、已提交、未提交）
    4. 计算成绩统计（平均分、最高分、最低分、已批改数）
    
    Args:
        assignment_id: 作业ID
        
    Returns:
        JSON: 提交列表和统计信息
    """
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    # 验证作业是否属于该教师，并获取作业的class_id
    cursor.execute(
        "SELECT id, class_id FROM assignments WHERE id = %s AND teacher_id = %s",
        (assignment_id, current_user['id'])
    )
    assignment = cursor.fetchone()
    if not assignment:
        cursor.close()
        return jsonify({'message': '作业不存在或无权访问'}), 404

    class_id = assignment['class_id']

    # 获取提交情况
    cursor.execute(
        """SELECT s.*, u.username FROM submissions s
           JOIN users u ON s.student_id = u.id
           WHERE s.assignment_id = %s""",
        (assignment_id,)
    )
    submissions = cursor.fetchall()

    # 获取班级总人数和已提交人数
    total_students = 0
    submitted_count = len(submissions)
    
    if class_id:
        # 获取班级总人数
        cursor.execute(
            "SELECT COUNT(*) as count FROM student_classes WHERE class_id = %s",
            (class_id,)
        )
        result = cursor.fetchone()
        total_students = result['count'] if result else 0

    # 计算成绩统计（只统计已批改的作业，score不为NULL）
    scores = [s['score'] for s in submissions if s.get('score') is not None]
    
    score_statistics = {
        'average_score': None,
        'max_score': None,
        'min_score': None,
        'graded_count': len(scores)
    }
    
    if scores:
        score_statistics['average_score'] = round(sum(scores) / len(scores), 2)
        score_statistics['max_score'] = max(scores)
        score_statistics['min_score'] = min(scores)

    cursor.close()

    # 返回提交列表和统计信息
    return jsonify({
        'submissions': submissions,
        'statistics': {
            'total_students': total_students,
            'submitted_count': submitted_count,
            'not_submitted_count': total_students - submitted_count,
            'score_statistics': score_statistics
        }
    })


@teacher_bp.route('/submissions/<int:submission_id>/grade', methods=['POST'])
@token_required
def grade_submission(current_user, submission_id):
    """
    批改作业接口
    
    功能：
    1. 验证教师身份
    2. 更新提交记录的成绩和评语
    3. 记录批改时间
    
    请求体：
        {
            "score": 分数（0-100）,
            "feedback": "评语"
        }
        
    Args:
        submission_id: 提交记录ID
        
    Returns:
        JSON: 批改结果
    """
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    data = request.get_json()
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            """UPDATE submissions SET score = %s, feedback = %s, graded_at = %s
               WHERE id = %s""",
            (data['score'], data['feedback'], datetime.now(), submission_id)
        )
        db.commit()
        return jsonify({'success': True, 'message': '作业批改完成'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
