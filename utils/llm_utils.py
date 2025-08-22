import openai
from openai import OpenAI
import os
from datetime import datetime
from config import config
from utils.logger import logger
from typing import List, Tuple

class LLMUtils:
    """
    🤖 大语言模型工具类
    功能：
    1. 🔗 封装OpenAI API调用
    2. 🎯 提供意图识别、文本生成、问题预测等功能
    3. 🛡️ 处理API错误和限流
    
    设计原则：
    1. 🔍 抽象化 - 隐藏底层API细节
    2. ⚙️ 可配置 - 模型参数可通过配置调整
    3. 🛡️ 健壮性 - 处理API错误和异常
    """
    
    def __init__(self):
        logger.info("🤖 初始化LLM工具类")
        
        # 🔗 创建OpenAI客户端实例
        self.client = OpenAI(
            api_key=config.MODEL_API_KEY,
            base_url=config.MODEL_BASE_URL,
        )
        logger.info(f"✅ LLM配置完成: {config.MODEL_NAME} @ {config.MODEL_BASE_URL}")
    
    def generate_text(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> str:
        """
        ✍️ 使用LLM生成文本
        参数:
            prompt: 输入提示
            max_tokens: 最大生成token数
            temperature: 生成温度 (0-1, 越高越随机)
        返回: 生成的文本
        """
        try:
            logger.info(f"🤖 开始文本生成 (max_tokens: {max_tokens}, temperature: {temperature})")
            start_time = datetime.now()
            
            # 🔗 使用新的Chat Completions API
            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            # ✂️ 提取生成的文本
            generated_text = response.choices[0].message.content.strip()
            
            # 📝 记录性能信息
            duration = (datetime.now() - start_time).total_seconds()
            tokens_used = response.usage.total_tokens
            logger.info(f"✅ LLM生成完成: {tokens_used} tokens, {duration:.2f}s, 回复长度: {len(generated_text)}")
            
            return generated_text
        except openai.APIError as e:  # 🚨 使用新的错误类型
            logger.error(f"❌ LLM API错误: {str(e)}")
            return "抱歉，我暂时无法回答这个问题。😅"
        except Exception as e:
            logger.error(f"❌ LLM调用异常: {str(e)}")
            return "处理您的请求时发生了错误。😅"
    
    def classify_intent(self, user_input: str) -> str:
        """
        🎯 使用LLM进行意图识别
        参数: 用户输入文本
        返回: 意图类别 (A-K)
        """
        logger.info(f"🎯 开始意图分类: '{user_input[:50]}...'")
        
        # 📝 构造提示
        prompt = config.INTENT_PROMPT.format(user_input=user_input)
        
        # 🤖 调用LLM
        intent = self.generate_text(prompt, max_tokens=2, temperature=0.1)
        
        # ✅ 验证和清理结果
        intent = intent.strip().upper()
        valid_intents = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K"]
        
        if intent in valid_intents:
            logger.info(f"✅ 意图识别成功: '{user_input[:30]}...' -> {intent}")
            return intent
        else:
            logger.warning(f"⚠️ 无法识别的意图: '{intent}'，使用默认值 'D'")
            return "D"  # ❓ 无法识别
    
    def predict_next_questions(self, current_input: str, history: List[Tuple[str, str]], max_questions: int = 3) -> List[str]:
        """
        🔮 预测后续可能的问题
        参数:
            current_input: 当前用户输入
            history: 历史对话列表 [(role, content), ...]
            max_questions: 最大预测问题数
        返回: 预测的问题列表
        """
        logger.info(f"🔮 开始预测后续问题 (最多{max_questions}个)")
        
        # 📝 构建历史对话上下文
        history_context = "\n".join([f"{role}: {content}" for role, content in history[-config.MAX_CHAT_HISTORY:]])
        
        # 📝 构造提示
        prompt = f"""
        🔮 根据当前对话内容和历史记录，推测用户接下来可能提出的问题（最多{max_questions}个）：
        
        💬 当前对话：
        {current_input}
        
        📜 历史对话（最近{config.MAX_CHAT_HISTORY}条）：
        {history_context}
        
        ❓ 请列出可能的问题，每个问题单独一行：
        """
        
        # 🤖 调用LLM
        response = self.generate_text(prompt, max_tokens=200, temperature=0.5)
        
        # 📋 解析响应为问题列表
        questions = [q.strip() for q in response.split("\n") if q.strip()]
        
        # ✂️ 限制问题数量
        questions = questions[:max_questions]
        logger.info(f"✅ 问题预测完成: {questions}")
        return questions

# 🌍 全局LLM工具对象
llm_utils = LLMUtils()