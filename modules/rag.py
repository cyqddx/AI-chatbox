import uuid
import chromadb
from chromadb.config import Settings
from utils.llm_utils import llm_utils
from config import config
from utils.logger import logger


class RAGSystem:
    """
    🧠 检索增强生成(RAG)系统
    功能：
      1. 🔍 从向量数据库中检索相关信息
      2. 🤖 使用大语言模型生成回答
      3. 🎯 结合检索结果和用户问题生成高质量回答

    设计原则：
      1. ⚡ 高效检索 - 使用向量数据库快速查找相关信息
      2. 🧠 智能生成 - 利用大语言模型理解上下文
      3. 🧩 模块化 - 与文件处理和LLM模块解耦
    """

    def __init__(self):
        logger.info("🧠 初始化RAG系统")
        
        # 🗄️ 初始化向量数据库客户端
        self.chroma_client = chromadb.PersistentClient(
            path=str(config.VECTOR_STORE_DIR), 
            settings=Settings(allow_reset=True)
        )
        logger.info("✅ RAG系统初始化完成")

    def retrieve(self, query: str, sid: str, top_k: int = 5) -> list:
        """
        🔍 从向量数据库中检索相关信息
        参数:
        query: 查询文本
        sid: 会话ID (UUID格式字符串)
        top_k: 返回的文档数量
        返回:
        相关文档列表
        """
        try:
            logger.info(f"🔍 开始向量检索: 查询='{query}', 会话UUID={sid}, top_k={top_k}")
            
            # 📝 严格验证UUID格式
            try:
                uuid.UUID(str(sid))
                sid_str = str(sid)
            except (ValueError, TypeError):
                logger.error(f"❌ 无效的会话UUID格式: {sid}")
                return []
            
            # 📝 使用UUID格式的会话ID创建集合名称
            collection_name = f"session_{sid_str}"
            logger.debug(f"🗄️ 使用向量集合: {collection_name}")

            # 🔍 检查集合是否存在
            try:
                collection = self.chroma_client.get_collection(collection_name)
                logger.info(f"✅ 找到向量集合: {collection_name}")
            except Exception:
                logger.warning(f"⚠️ 向量集合不存在: {collection_name}")
                # 🆕 创建新的会话专属集合
                self.chroma_client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"✅ 创建新会话向量集合: {collection_name}")
                return []

            # 🔍 执行查询（会话隔离）
            results = collection.query(
                query_texts=[query], 
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )

            # 📋 确保返回的是字符串列表
            if results and results.get("documents"):
                docs = [str(doc) for doc in results["documents"][0]]
                logger.info(f"✅ 检索完成: 会话UUID={sid_str}, 找到 {len(docs)} 条相关文档")
                return docs
            
            logger.info(f"📭 会话 {sid_str} 未找到相关文档")
            return []
            
        except Exception as e:
            logger.error(f"❌ 向量检索失败: 会话UUID={sid} - {str(e)}")
            return []

    def generate_answer(self, query: str, context: list) -> str:
        """
        🤖 使用LLM生成回答
        
        参数:
          query: 用户问题
          context: 检索到的上下文
        返回:
          生成的回答
        """
        try:
            # 📝 构建上下文字符串
            context_str = "\n\n".join(context) if context else "📭 无相关上下文信息"
            
            # 🎯 构造提示
            prompt = f"""
            🤖 你是一个智能课程助手，请根据提供的课程资料回答问题。
            如果上下文信息不足以回答问题，请如实告知。
            
            ❓ 问题：
            {query}
            
            📚 相关资料：
            {context_str}
            
            💡 请根据以上信息提供准确、简洁的回答：
            """
            
            # 🤖 使用LLM生成回答
            logger.info("🤖 开始生成回答...")
            answer = llm_utils.generate_text(prompt)
            logger.info(f"✅ 回答生成完成: 长度={len(answer)}")
            return answer
        except Exception as e:
            logger.error(f"❌ 回答生成失败: {str(e)}")
            return "抱歉，我暂时无法回答这个问题。😅"

    def query(self, question: str, sid: str) -> str:
        """
        🧠 RAG查询完整流程
        
        参数:
          question: 用户问题
          sid: 会话ID (UUID格式)
        返回:
          生成的回答
        """
        logger.info(f"🧠 开始RAG查询: 问题='{question}', 会话={sid}")
        
        # 📝 直接使用UUID格式的会话ID
        logger.debug(f"🆔 使用会话ID: {sid}")

        # 1. 🔍 检索相关信息
        context_docs = self.retrieve(question, sid)
        
        # 📊 记录检索结果
        if context_docs:
            logger.info(f"📊 检索到 {len(context_docs)} 条相关文档")
        else:
            logger.warning("📭 未检索到相关文档")

        # 2. 🤖 生成回答
        answer = self.generate_answer(question, context_docs)
        logger.info("✅ RAG查询完成")
        return answer


# 🌍 全局RAG系统实例
rag_system = RAGSystem()