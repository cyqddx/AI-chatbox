import requests
import time
import random
from config import config
from utils.logger import logger
from utils.llm_utils import llm_utils

class WebSearch:
    """
    🕵️ 网络搜索模块，用于通过SerpAPI执行网络搜索并总结结果。
    设计原则：
    1. 🔍 外部知识获取：从互联网获取最新信息。
    2. 📝 结果总结：提取关键信息。
    3. 🔄 API集成：与SerpAPI无缝集成。
    """
    
    def __init__(self, api_key=None):
        """
        🕵️ 初始化网络搜索模块。
        参数：
        - api_key: SerpAPI 密钥（可选），默认使用配置文件中的密钥。
        """
        # 📝 使用配置中的API密钥
        self.api_key = api_key or config.SERPAPI_API_KEY
        if not self.api_key:
            logger.warning("🔍 SerpAPI密钥未配置，网络搜索功能不可用")

    def search(self, query: str, num_results: int = 5, max_retries: int = 3, retry_delay: int = 5) -> str:
        """
        🕵️ 执行网络搜索，并加入重试机制，提升搜索的健壮性。
        参数：
        - query: 搜索用户问题。
        - num_results: 返回的结果数量，默认为5。
        - max_retries: 最大重试次数，默认为3次。
        - retry_delay: 重试间隔（秒，默认为5秒。
        返回值：
        - 成功时返回搜索结果摘要；失败时返回相应的错误信息。
        """
        if not self.api_key:
            logger.error("🔍 网络搜索功能不可用，请配置API密钥")
            return "网络搜索功能不可用，请配置API密钥"
        
        logger.info(f"🔍 尝试网络搜索：查询 '{query}'")
        
        for attempt in range(1, max_retries + 2):  # 从1开始计数，包含初始尝试
            try:
                # 📝 设置请求参数，增加连接和读取超时时间
                params = {
                    "q": query,               # 搜索输入的查询
                    "api_key": self.api_key,  # API密钥
                    "num": num_results,       # 结果数量
                    "engine": "bing"          # 使用Bing作为搜索引擎
                }
                
                # 🕒 设置连接超时（连接到服务器的时间）和读取超时（等待服务器响应的时间）
                response = requests.get(
                    "https://serpapi.com/search",
                    params=params,
                    timeout=(10, 20)  # 连接超时10秒，读取超时20秒
                )
                response.raise_for_status()  # 📝 检查HTTP错误
                
                # 📊 解析响应并提取搜索结果
                if 'organic_results' in response.json():
                    snippets = [
                        result.get('snippet', '') 
                        for result in response.json()['organic_results'][:num_results]
                    ]
                    return "\n\n".join(snippets)  # 📝 返回搜索结果摘要
                
                logger.warning("🔍 搜索按钮到相关文档，可能需要调整查询参数")
                return "没有搜索到相关信息"  # 📝 没有找到结果的情况
            
            except requests.exceptions.Timeout:
                # ⏱️ 超时处理，记录警告并重试
                logger.warning(f"⏳ 尝试 {attempt}/{max_retries + 1}：网络请求超时，正在重试...")
                time.sleep(retry_delay + random.uniform(0, 2))  # 🕒 增加重试延迟的随机性
            except requests.exceptions.HTTPError as e:
                # 📋 HTTP错误处理，记录详细错误并重试
                logger.error(f"❌ 尝试 {attempt}/{max_retries + 1}：HTTP错误：{e.response.status_code} - {query}")
                time.sleep(retry_delay + random.uniform(0, 2))
            except Exception as e:
                # 🚫 捕获其他异常，记录错误并重试
                logger.error(f"❌ 尝试 {attempt}/{max_retries + 1}：请求失败：{str(e)}")
                time.sleep(retry_delay + random.uniform(0, 2))
        
        logger.error("❌ 多次尝试后，网络搜索仍然失败，请稍后再试")
        return "多次尝试后，网络搜索仍然失败，请稍后再试"  # 📝 所有重试失败后的最终提示

    def summarize_search_results(self, query: str) -> str:
        """
        📝 搜索更并总结结果，利用搜索结果和LLM生成简洁的回答。
        参数：
        - query: 用户的问题。
        返回值：
        - 总结后的结果或者错误信息。
        """
        search_results = self.search(query)
        
        # 🤖 使用LLM总结结果
        prompt = f"""
        根据以下网络搜索结果，回答用户的问题：
        
        问题：{query}
        
        具体的搜索结果：
        {search_results}
        
        😊 请提取关键信息，提供简洁、准确的回答：
        """
        
        return llm_utils.generate_text(prompt)  # 📝 生成总结性的回答

# 🌍 全局网络搜索实例
web_searcher = WebSearch()