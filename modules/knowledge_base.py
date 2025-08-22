import os
import uuid
from pathlib import Path
from langchain_community.document_loaders import (
    PyPDFLoader, Docx2txtLoader, TextLoader,
    UnstructuredPowerPointLoader, UnstructuredHTMLLoader, NotebookLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
from chromadb.config import Settings
from config import config
from utils.logger import logger
from utils.llm_utils import llm_utils


class KnowledgeBase:
    """
    📚 知识库管理模块
    功能：
      1. 📝 知识条目的添加、删除和检索
      2. 🔍 文档内容的向量化存储
      3. 🧠 知识检索增强生成(RAG)
      4. 📋 元数据管理
    
    设计原则：
      1. 🔧 模块化设计 - 清晰的接口划分
      2. ⚡ 高效检索 - 使用向量数据库实现语义搜索
      3. 📈 可扩展性 - 支持多种文档格式
      4. 🏷️ 元数据管理 - 丰富的知识条目描述
    """

    def __init__(self):
        logger.info("📚 初始化知识库管理模块")
        
        # 🧩 初始化文本分块器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            length_function=len,
            is_separator_regex=False,
        )
        
        # 🗄️ 初始化向量数据库客户端
        self.chroma_client = chromadb.PersistentClient(
            path=str(config.VECTOR_STORE_DIR),
            settings=Settings(allow_reset=True)
        )
        
        # 📚 主知识库集合
        self.main_collection = self.chroma_client.get_or_create_collection(
            name="main_knowledge_base",
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("✅ 知识库初始化完成")
    
    def _get_loader(self, file_type: str):
        """根据文件类型获取对应的文档加载器"""
        loader_map = {
            "pdf": PyPDFLoader,
            "docx": Docx2txtLoader,
            "txt": lambda path: TextLoader(path, encoding='utf-8'),
            "pptx": UnstructuredPowerPointLoader,
            "html": UnstructuredHTMLLoader,
            "ipynb": NotebookLoader
        }
        return loader_map.get(file_type.lower())
    
    def add_document(self, file_path: Path, metadata: dict) -> bool:
        """
        📥 添加文档到知识库
        1. 📖 加载文档内容
        2. ✂️ 文本分块处理
        3. 🗄️ 存储到向量数据库
        4. 🏷️ 保存元数据
        
        参数:
          file_path: 文件路径
          metadata: 元数据 (标题、作者、标签等)
        返回:
          是否添加成功
        """
        try:
            logger.info(f"📥 开始添加文档到知识库: {file_path.name}")
            
            # 📋 获取文件类型
            file_type = file_path.suffix[1:]  # 去掉点号
            
            # 🛠️ 获取对应的文档加载器
            loader_class = self._get_loader(file_type)
            if not loader_class:
                logger.error(f"❌ 不支持的文件类型: {file_type}")
                return False
            
            # 📖 加载文档
            loader = loader_class(str(file_path))
            documents = loader.load()
            
            if not documents:
                logger.warning(f"⚠️ 文档内容为空: {file_path}")
                return False
            
            # ✂️ 文本分块
            chunks = self.text_splitter.split_documents(documents)
            
            # 📝 准备向量数据库存储
            ids = [str(uuid.uuid4()) for _ in chunks]
            texts = [chunk.page_content for chunk in chunks]
            
            # 🏷️ 添加元数据
            metadatas = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    "source": metadata.get("title", file_path.stem),
                    "author": metadata.get("author", "unknown"),
                    "tags": metadata.get("tags", ""),
                    "chunk_index": i,
                    "file_path": str(file_path),
                    **metadata  # 包含所有自定义元数据
                }
                metadatas.append(chunk_metadata)
            
            # 🗄️ 添加到向量数据库
            self.main_collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            
            logger.info(f"✅ 文档添加成功: {file_path.name} -> {len(chunks)}个块")
            return True
        except Exception as e:
            logger.error(f"❌ 添加文档失败: {file_path} - {str(e)}")
            return False
    
    def delete_document(self, file_path: str) -> bool:
        """
        🗑️ 从知识库中删除文档
        1. 🔍 查找所有相关块
        2. 🗑️ 从向量数据库中删除
        
        参数:
          file_path: 文件路径
        返回:
          是否删除成功
        """
        try:
            logger.info(f"🗑️ 开始从知识库删除文档: {file_path}")
            
            # 🔍 查找所有与该文件相关的块
            results = self.main_collection.get(
                where={"file_path": file_path},
                include=["metadatas", "documents"]
            )
            
            if not results['ids']:
                logger.warning(f"⚠️ 未找到与文件相关的知识块: {file_path}")
                return False
            
            # 🗑️ 删除所有相关块
            self.main_collection.delete(ids=results['ids'])
            
            logger.info(f"✅ 成功删除 {len(results['ids'])} 个知识块")
            return True
        except Exception as e:
            logger.error(f"❌ 删除文档失败: {file_path} - {str(e)}")
            return False
    
    def query(self, question: str, top_k: int = 5) -> tuple:
        """
        🔍 知识库查询
        1. 🔍 语义检索相关文档块
        2. 🤖 使用LLM生成答案
        参数:
          question: 查询问题
          top_k: 返回的相关块数量
        返回:
          (生成的答案, 相关文档块列表)
        """
        try:
            logger.info(f"🔍 开始知识库查询: '{question}'")
            
            # 🔍 语义检索相关文档块
            results = self.main_collection.query(
                query_texts=[question],
                n_results=top_k
            )
            
            # 📄 提取相关文档内容
            context_docs = results['documents'][0]
            metadatas = results['metadatas'][0]
            
            logger.info(f"✅ 检索到 {len(context_docs)} 条相关文档")
            
            # 📝 构建上下文字符串
            context_str = "\n\n".join([
                f"[📄 来源: {meta['source']}, 👤 作者: {meta.get('author', '未知')}]\n{content}"
                for content, meta in zip(context_docs, metadatas)
            ])
            
            # 🤖 使用LLM生成答案
            prompt = f"""
            🤖 你是一个智能知识库助手，请根据提供的上下文信息回答问题。
            如果上下文信息不足以回答问题，请如实告知。
            
            ❓ 问题：
            {question}
            
            📚 上下文信息：
            {context_str}
            
            💡 请基于以上信息提供准确、完整的回答：
            """
            
            answer = llm_utils.generate_text(prompt)
            return answer, context_docs
        except Exception as e:
            logger.error(f"❌ 知识库查询失败: {str(e)}")
            return "抱歉，查询知识库时发生错误。😅", []
    
    def search_documents(self, query: str, top_k: int = 10) -> list:
        """
        🔍 搜索知识库文档
        1. 🔍 根据元数据搜索文档
        2. 📋 返回匹配的文档信息
        
        参数:
          query: 搜索查询
          top_k: 返回结果数量
        返回:
          匹配的文档元数据列表
        """
        try:
            logger.info(f"🔍 开始文档搜索: '{query}'")
            
            # 🔍 在元数据中搜索
            results = self.main_collection.get(
                where={"$or": [
                    {"source": {"$contains": query}},
                    {"author": {"$contains": query}},
                    {"tags": {"$contains": query}}
                ]},
                limit=top_k,
                include=["metadatas"]
            )
            
            # 📋 提取唯一文档信息
            unique_docs = {}
            for metadata in results['metadatas']:
                file_path = metadata.get('file_path')
                if file_path and file_path not in unique_docs:
                    unique_docs[file_path] = {
                        "source": metadata.get("source", ""),
                        "author": metadata.get("author", ""),
                        "tags": metadata.get("tags", ""),
                        "file_path": file_path
                    }
            
            doc_list = list(unique_docs.values())
            logger.info(f"✅ 文档搜索完成: 找到 {len(doc_list)} 个匹配文档")
            return doc_list
        except Exception as e:
            logger.error(f"❌ 文档搜索失败: {str(e)}")
            return []
    
    def get_document_chunks(self, file_path: str) -> list:
        """
        📄 获取文档的所有块
        1. 🔍 根据文件路径查找所有相关块
        2. 📋 返回块内容和元数据
        
        参数:
          file_path: 文件路径
        返回:
          块内容列表
        """
        try:
            logger.info(f"📄 获取文档块: {file_path}")
            
            results = self.main_collection.get(
                where={"file_path": file_path},
                include=["documents", "metadatas"]
            )
            
            chunks = []
            for doc, meta in zip(results['documents'], results['metadatas']):
                chunks.append({
                    "content": doc,
                    "metadata": meta
                })
            
            logger.info(f"✅ 获取文档块完成: {len(chunks)} 个块")
            return chunks
        except Exception as e:
            logger.error(f"❌ 获取文档块失败: {file_path} - {str(e)}")
            return []
    
    def update_chunk(self, chunk_id: str, new_content: str) -> bool:
        """
        ✏️ 更新知识块内容
        1. 🔄 更新向量数据库中的内容
        2. 🔄 重新嵌入向量表示
        
        参数:
          chunk_id: 知识块ID
          new_content: 新内容
        返回:
          是否更新成功
        """
        try:
            logger.info(f"✏️ 开始更新知识块: {chunk_id}")
            
            self.main_collection.update(
                ids=[chunk_id],
                documents=[new_content]
            )
            logger.info(f"✅ 知识块更新成功: {chunk_id}")
            return True
        except Exception as e:
            logger.error(f"❌ 更新知识块失败: {chunk_id} - {str(e)}")
            return False
    
    def get_statistics(self) -> dict:
        """
        📊 获取知识库统计信息
        返回:
          包含统计信息的字典
        """
        try:
            logger.info("📊 开始获取知识库统计信息")
            
            count = self.main_collection.count()
            
            # 📋 获取所有元数据
            results = self.main_collection.get(include=["metadatas"])
            metadatas = results['metadatas']
            
            # 📊 统计文档类型
            doc_types = {}
            for meta in metadatas:
                file_path = meta.get('file_path', '')
                if file_path:
                    file_type = Path(file_path).suffix[1:] or 'unknown'
                    doc_types[file_type] = doc_types.get(file_type, 0) + 1
            
            # 👥 统计作者
            authors = {}
            for meta in metadatas:
                author = meta.get('author', 'unknown')
                authors[author] = authors.get(author, 0) + 1
            
            stats = {
                "total_chunks": count,
                "document_types": doc_types,
                "authors": authors
            }
            
            logger.info(f"📊 统计信息获取完成: 总块数={count}, 文档类型={len(doc_types)}, 作者数={len(authors)}")
            return stats
        except Exception as e:
            logger.error(f"❌ 获取知识库统计失败: {str(e)}")
            return {"error": "获取统计信息失败"}


# 🌍 全局知识库实例
knowledge_base = KnowledgeBase()