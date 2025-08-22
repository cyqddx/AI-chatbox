from utils.llm_utils import llm_utils
from modules.web_search import web_searcher
from utils.logger import logger


class ProfessionalQA:
    """
    专业领域问答模块
    功能：处理专业领域问题，包括：
      - 定义与解释类
      - 方法与步骤类
      - 比较与选择类
      - 评估与建议类
      - 其他专业问题

    设计原则：
      1. 专业性强 - 针对不同问题类型采用不同策略
      2. 模块化 - 每种问题类型有独立处理方法
      3. 灵活性 - 结合网络搜索和大模型
    """

    def answer_definition(self, question: str) -> str:
        """
        回答定义与解释类问题
        参数:
          question: 问题文本
        返回:
          生成的回答
        """
        logger.info(f"处理定义与解释类问题: {question}")
        return web_searcher.summarize_search_results(question)

    def answer_method(self, question: str) -> str:
        """
        回答方法与步骤类问题
        参数:
          question: 问题文本
        返回:
          生成的回答
        """
        logger.info(f"处理方法与步骤类问题: {question}")
        return web_searcher.summarize_search_results(question)

    def answer_comparison(self, question: str) -> str:
        """
        回答比较与选择类问题
        参数:
          question: 问题文本
        返回:
          生成的回答
        """
        logger.info(f"处理比较与选择类问题: {question}")

        try:
            # 构造专业提示
            prompt = f"""
            你是一个专业顾问，请比较以下选项并提供选择建议：
            
            问题：{question}
            
            请分析各选项的优缺点，考虑以下因素：
            1. 成本效益
            2. 适用场景
            3. 长期影响
            4. 用户特定需求
            
            最后给出推荐选择：
            """

            return llm_utils.generate_text(prompt)
        except Exception as e:
            logger.error(f"比较问题处理失败: {str(e)}")
            return "抱歉，处理比较问题时出现错误。请尝试重新提问。"

    def answer_evaluation(self, question: str) -> str:
        """
        回答评估与建议类问题
        参数:
          question: 问题文本
        返回:
          生成的回答
        """
        logger.info(f"处理评估与建议类问题: {question}")

        # 构造专业提示
        prompt = f"""
        你是一个专业评估师，请对以下内容进行评估并提供建议：
        
        问题：{question}
        
        请从以下角度进行全面评估：
        1. 当前状态分析
        2. 潜在风险
        3. 改进机会
        4. 最佳实践参考
        
        最后给出具体、可操作的建议：
        """

        return llm_utils.generate_text(prompt)

    def answer_other(self, question: str) -> str:
        """
        回答其他专业问题
        参数:
          question: 问题文本
        返回:
          生成的回答
        """
        logger.info(f"处理其他专业问题: {question}")
        return web_searcher.summarize_search_results(question)


# 全局专业问答实例
professional_qa = ProfessionalQA()
