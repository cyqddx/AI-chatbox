from utils.llm_utils import llm_utils
from utils.logger import logger
from config import config


class NextQuestionsPredictor:
    """
    后续问题推测模块
    功能：基于当前对话内容和历史记录，预测用户可能提出的后续问题

    设计原则：
      1. 上下文感知 - 基于对话历史进行预测
      2. 相关性 - 预测与当前话题相关的问题
      3. 实用性 - 提供有价值的后续问题建议
    """

    def predict(
        self, current_input: str, history: list, max_questions: int = 3
    ) -> list:
        """
        预测后续问题
        参数:
          current_input: 当前用户输入
          history: 对话历史 [(角色, 内容), ...]
          max_questions: 最大预测问题数
        返回:
          预测的问题列表
        """
        try:
            # 构建历史对话上下文 - 修复历史记录格式问题
            history_context = self._build_context(history)

            # 调用LLM预测后续问题
            questions = llm_utils.predict_next_questions(
                current_input, history_context, max_questions
            )

            logger.info(f"预测后续问题: {questions}")
            return questions
        except Exception as e:
            logger.error(f"后续问题预测失败: {str(e)}")
            return []

    def _build_context(self, history: list) -> list:
        """
        构建对话历史上下文
        参数:
          history: 原始对话历史
        返回:
          格式化的历史上下文
        """
        # 处理不同格式的历史记录
        formatted_history = []
        for item in history:
            if len(item) >= 2:
                # 如果历史记录有2个元素 (角色, 内容)
                role, content = item[0], item[1]
                formatted_history.append((role, content))
            elif len(item) == 3:
                # 如果历史记录有3个元素 (角色, 内容, 时间戳)
                role, content, _ = item
                formatted_history.append((role, content))
            else:
                logger.warning(f"无效的历史记录格式: {item}")

        # 只保留最近的对话历史
        return (
            formatted_history[-config.MAX_CHAT_HISTORY :] if formatted_history else []
        )


# 全局问题预测器实例
question_predictor = NextQuestionsPredictor()
