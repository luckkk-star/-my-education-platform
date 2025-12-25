from flask import Blueprint, jsonify, request
from db.connect import get_db
from datetime import datetime
from .utils import token_required  # 从utils导入装饰器

teacher_bp = Blueprint('teacher', __name__)


# 发布作业
@teacher_bp.route('/assignments', methods=['POST'])
@token_required
def create_assignment(current_user):
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    data = request.get_json()
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            "INSERT INTO assignments (title, description, teacher_id, deadline) VALUES (%s, %s, %s, %s)",
            (data['title'], data['description'], current_user['id'], data['deadline'])
        )
        db.commit()
        return jsonify({'success': True, 'message': '作业发布成功'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()



#删除作业
@teacher_bp.route('/assignments/<int:assignment_id>', methods=['DELETE'])
@token_required
def delete_assignment(current_user, assignment_id):
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

        # 先删除关联的提交记录（如果需要保留提交记录可跳过此步）
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


# 获取教师发布的所有作业
@teacher_bp.route('/assignments', methods=['GET'])
@token_required
def get_teacher_assignments(current_user):
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


# 获取作业提交情况
@teacher_bp.route('/assignments/<int:assignment_id>/submissions', methods=['GET'])
@token_required
def get_submissions(current_user, assignment_id):
    if current_user['role'] != 'teacher':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    # 验证作业是否属于该教师
    cursor.execute(
        "SELECT id FROM assignments WHERE id = %s AND teacher_id = %s",
        (assignment_id, current_user['id'])
    )
    if not cursor.fetchone():
        cursor.close()
        return jsonify({'message': '作业不存在或无权访问'}), 404

    # 获取提交情况
    cursor.execute(
        """SELECT s.*, u.username FROM submissions s
           JOIN users u ON s.student_id = u.id
           WHERE s.assignment_id = %s""",
        (assignment_id,)
    )
    submissions = cursor.fetchall()
    cursor.close()

    return jsonify(submissions)


# 批改作业
@teacher_bp.route('/submissions/<int:submission_id>/grade', methods=['POST'])
@token_required
def grade_submission(current_user, submission_id):
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
