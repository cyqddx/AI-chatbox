from utils.llm_utils import llm_utils
from utils.logger import logger
from modules.web_search import web_searcher

class DailyChat:
    """
    💬 日常交流模块
    功能：处理日常对话和交流
    设计原则：
      1. 🧠 自然语言处理 - 生成自然流畅的对话
      2. 📥 上下文感知 - 基于对话历史生成回答
      3. 😊 友好性 - 生成友好、自然的对话
    """
    
    def generate_response(self, user_input: str, history: list) -> str:
        """
        💬 生成日常交流的回答
        如果识别为实时性问题，则调用网络搜索
        
        参数:
          user_input: 用户输入
          history: 对话历史 [(角色, 内容), ...]
        返回:
          生成的回答
        """
        try:
            # 🕒 检测是否为实时性问题
            if self._is_realtime_question(user_input):
                logger.info("💬 日常交流中检测到实时性问题，调用网络搜索")
                search_result = web_searcher.summarize_search_results(user_input)
                
                # 📝 检查搜索是否成功
                if "不可用" in search_result or "错误" in search_result or "超时" in search_result:
                    # 🔍 搜索框失败，使用LLM生成友好回复
                    prompt = f"""
                    用户问了一个关于实时信息的问题，但网络搜索暂时不可用。
                    
                    用户问题：{user_input}
                    
                    😊 请用友好、自然的方式告诉用户暂时无法获取实时信息，并建议稍后再试或提供一些通用的建议：
                    """
                    return llm_utils.generate_text(prompt)
                
                return search_result

            # 🔄 否则走原有逻辑
            context = self._build_context(history)
            prompt = f"""
            😊 你是一个友好的助手，请根据对话历史进行自然流畅的日常交流：

            对话历史：
            {context}

            用户最新消息：
            {user_input}

            😊 请用友好、自然的语气回复：
            """
            return llm_utils.generate_text(prompt)
        except Exception as e:
            logger.error(f"❌ 日常交流生成失败: {str(e)}")
            return "嗯，我在听，你接着说..."

    def _is_realtime_question(self, text: str) -> bool:
        """
        🕒 检测是否为实时性问题
        关键词匹配 + 简单规则
        """
        realtime_keywords = [
            "今天", "昨天", "明天", "刚刚", "最新", "实时", "现在", "刚刚", "目前",
            "今天早上", "今天下午", "今天晚上", "昨天早上", "昨天下午"
        ]
        return any(keyword in text for keyword in realtime_keywords)
    
    def _build_context(self, history: list) -> str:
        """📝 构建对话历史上下文字符串"""
        if not history:
            return "无对话历史"
        
        # 📋 只保留最近的对话历史
        recent_history = history[-5:]
        
        # 📝 构建LLM需要的格式 (只取角色和内容)
        context_lines = []
        for item in recent_history:
            if len(item) >= 2:  # 🛡️ 确保有角色和内容
                role, content = item[0], item[1]
                context_lines.append(f"{role}: {content}")
        
        return "\n".join(context_lines)

# 🌍 全局日常交流处理器实例
daily_chat = DailyChat()