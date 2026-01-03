"""
Flask应用主文件
负责初始化应用、配置路由和注册蓝图
"""
import os
from flask import Flask, send_from_directory, render_template
from flask_cors import CORS
from config import Config
from db.connect import init_app

# ==================== Flask应用初始化 ====================
# 创建Flask应用实例
app = Flask(__name__)
# 加载配置类
app.config.from_object(Config)
# 启用CORS跨域支持，允许前端访问后端API
CORS(app)

# 初始化数据库连接
init_app(app)

# 配置上传文件夹路径，用于存储学生提交的作业文件
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')

# ==================== 页面路由 ====================
# 这些路由用于渲染HTML页面，不处理业务逻辑

@app.route('/')
def index():
    """
    登录页面路由
    返回登录注册页面
    """
    return render_template('login.html')


@app.route('/student-assignment.html')
def student_assignment_page():
    """
    学生作业页面路由
    返回学生作业列表和班级管理页面
    """
    return render_template('student-assignment.html')


@app.route('/teacher-assignment.html')
def teacher_assignment_page():
    """
    教师作业管理页面路由
    返回教师作业管理和班级管理页面
    """
    return render_template('teacher-assignment.html')


@app.route('/submissions')
def student_submissions_page():
    """
    学生提交历史页面路由
    返回学生已提交作业的历史记录页面
    """
    return render_template('submissions.html')


@app.route('/grade-trend.html')
def grade_trend_page():
    """
    成绩趋势分析页面路由
    返回学生成绩趋势图表和分析页面
    """
    return render_template('grade-trend.html')


# ==================== 文件服务路由 ====================
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """
    文件访问路由
    提供学生上传的作业文件的下载访问
    
    Args:
        filename: 文件名
        
    Returns:
        文件内容
    """
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ==================== 注册蓝图 ====================
# 将各个功能模块的路由注册到应用中
# auth_bp: 用户认证相关路由（登录、注册、令牌刷新等）
# teacher_bp: 教师功能相关路由（班级管理、作业管理、批改等）
# student_bp: 学生功能相关路由（加入班级、提交作业、查看成绩等）
from routes.auth import auth_bp
from routes.teacher import teacher_bp
from routes.student import student_bp

# 注册认证蓝图，URL前缀为 /api/auth
app.register_blueprint(auth_bp, url_prefix='/api/auth')
# 注册教师蓝图，URL前缀为 /api/teacher
app.register_blueprint(teacher_bp, url_prefix='/api/teacher')
# 注册学生蓝图，URL前缀为 /api/student
app.register_blueprint(student_bp, url_prefix='/api/student')


if __name__ == '__main__':
    # 开发模式运行，开启调试模式
    app.run(debug=True)
