"""
AI批改模块
使用通义千问API实现作业自动批改和成绩趋势分析功能
"""
import requests
import json
import os
from dotenv import load_dotenv

# 加载环境变量（从.env文件读取API密钥）
load_dotenv()


class TongyiQianwenAPI:
    """
    通义千问API封装类
    提供作业批改和成绩趋势分析功能
    """
    
    def __init__(self):
        """
        初始化API客户端
        
        功能：
        1. 从环境变量读取API密钥
        2. 设置API请求地址
        3. 验证API密钥是否存在
        
        异常：
            ValueError: 如果未设置API密钥则抛出异常
        """
        # 从环境变量获取API密钥
        self.api_key = os.getenv("QIANWEN_API_KEY")
        # 通义千问API的文本生成接口地址
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

        # 验证API密钥是否存在
        if not self.api_key:
            raise ValueError("请设置通义千问API密钥(QIANWEN_API_KEY)")

    def get_grading(self, assignment_description, submission_content):
        """
        调用通义千问API获取作业评分和评价
        
        功能：
        1. 构建批改提示词
        2. 调用API获取AI批改结果
        3. 解析并返回评分和评价
        
        Args:
            assignment_description: 作业描述/标题，用于AI理解作业要求
            submission_content: 学生提交的作业内容（文本或从文件提取的内容）
            
        Returns:
            tuple: (评分(0-100), 评价文本) 或 (None, 错误信息)
        """
        # 构建批改提示词，指导AI如何批改作业
        prompt = f"""
        请作为一名教师，批改以下作业内容。
        作业标题: {assignment_description}
        作业内容: {submission_content}

        请按照以下格式返回结果:
        1. 评分(0-100分): [分数，纯数字]
        2. 评价: [具体评价内容，指出优点和不足]

        评价需要具体、有建设性，符合作业标题与内容的要求。
        """

        # 设置HTTP请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"  # 使用Bearer Token认证
        }

        # 构建API请求数据
        data = {
            "model": "qwen-plus",  # 使用通义千问Plus模型
            "input": {
                "prompt": prompt
            },
            "parameters": {
                "temperature": 0.7,  # 温度参数，控制输出的随机性（0-1）
                "top_p": 0.9  # 核采样参数，控制输出的多样性
            }
        }

        try:
            # 发送POST请求到API
            response = requests.post(self.api_url, headers=headers, data=json.dumps(data))
            response.raise_for_status()  # 如果状态码不是200，抛出异常

            # 解析API返回的JSON结果
            result = response.json()
            if "output" in result and "text" in result["output"]:
                # 调用解析函数提取评分和评价
                return self.parse_grading_result(result["output"]["text"])
            else:
                return None, "AI批改失败，无法获取有效结果"

        except Exception as e:
            # 捕获所有异常，返回错误信息
            print(f"AI批改出错: {str(e)}")
            return None, f"AI批改出错: {str(e)}"

    def parse_grading_result(self, text):
        """
        解析AI返回的评分结果
        
        功能：
        1. 从AI返回的文本中提取分数
        2. 提取评价内容
        3. 验证分数是否在有效范围内（0-100）
        
        Args:
            text: AI返回的文本结果
            
        Returns:
            tuple: (评分(0-100), 评价文本) 或 (None, 错误信息)
        """
        try:
            # 查找包含"评分"的行，提取分数
            score_line = [line for line in text.split('\n') if "评分" in line][0]
            score = int(score_line.split(':')[1].strip())

            # 查找包含"评价"的行，提取评价内容
            feedback_line = [line for line in text.split('\n') if "评价" in line][0]
            feedback = feedback_line.split(':')[1].strip()

            # 验证分数是否在0-100范围内
            if 0 <= score <= 100:
                return score, feedback
            else:
                return None, "AI返回的分数超出范围"

        except Exception as e:
            # 解析失败时返回错误信息
            print(f"解析AI结果出错: {str(e)}")
            return None, "无法解析AI批改结果"

    def analyze_grade_trend(self, class_name, grade_data):
        """
        分析成绩趋势
        
        功能：
        1. 验证数据是否足够（至少需要2个数据点）
        2. 构建成绩趋势分析提示词
        3. 调用API获取AI分析结果
        4. 返回分析文本和成功状态
        
        Args:
            class_name: 班级名称，用于个性化分析
            grade_data: 成绩数据列表，格式为 [
                {
                    'submitted_at': '提交时间',
                    'grade': 分数,
                    'assignment_title': '作业标题'
                }, ...
            ]
        
        Returns:
            tuple: (分析结果文本, 是否成功)
                - 如果成功: (分析文本, True)
                - 如果失败: (错误信息, False)
        """
        # 验证数据是否足够进行分析（至少需要2个数据点才能看出趋势）
        if not grade_data or len(grade_data) < 2:
            return "数据不足，无法进行趋势分析", False
        
        # 从成绩数据中提取信息
        grades = [item['grade'] for item in grade_data]  # 分数列表
        dates = [item['submitted_at'] for item in grade_data]  # 时间列表
        assignments = [item['assignment_title'] for item in grade_data]  # 作业标题列表
        
        # 构建成绩描述字符串，格式：作业1: 85分, 作业2: 90分, ...
        grade_str = ', '.join([f"提交于{dates[i]}的{assignments[i]}: {grades[i]}分" for i in range(len(grades))])
        
        # 构建趋势分析提示词
        prompt = f"""
        请作为一名教育专家，严格按照时间从早到晚的顺序分析此学生在这个班级的成绩趋势。
        
        班级名称: {class_name}
        成绩记录（按时间顺序）:
        {grade_str}
        
        请分析：
        1. 成绩整体趋势（上升/下降/波动）
        2. 成绩变化幅度
        3. 可能的原因分析
        4. 给出学习建议和改进方向
        
        请用简洁、专业、鼓励性的语言进行分析，控制在200字以内。
        """

        # 设置HTTP请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # 构建API请求数据
        data = {
            "model": "qwen-plus",
            "input": {
                "prompt": prompt
            },
            "parameters": {
                "temperature": 0.7,  # 温度参数
                "top_p": 0.9  # 核采样参数
            }
        }

        try:
            # 发送POST请求到API
            response = requests.post(self.api_url, headers=headers, data=json.dumps(data))
            response.raise_for_status()

            # 解析API返回结果
            result = response.json()
            if "output" in result and "text" in result["output"]:
                # 提取分析文本并去除首尾空白
                analysis = result["output"]["text"].strip()
                return analysis, True
            else:
                return "AI分析失败，无法获取有效结果", False

        except Exception as e:
            # 捕获异常，返回错误信息
            print(f"AI成绩趋势分析出错: {str(e)}")
            return f"AI分析出错: {str(e)}", False
