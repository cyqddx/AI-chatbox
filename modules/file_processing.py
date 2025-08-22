import os
import datetime
import uuid
import shutil
import re
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import docx2txt
import gradio as gr

# 📄 文档加载器
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredPowerPointLoader,
    UnstructuredHTMLLoader,
    NotebookLoader,
    UnstructuredWordDocumentLoader,
)

# 🧩 文本分块
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 🗄️ 向量数据库
import chromadb
from chromadb.config import Settings

# ⚙️ 项目配置
from config import config
from utils.logger import logger
from utils.database import db_manager

# 💬 聊天管理（用于进度提示）
from modules.chat_management import chat_manager

class FileProcessor:
    """
    📁 文件处理模块 - 增强版
    功能：
        1. 📄 支持多种文件格式（PDF、DOCX、TXT、PPTX、HTML、IPYNB）
        2. 💾 自动保存上传文件到本地
        3. ✂️ 文本智能分块处理
        4. 🗄️ 向量化存储到 ChromaDB（会话隔离）
        5. 📊 实时进度反馈
        6. ⏱️ 超时保护机制
    
    设计原则：
        - 🔄 兼容性：完全适配 Gradio 5.42.0 的 FileData 对象
        - 🛡️ 健壮性：多重错误处理和超时保护
        - 📈 可扩展性：模块化设计，易于添加新格式支持
        - 🔗 会话隔离：文档只在指定会话中生效
    """

    def __init__(self) -> None:
        """初始化文件处理器"""
        logger.info("📁 初始化文件处理器")
        
        # 🧩 文本分块器配置
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,          # ✂️ 每个块的最大字符数
            chunk_overlap=config.CHUNK_OVERLAP,    # 🔄 块之间的重叠字符数
            length_function=len,                   # 📏 长度计算函数
            is_separator_regex=False,             # ❌ 不使用正则表达式分隔符
        )

        # 🗄️ ChromaDB 客户端配置
        self.chroma_client = chromadb.PersistentClient(
            path=str(config.VECTOR_STORE_DIR),     # 🗄️ 向量数据库保存路径
            settings=Settings(allow_reset=True),  # 🔄 允许重置数据库
        )
        
        # ⏱️ 处理超时设置（秒）
        self.processing_timeout = 60
        
        # 🧵 线程池用于异步处理
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # 📋 支持的文件格式映射
        self.supported_formats = {
            "pdf": PyPDFLoader,
            "docx": UnstructuredWordDocumentLoader,
            "txt": lambda p: TextLoader(p, encoding="utf-8"),
            "pptx": UnstructuredPowerPointLoader,
            "html": UnstructuredHTMLLoader,
            "ipynb": NotebookLoader,
        }
        
        logger.info("✅ 文件处理器初始化完成")

    def _get_loader(self, file_type: str) -> Any | None:
        """根据文件类型返回对应的文档加载器"""
        loader = self.supported_formats.get(file_type.lower())
        logger.debug(f"📋 获取加载器: {file_type} -> {loader}")
        return loader

    def save_file(self, file_data: Any, phone: str, sid: str) -> str:
        """
        💾 保存上传文件（增强版）
        
        参数:
            file_data: Gradio 5.42.0 的 FileData 对象
            phone: 用户手机号（用于用户目录隔离）
            sid: 会话ID (UUID格式，用于会话隔离)
            
        返回:
            保存后的完整文件路径
        """
        try:
            logger.info(f"💾 开始保存文件: 用户={phone}, 会话={sid}")
            
            # 📝 严格验证UUID格式
            try:
                uuid.UUID(str(sid))
                sid_str = str(sid)
            except (ValueError, TypeError):
                logger.error(f"❌ 无效的会话ID格式: {sid}")
                raise ValueError(f"无效的会话ID: {sid}")

            # 📋 获取文件信息 - 修复文件名提取
            if hasattr(file_data, 'name'):
                # 🎯 Gradio FileData 对象
                original_filename = str(file_data.name)
                source_path = Path(file_data.name) if hasattr(file_data, 'path') else None
            elif hasattr(file_data, 'orig_name'):
                # 📝 备用方案
                original_filename = str(file_data.orig_name)
                source_path = None
            else:
                # 🚨 兜底方案
                original_filename = str(file_data).split('/')[-1]  # 提取文件名
                source_path = None
            
            # 🧹 清理文件名
            original_filename = self.sanitize_filename(original_filename)
            file_type = Path(original_filename).suffix.lower().lstrip(".")

            logger.info(f"📋 文件信息: 名称={original_filename}, 类型={file_type}")

            # ✅ 验证文件格式
            if file_type not in config.SUPPORTED_FILE_FORMATS:
                error_msg = (
                    f"❌ 不支持的文件格式: {file_type}\n"
                    f"✅ 支持的格式: {', '.join(config.SUPPORTED_FILE_FORMATS)}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 📁 创建用户专属目录（用户级隔离）
            user_dir = config.UPLOADS_DIR / phone
            user_dir.mkdir(parents=True, exist_ok=True)

            # 📁 创建会话专属目录（会话级隔离）
            session_dir = user_dir / sid_str
            session_dir.mkdir(parents=True, exist_ok=True)

            # 🆔 生成唯一文件名
            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
            save_path = session_dir / unique_filename
            save_path = save_path.resolve()

            # 📋 验证目录存在
            if not save_path.parent.exists():
                logger.error(f"❌ 目录不存在: {save_path.parent}")
                raise ValueError(f"无法创建保存目录: {save_path.parent}")

            # 💾 复制文件到目标位置
            if hasattr(file_data, 'path') and file_data.path and Path(file_data.path).exists():
                # 📁 直接复制 - 使用绝对路径
                source_path = Path(file_data.path)
                shutil.copy2(str(source_path), str(save_path))
                logger.info(f"✅ 文件复制成功: {source_path} -> {save_path}")
            elif hasattr(file_data, 'read'):
                # 📄 从文件对象读取
                file_bytes = file_data.read()
                with open(save_path, "wb") as f:
                    f.write(file_bytes)
                logger.info(f"✅ 文件字节写入成功: {save_path}")
            else:
                # 📄 从字符串路径读取
                try:
                    source_path = Path(str(file_data))
                    if source_path.exists():
                        shutil.copy2(str(source_path), str(save_path))
                        logger.info(f"✅ 文件复制成功: {source_path} -> {save_path}")
                    else:
                        # 📝 字符串转字节
                        file_bytes = bytes(str(file_data), "utf-8")
                        with open(save_path, "wb") as f:
                            f.write(file_bytes)
                        logger.info(f"✅ 文件字节写入成功: {save_path}")
                except Exception:
                    # 🚨 最后尝试
                    with open(save_path, "wb") as f:
                        f.write(str(file_data).encode('utf-8'))
                    logger.info(f"✅ 文件字符串写入成功: {save_path}")

            # 🗄️ 记录到数据库
            file_id = db_manager.add_file(
                sid=sid_str,
                file_path=str(save_path),
                file_name=original_filename,  # 📋 使用清理后的文件名
                file_type=file_type,
                uploaded_at=datetime.datetime.now().isoformat(),
            )

            logger.info(f"🎉 文件保存完成: {original_filename} -> {save_path} (ID: {file_id})")
            return str(save_path)

        except Exception as e:
            logger.error(f"❌ 文件保存失败: {str(e)}")
            raise ValueError(f"文件保存失败: {str(e)}")

    def load_document(self, file_path: Path, file_type: str) -> list[Any] | None:
        """
        📖 加载并解析文档 - 带超时保护
        
        参数:
            file_path: 文件完整路径
            file_type: 文件扩展名
            
        返回:
            文档内容列表或None
        """
        try:
            loader_class = self._get_loader(file_type)
            if loader_class is None:
                logger.error(f"❌ 不支持的文件类型: {file_type}")
                return None

            abs_path = file_path.resolve()
            if not abs_path.exists():
                logger.error(f"❌ 文件不存在: {abs_path}")
                return None

            logger.info(f"📖 开始加载文档: {abs_path}")

            def _load_document():
                """内部文档加载函数"""
                try:
                    # 📝 特殊处理 Word 文档
                    if file_type == "docx":
                        try:
                            text = docx2txt.process(str(abs_path))
                            from langchain_core.documents import Document
                            return [Document(page_content=text, metadata={"source": str(abs_path)})]
                        except ImportError:
                            logger.error("❌ 请安装docx2txt: pip install docx2txt")
                            return None
                        except Exception as e:
                            logger.error(f"❌ docx2txt处理失败: {e}")
                            return None
                    else:
                        # 📄 其他格式直接加载
                        loader = loader_class(str(abs_path))
                        documents = loader.load()

                    if not documents:
                        logger.warning(f"⚠️ 文档内容为空: {abs_path}")
                        return None

                    logger.info(f"✅ 文档加载成功: {abs_path} - {len(documents)} 个文档")
                    return documents
                except Exception as e:
                    logger.error(f"❌ 文档加载异常: {str(e)}")
                    return None

            # 🧵 使用线程池和超时保护
            future = self.executor.submit(_load_document)
            documents = future.result(timeout=self.processing_timeout)

            return documents

        except TimeoutError:
            logger.error(f"⏱️ 文档加载超时: {file_path} ({self.processing_timeout}秒)")
            return None
        except Exception as e:
            logger.error(f"❌ 文档加载失败: {file_path} - {str(e)}")
            return None

    def process_file(self, sid: str, file_path: Path, file_name: str, file_type: str) -> bool:
        """
        🔄 处理单个文件 - 会话隔离版
        重要：确保文档只在指定的会话中生效
        
        参数:
            sid: 会话ID (UUID格式)
            file_path: 文件路径
            file_name: 原始文件名
            file_type: 文件类型
            
        返回:
            处理成功返回True，否则False
        """
        try:
            # 🔍 严格验证UUID格式
            try:
                session_uuid = uuid.UUID(str(sid))
                sid_str = str(session_uuid)
                logger.info(f"🔄 [FILE_PROCESS] 开始处理文件: {file_name} (会话UUID: {sid_str})")
            except (ValueError, TypeError):
                logger.error(f"❌ [FILE_PROCESS] 无效的会话UUID格式: {sid}")
                return False

            logger.info(f"🔄 开始处理文件: {file_name} (会话: {sid_str})")
            
            # 💬 添加上传进度提示
            progress_msg = f"📄 正在处理文档: {file_name}..."
            chat_manager.add_message(sid_str, "system", progress_msg)

            # 1. 📖 加载文档（带超时保护）
            documents = self.load_document(file_path, file_type)
            if documents is None:
                error_msg = f"❌ 无法加载文档: {file_name}"
                chat_manager.add_message(sid_str, "system", error_msg)
                return False

            # 2. ✂️ 文本分块
            try:
                chunks = self.text_splitter.split_documents(documents)
                if not chunks:
                    warning_msg = f"⚠️ 文档分块为空: {file_name}"
                    chat_manager.add_message(sid_str, "system", warning_msg)
                    return False
            except Exception as e:
                error_msg = f"❌ 文档分块失败: {file_name}"
                chat_manager.add_message(sid_str, "system", error_msg)
                logger.error(f"❌ 文档分块失败: {file_name} - {str(e)}")
                return False

            logger.info(f"📊 分块完成: {file_name} - {len(chunks)} 个块")

            # 3. 🗄️ 获取或创建会话专属的向量存储
            try:
                # 🎯 使用会话ID作为集合名称，确保会话隔离
                collection_name = f"session_{sid_str}"
                collection = self.chroma_client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"✅ 向量集合已就绪: {collection_name}")
            except Exception as e:
                error_msg = f"❌ 向量数据库连接失败"
                chat_manager.add_message(sid_str, "system", error_msg)
                logger.error(f"❌ 向量数据库连接失败: {str(e)}")
                return False

            # 4. 📝 准备数据
            ids = [str(uuid.uuid4()) for _ in chunks]
            texts = [chunk.page_content for chunk in chunks]
            metadatas = [
                {
                    "source": file_name,
                    "chunk_index": i,
                    "file_path": str(file_path.resolve()),
                    "file_type": file_type,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "session_id": sid_str,  # 🎯 添加会话ID标记
                }
                for i in range(len(chunks))
            ]

            # 5. 📦 分批存储到会话专属的向量库
            batch_size = 50  # 🎯 每批50个块
            total_chunks = len(chunks)
            
            try:
                for i in range(0, total_chunks, batch_size):
                    batch_end = min(i + batch_size, total_chunks)
                    
                    collection.add(
                        ids=ids[i:batch_end],
                        documents=texts[i:batch_end],
                        metadatas=metadatas[i:batch_end],
                    )
                    
                    progress = (batch_end / total_chunks) * 100
                    logger.info(f"📤 上传进度: {batch_end}/{total_chunks} ({progress:.1f}%)")
                    
                    # 📊 更新进度提示（大文件）
                    if total_chunks > 100:
                        progress_msg = f"📊 处理中... {progress:.0f}%"
                        chat_manager.add_message(sid_str, "system", progress_msg)
                
                # ✅ 添加成功处理消息
                success_msg = f"✅ 文档处理完成: {file_name} ({len(chunks)} 个片段)"
                chat_manager.add_message(sid_str, "assistant", success_msg)
                
                logger.info(
                    f"🎉 文件处理完成: {file_name} -> {len(chunks)} 个块 "
                    f"(会话: {sid_str})"
                )
                return True
                
            except Exception as e:
                error_msg = f"❌ 向量存储失败: {file_name}"
                chat_manager.add_message(sid_str, "system", error_msg)
                logger.error(f"❌ 向量存储失败: {file_name} - {str(e)}")
                return False

        except Exception as e:
            error_msg = f"💥 处理出错: {file_name}"
            chat_manager.add_message(sid_str, "system", error_msg)
            logger.error(f"❌ 文件处理失败: {file_name} - {str(e)}")
            return False

    def process_uploaded_files(self, sid: str) -> int:
        """
        📦 批量处理未处理文件 - 会话隔离版
        
        参数:
            sid: 会话ID (UUID格式)
        返回:
            成功处理的文件数量
        """
        try:
            # 🔍 严格验证UUID格式
            try:
                uuid.UUID(str(sid))
                sid_str = str(sid)
            except (ValueError, TypeError):
                logger.error(f"❌ 无效的会话ID格式: {sid}")
                return 0

            logger.info(f"📦 开始批量处理文件: 会话={sid_str}")
            
            # 🔍 获取该会话的未处理文件
            unprocessed_files = db_manager.get_unprocessed_files(sid_str)
            if not unprocessed_files:
                logger.info(f"ℹ️ 会话 {sid_str} 没有待处理文件")
                return 0

            processed_count = 0
            file_ids = []

            logger.info(f"🔍 发现 {len(unprocessed_files)} 个待处理文件")

            for file_info in unprocessed_files:
                file_id, file_path, file_name, file_type = file_info

                try:
                    file_path_obj = Path(file_path)
                    if not file_path_obj.exists():
                        logger.error(f"❌ 文件不存在: {file_path}")
                        continue

                    success = self.process_file(
                        sid_str, file_path_obj, file_name, file_type
                    )

                    if success:
                        file_ids.append(file_id)
                        processed_count += 1
                        logger.info(f"✅ 处理成功: {file_name}")
                    else:
                        logger.warning(f"⚠️ 处理失败: {file_name}")

                except Exception as e:
                    logger.error(f"💥 处理异常: {file_name} - {str(e)}")
                    continue

            # 📝 标记文件为已处理
            if file_ids:
                db_manager.mark_files_processed(file_ids)
                logger.info(f"📋 批量更新完成: {len(file_ids)} 个文件")

            logger.info(f"✅ 批量处理完成: 成功处理 {processed_count} 个文件")
            return processed_count

        except Exception as e:
            logger.error(f"❌ 批量处理失败: {str(e)}")
            return 0

    def get_file_info(self, file_path: str) -> dict:
        """
        📋 获取文件信息
        
        参数:
            file_path: 文件路径
        返回:
            文件信息字典
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return {"error": "❌ 文件不存在"}
                
            stat = path.stat()
            info = {
                "name": path.name,
                "size": stat.st_size,
                "type": path.suffix.lower(),
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(path)
            }
            logger.info(f"📋 获取文件信息: {info['name']} - {info['size']} bytes")
            return info
        except Exception as e:
            logger.error(f"❌ 获取文件信息失败: {str(e)}")
            return {"error": str(e)}

    def get_session_file_status(self, sid: str) -> dict:
        """
        📊 获取会话的文件处理状态
        
        参数:
            sid: 会话ID (UUID格式字符串)
        返回:
            文件状态字典 {
                'total': 总文件数,
                'processed': 已处理文件数,
                'unprocessed': 未处理文件数,
                'files': [...]
            }
        """
        try:
            # 🔍 严格验证UUID格式
            uuid.UUID(str(sid))
            sid_str = str(sid)
            
            # 📋 获取所有文件
            all_files = db_manager.get_files_for_session(sid_str)
            
            # 📊 统计状态
            processed = [f for f in all_files if f[5] == 1]  # processed=1
            unprocessed = [f for f in all_files if f[5] == 0]  # processed=0
            
            status = {
                'total': len(all_files),
                'processed': len(processed),
                'unprocessed': len(unprocessed),
                'files': all_files
            }
            
            logger.info(
                f"📊 会话文件状态: 会话={sid_str}, "
                f"总数={len(all_files)}, 已处理={len(processed)}, 未处理={len(unprocessed)}"
            )
            
            return status
            
        except Exception as e:
            logger.error(f"❌ 获取会话文件状态失败: 会话={sid}, 错误={str(e)}")
            return {'total': 0, 'processed': 0, 'unprocessed': 0, 'files': []}

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        🧹 清理文件名，移除非法字符
        
        参数:
            filename: 原始文件名
            
        返回:
            清理后的文件名
        """
        # 🎯 只保留文件名部分
        filename = Path(filename).name
        
        # 🧹 移除非法字符
        filename = re.sub(r'[<>:\"/\\|?*]', '_', filename)
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        
        # 📏 限制长度
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename
        
    def cleanup(self):
        """🧹 清理资源"""
        logger.info("🧹 开始清理文件处理器资源")
        self.executor.shutdown(wait=True)
        logger.info("✅ 文件处理器资源已清理")


# 🌍 创建全局实例
file_processor = FileProcessor()