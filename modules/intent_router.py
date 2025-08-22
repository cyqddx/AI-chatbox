"""
🛣️ 意图路由模块
功能：根据识别到的意图类型，将用户请求路由到相应的处理工具
"""

from modules import (
    rag,
    web_search,
    professional_qa,
    daily_chat,
    chat_management
)
from utils.logger import logger


class IntentRouter:
    """
    🎯 意图路由类
    负责根据意图类型选择并调用相应的处理工具
    """
    
    def __init__(self):
        # 🗺️ 意图到处理函数的映射
        self.intent_handlers = {
            "A": self._handle_course_question,      # 📚 课程相关问题
            "C": self._handle_daily_chat,          # 💬 日常交流
            "E": self._handle_definition_question, # 📖 定义与解释
            "F": self._handle_method_question,     # 🔧 方法与步骤
            "G": self._handle_comparison_question, # ⚖️ 比较与选择
            "H": self._handle_evaluation_question, # 📊 评估与建议
            "J": self._handle_other_question,      # 🔍 其他问题
            "K": self._handle_file_question        # 📄 文件相关问题
        }
    
    def route(self, intent: str, user_input: str, sid: str, history: list[tuple] = None) -> str:
        """
        🛣️ 根据意图路由到相应的处理工具
        
        参数:
            intent: 意图代码 (A, C, E, F, G, H, J, K)
            user_input: 用户输入文本
            sid: 会话ID (UUID格式)
            history: 聊天记录 [(role, content, timestamp), ...]
        
        返回:
            处理后的回答文本
        """
        logger.info(f"🎯 路由意图: {intent} - '{user_input[:30]}...' (会话: {sid})")
        
        # 🔍 检查是否有对应的处理函数
        handler = self.intent_handlers.get(intent)
        if not handler:
            logger.warning(f"⚠️ 未找到意图处理器: {intent}")
            return self._handle_unknown_intent()
        
        try:
            # 🚀 调用对应的处理函数
            logger.info(f"🔄 调用处理器: {intent} -> {handler.__name__}")
            result = handler(user_input, sid, history)
            logger.info(f"✅ 处理完成: {intent} - 回复长度: {len(result)}")
            return result
        except Exception as e:
            logger.error(f"❌ 意图处理失败: {intent} - {str(e)}")
            return self._handle_error()
    
    def _handle_course_question(self, user_input: str, sid: str, history: list[tuple] = None) -> str:
        """
        📚 处理课程相关问题（意图A）
        使用RAG系统查询课程知识
        """
        try:
            logger.info("📚 开始处理课程相关问题")
            return rag.rag_system.query(user_input, sid)
        except Exception as e:
            logger.error(f"📚 课程问题处理失败: {str(e)}")
            return "抱歉，处理课程问题时出现错误。😅"

    def _handle_daily_chat(self, user_input: str, sid: str, history: list[tuple] = None) -> str:
        """
        💬 处理日常交流（意图C）
        使用日常对话模块生成回复
        """
        logger.info("💬 开始处理日常交流")
        
        # 📝 正确处理历史记录格式
        recent_history = []
        if history:
            for item in history:
                # 处理不同格式的历史记录
                if len(item) >= 2:  # 确保至少有两个元素
                    role, content = item[0], item[1]
                    recent_history.append((role, content))
        
        return daily_chat.daily_chat.generate_response(user_input, recent_history)
    
    def _handle_definition_question(self, user_input: str, sid: str, history: list[tuple] = None) -> str:
        """
        📖 处理定义与解释问题（意图E）
        使用网络搜索获取权威解释
        """
        logger.info("📖 开始处理定义与解释问题")
        return web_search.web_searcher.summarize_search_results(user_input)
    
    def _handle_method_question(self, user_input: str, sid: str, history: list[tuple] = None) -> str:
        """
        🔧 处理方法与步骤问题（意图F）
        使用网络搜索获取操作指南
        """
        logger.info("🔧 开始处理方法与步骤问题")
        return web_search.web_searcher.summarize_search_results(user_input)
    
    def _handle_comparison_question(self, user_input: str, sid: str, history: list[tuple] = None) -> str:
        """
        ⚖️ 处理比较与选择问题（意图G）
        使用专业问答模块进行比较分析
        """
        logger.info("⚖️ 开始处理比较与选择问题")
        return professional_qa.professional_qa.answer_comparison(user_input)
    
    def _handle_evaluation_question(self, user_input: str, sid: str, history: list[tuple] = None) -> str:
        """
        📊 处理评估与建议问题（意图H）
        使用专业问答模块提供评估和建议
        """
        logger.info("📊 开始处理评估与建议问题")
        return professional_qa.professional_qa.answer_evaluation(user_input)
    
    def _handle_other_question(self, user_input: str, sid: str, history: list[tuple] = None) -> str:
        """
        🔍 处理其他专业问题（意图J）
        使用网络搜索获取相关信息
        """
        logger.info("🔍 开始处理其他专业问题")
        return web_search.web_searcher.summarize_search_results(user_input)
    
    def _handle_file_question(self, user_input: str, sid: str, history: list[tuple] = None) -> str:
        """
        📄 处理文件相关问题（意图K）
        使用RAG系统查询上传文件内容
        """
        try:
            logger.info("📄 开始处理文件相关问题")
            return rag.rag_system.query(user_input, sid)
        except Exception as e:
            logger.error(f"📄 文件问题处理失败: {str(e)}")
            return "抱歉，处理文件问题时出现错误。😅"
    
    def _handle_unknown_intent(self) -> str:
        """❓ 处理未知意图"""
        return "抱歉，我暂时无法理解您的问题类型。🤔 请尝试用更清晰的方式提问。"
    
    def _handle_error(self) -> str:
        """❌ 处理处理过程中的错误"""
        return "抱歉，处理您的请求时遇到了问题。😅 请稍后再试。"

# 🌍 创建全局路由实例
intent_router = IntentRouter()