import os
import uuid

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from db.connect import get_db
from datetime import datetime
from .utils import token_required  # 从utils导入装饰器


student_bp = Blueprint('student', __name__)


# 获取学生可见的作业
@student_bp.route('/assignments', methods=['GET'])
@token_required
def get_student_assignments(current_user):
    if current_user['role'] != 'student':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM assignments ORDER BY deadline ASC"
    )
    assignments = cursor.fetchall()

    # 获取学生已提交的作业ID
    cursor.execute(
        "SELECT assignment_id FROM submissions WHERE student_id = %s",
        (current_user['id'],)
    )
    submitted_ids = [item['assignment_id'] for item in cursor.fetchall()]

    cursor.close()

    # 添加是否已提交的标记
    for assignment in assignments:
        assignment['submitted'] = assignment['id'] in submitted_ids

    return jsonify(assignments)


# 提交作业
# 配置文件上传路径和允许的扩展名
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

# 创建上传目录（如果不存在）
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@student_bp.route('/assignments/<int:assignment_id>/submit', methods=['POST'])
@token_required
def submit_assignment(current_user, assignment_id):
    if current_user['role'] != 'student':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    try:
        # 获取文本内容
        content = request.form.get('content', '')

        # 处理文件上传
        file_url = ''
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '' and allowed_file(file.filename):
                # 生成唯一文件名（避免冲突）
                filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)

                # 生成可访问的URL
                file_url = f"/uploads/{filename}"

        # 获取作业标题，用于AI批改
        cursor.execute("SELECT title, description FROM assignments WHERE id = %s", (assignment_id,))
        assignment = cursor.fetchone()
        assignment_description = assignment['description'] if assignment else "未知作业"

        # AI自动批改
        ai_score = None
        ai_feedback = None
        try:
            from ai_grading import TongyiQianwenAPI
            ai = TongyiQianwenAPI()
            ai_score, ai_feedback = ai.get_grading(assignment_description , content)
        except Exception as e:
            print(f"AI批改服务初始化失败: {str(e)}")
            ai_feedback = "AI批改服务暂时不可用"

        # 检查是否已提交
        cursor.execute(
            "SELECT id FROM submissions WHERE assignment_id = %s AND student_id = %s",
            (assignment_id, current_user['id'])
        )
        if cursor.fetchone():
            # 更新提交
            cursor.execute(
                """UPDATE submissions SET content = %s, file_url = %s, submitted_at = %s,
                   ai_score = %s, ai_feedback = %s
                   WHERE assignment_id = %s AND student_id = %s""",
                (content, file_url, datetime.now(), ai_score, ai_feedback,
                 assignment_id, current_user['id'])
            )
        else:
            # 新提交
            cursor.execute(
                """INSERT INTO submissions 
                   (assignment_id, student_id, content, file_url, submitted_at,
                    ai_score, ai_feedback)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (assignment_id, current_user['id'], content, file_url, datetime.now(),
                 ai_score, ai_feedback)
            )

        db.commit()
        return jsonify({
            'success': True,
            'message': '作业提交成功',
            'file_url': file_url,
            'ai_score': ai_score,
            'ai_feedback': ai_feedback
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()

# 获取学生的提交历史
@student_bp.route('/submissions', methods=['GET'])
@token_required
def get_student_submissions(current_user):
    if current_user['role'] != 'student':
        return jsonify({'message': '权限不足'}), 403

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """SELECT s.*, a.title FROM submissions s
           JOIN assignments a ON s.assignment_id = a.id
           WHERE s.student_id = %s ORDER BY submitted_at DESC""",
        (current_user['id'],)
    )
    submissions = cursor.fetchall()
    cursor.close()

    return jsonify(submissions)