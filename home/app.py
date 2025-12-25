import os
from flask import Flask, jsonify, request, session, send_from_directory, render_template
from flask_cors import CORS
from config import Config
from db.connect import init_app, get_db
import jwt
import datetime
import functools

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

init_app(app)

@app.route('/')
def index():
    return render_template('login.html')  # 使用render_template渲染模板
# 配置上传文件夹路径
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')

# 提供上传文件的访问路由
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
# 2. 学生作业页面路由（对应templates/student-assignment.html）
@app.route('/student-assignment.html')
def student_assignment_page():
    return render_template('student-assignment.html')

# 3. 教师作业页面路由（对应templates/teacher-assignment.html）
@app.route('/teacher-assignment.html')
def teacher_assignment_page():
    return render_template('teacher-assignment.html')
# app.py 中添加提交历史页面路由
@app.route('/submissions')
def student_submissions_page():
    return render_template('submissions.html')
# 导入路由
from routes.auth import auth_bp
from routes.teacher import teacher_bp
from routes.student import student_bp

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(teacher_bp, url_prefix='/api/teacher')
app.register_blueprint(student_bp, url_prefix='/api/student')

if __name__ == '__main__':
    app.run(debug=True)