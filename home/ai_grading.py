# home/utils/ai_grading.py
import requests
import json
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class TongyiQianwenAPI:
    def __init__(self):
        self.api_key = os.getenv("QIANWEN_API_KEY")
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

        if not self.api_key:
            raise ValueError("请设置通义千问API密钥(QIANWEN_API_KEY)")

    def get_grading(self, assignment_description , submission_content):
        """调用通义千问API获取作业评分和评价"""
        prompt = f"""
        请作为一名教师，批改以下作业内容。
        作业标题: {assignment_description }
        作业内容: {submission_content}

        请按照以下格式返回结果:
        1. 评分(0-100分): [分数，纯数字]
        2. 评价: [具体评价内容，指出优点和不足]

        评价需要具体、有建设性，符合作业标题的要求。
        """

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": "qwen-plus",
            "input": {
                "prompt": prompt
            },
            "parameters": {
                "temperature": 0.7,
                "top_p": 0.9
            }
        }

        try:
            response = requests.post(self.api_url, headers=headers, data=json.dumps(data))
            response.raise_for_status()

            result = response.json()
            if "output" in result and "text" in result["output"]:
                return self.parse_grading_result(result["output"]["text"])
            else:
                return None, "AI批改失败，无法获取有效结果"

        except Exception as e:
            print(f"AI批改出错: {str(e)}")
            return None, f"AI批改出错: {str(e)}"

    def parse_grading_result(self, text):
        """解析AI返回的评分结果"""
        try:
            # 提取分数
            score_line = [line for line in text.split('\n') if "评分" in line][0]
            score = int(score_line.split(':')[1].strip())

            # 提取评价
            feedback_line = [line for line in text.split('\n') if "评价" in line][0]
            feedback = feedback_line.split(':')[1].strip()

            # 确保分数在0-100范围内
            if 0 <= score <= 100:
                return score, feedback
            else:
                return None, "AI返回的分数超出范围"

        except Exception as e:
            print(f"解析AI结果出错: {str(e)}")
            return None, "无法解析AI批改结果"