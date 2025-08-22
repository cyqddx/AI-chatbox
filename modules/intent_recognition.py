from utils.llm_utils import llm_utils
from utils.logger import logger
from config import config

class IntentRecognizer:
    """
    🎯 意图识别模块
    功能：使用大语言模型识别用户输入的意图类别
    
    设计原则：
      1. 🔍 抽象化 - 隐藏LLM调用细节
      2. 🛡️ 错误处理 - 处理识别失败的情况
      3. 📝 日志记录 - 详细记录识别过程
    
    意图类别说明：
      A: 📚 课程相关问题
      B: 🎓 专业领域问题
      C: 💬 日常交流
      D: ❓ 无法识别
      E: 📖 定义与解释类
      F: 🔧 方法与步骤类
      G: ⚖️ 比较与选择类
      H: 📊 评估与建议类
      J: 🔍 其他问题
      K: 📄 文件相关问题
    """
    
    def recognize(self, user_input: str) -> str:
        """
        🎯 识别用户输入的意图类别
        参数:
          user_input: 用户输入的文本
        返回:
          意图类别 (A-K)
        """
        try:
            logger.info(f"🔍 开始意图识别: '{user_input[:50]}...'")
            
            # 使用LLM工具类进行意图识别
            intent = llm_utils.classify_intent(user_input)
            logger.info(f"🤖 LLM返回意图: {intent}")
            
            # 验证意图类别是否有效
            if intent not in config.VALID_INTENTS:
                logger.warning(f"⚠️ 识别到无效意图: {intent}，使用默认值 'D'")
                return "D"  # ❓ 无法识别
            
            logger.info(f"✅ 意图识别成功: '{user_input[:30]}...' -> {intent}")
            return intent
            
        except Exception as e:
            logger.error(f"❌ 意图识别失败: {str(e)}")
            return "D"  # ❓ 无法识别

# 🌍 全局意图识别器实例
intent_recognizer = IntentRecognizer()