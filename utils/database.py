import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
from config import config
from utils.logger import logger


class DatabaseManager:
    """
    🗄️ 数据库管理工具类
    功能：
        1. ✅ 封装SQLite数据库操作
        2. 📋 提供用户、会话、消息和文件管理的CRUD操作
        3. 📊 提供知识库管理和系统维护的CRUD操作
        4. 🔄 自动初始化数据库结构
        5. ⚠️ 处理数据库连接和错误

    设计原则：
        1. 🔒 单一职责 - 只处理数据库相关操作
        2. 🐛 可测试性 - 所有方法可独立测试
        3. 🔄 可恢复性 - 提供备份和还原方法
    """

    def __init__(self, db_path=None):
        # 📄 使用配置中的数据库路径
        self.db_path = db_path or config.DB_PATH
        
        # 📋 确保数据库目录存在
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # 🔄 初始化数据库
        self._init_db()

    # ================================ 数据库初始化 ================================

    def _init_db(self):
        """初始化数据库结构 - 增强版"""
        logger.info("🔄 初始化数据库...")
        
        # 📄 获取数据库连接
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # ================================= 用户表 =================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    phone TEXT PRIMARY KEY,  -- 用户手机号 (主键)
                    pwd TEXT NOT NULL,       -- 用户密码
                    name TEXT,              -- 用户名
                    role INTEGER DEFAULT 0  -- 用户角色 (0: 普通用户, 1: 管理员)
                )
            ''')
            
            # ================================= 会话表 =================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    sid TEXT PRIMARY KEY,    -- 会话ID (UUID格式)
                    phone TEXT,              -- 关联的用户手机号
                    title TEXT,              -- 会话标题
                    created TEXT NOT NULL    -- 创建时间 (ISO格式)
                )
            ''')
            
            # ================================= 消息表 =================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 消息ID
                    sid TEXT NOT NULL,                     -- 关联的会话ID
                    role TEXT NOT NULL,                    -- 消息角色 (user/assistant/system)
                    content TEXT NOT NULL,                 -- 消息内容
                    ts TEXT NOT NULL                       -- 时间戳 (ISO格式)
                )
            ''')
            
            # ================================= 文件表 =================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 文件ID
                    sid TEXT NOT NULL,                     -- 关联的会话ID
                    file_path TEXT NOT NULL,               -- 文件存储路径
                    file_name TEXT NOT NULL,               -- 原始文件名
                    file_type TEXT NOT NULL,               -- 文件类型 (pdf, docx等)
                    uploaded_at TEXT NOT NULL,             -- 上传时间 (ISO格式)
                    processed INTEGER DEFAULT 0            -- 处理状态 (0: 未处理, 1: 已处理)
                )
            ''')
            
            # ================================= 知识库表 =================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 知识条目ID
                    file_name TEXT NOT NULL,                -- 文件名
                    file_path TEXT NOT NULL,                -- 文件路径
                    title TEXT NOT NULL,                    -- 标题
                    author TEXT,                            -- 作者
                    tags TEXT,                              -- 标签 (逗号分隔)
                    status TEXT CHECK(status IN ('pending', 'pending_review', 'approved', 'rejected', 'deleted')) DEFAULT 'pending',  -- 状态
                    reviewer TEXT,                          -- 审核人
                    review_status TEXT,                     -- 审核状态
                    review_comments TEXT,                   -- 审核意见
                    created_at TEXT NOT NULL,               -- 创建时间 (ISO格式)
                    updated_at TEXT,                        -- 更新时间 (ISO格式)
                    reviewed_at TEXT,                       -- 审核时间 (ISO格式)
                    description TEXT,                       -- 描述
                    content_summary TEXT,                   -- 内容摘要
                    category TEXT                           -- 分类字段
                )
            ''')
            
            # ================================= 知识库权限表 =================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 权限ID
                    entry_id INTEGER NOT NULL,              -- 关联的知识条目ID
                    role TEXT NOT NULL                      -- 角色 (admin, reviewer, user)
                )
            ''')
            
            # ================================= 系统告警表 =================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 告警ID
                    message TEXT NOT NULL,                  -- 告警消息
                    level TEXT CHECK(level IN ('info', 'warning', 'error', 'critical')) DEFAULT 'warning',  -- 告警级别
                    created_at TEXT NOT NULL                -- 创建时间 (ISO格式)
                )
            ''')
            
            # ================================= 系统备份表 =================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 备份ID
                    backup_path TEXT NOT NULL,              -- 备份文件路径
                    version TEXT,                           -- 系统版本
                    created_at TEXT NOT NULL,               -- 创建时间 (ISO格式)
                    size INTEGER                           -- 备份文件大小 (字节)
                )
            ''')
            
            # ================================= 索引优化 =================================
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_phone ON sessions(phone)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_sid ON messages(sid)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_sid ON files(sid)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge_entries(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_permissions ON knowledge_permissions(entry_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_alerts_level ON system_alerts(level)')
            
            conn.commit()
            logger.info("✅ 数据库初始化完成")
            
        except sqlite3.Error as e:
            logger.error(f"❌ 数据库初始化失败: {str(e)}")
            conn.rollback()
        finally:
            conn.close()

    # ================================ 用户管理方法 ================================

    def add_user(self, phone: str, pwd: str, name: str = "") -> tuple[bool, str]:
        """
        ➕ 添加新用户
        
        参数:
            phone: 手机号
            pwd: 密码
            name: 用户名（可选）
        返回:
            (操作结果, 消息)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 🔍 检查用户是否已存在
            cursor.execute("SELECT 1 FROM users WHERE phone = ?", (phone,))
            if cursor.fetchone():
                return False, "该手机号已注册"
            
            # 📝 插入新用户
            cursor.execute(
                "INSERT INTO users(phone, pwd, name) VALUES(?, ?, ?)",
                (phone, pwd, name or phone)
            )
            conn.commit()
            
            logger.info(f"✅ 用户添加成功: {phone}")
            return True, "用户添加成功"
            
        except sqlite3.Error as e:
            logger.error(f"❌ 添加用户失败: {str(e)}")
            conn.rollback()
            return False, f"数据库错误: {str(e)}"
        finally:
            conn.close()

    def get_user(self, phone: str) -> tuple | None:
        """
        🔍 根据手机号获取用户信息
        
        参数:
            phone: 手机号
        返回:
            用户信息元组 (phone, pwd, name, role) 或 None
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT phone, pwd, name, role FROM users WHERE phone = ?", (phone,))
            return cursor.fetchone()
            
        except sqlite3.Error as e:
            logger.error(f"❌ 获取用户失败: {str(e)}")
            return None
        finally:
            conn.close()

    def update_user_role(self, phone: str, role: int) -> bool:
        """
        ✏️ 更新用户角色
        
        参数:
            phone: 手机号
            role: 新角色 (0: 普通用户, 1: 管理员)
        返回:
            是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("UPDATE users SET role = ? WHERE phone = ?", (role, phone))
            conn.commit()
            
            logger.info(f"✅ 用户角色更新: {phone} -> {role}")
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"❌ 更新用户角色失败: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete_user(self, phone: str) -> bool:
        """
        🗑️ 删除用户
        
        参数:
            phone: 手机号
        返回:
            是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM users WHERE phone = ?", (phone,))
            conn.commit()
            
            logger.info(f"✅ 用户删除成功: {phone}")
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"❌ 删除用户失败: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ================================ 会话管理方法 ================================

    def create_session(self, sid: str, phone: str, title: str, created: str) -> bool:
        """
        ➕ 创建新会话
        
        参数:
            sid: 会话ID (UUID格式)
            phone: 用户手机号
            title: 会话标题
            created: 创建时间 (ISO格式)
        返回:
            是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO sessions(sid, phone, title, created) VALUES(?, ?, ?, ?)",
                (sid, phone, title, created)
            )
            conn.commit()
            
            logger.info(f"✅ 会话创建成功: {sid}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"❌ 创建会话失败: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_sessions(self, phone: str) -> list[tuple]:
        """
        🔍 获取用户的所有会话
        
        参数:
            phone: 用户手机号
        返回:
            会话列表 [(sid, title, created), ...]
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT sid, title, created FROM sessions WHERE phone = ? ORDER BY created DESC", (phone,))
            return cursor.fetchall()
            
        except sqlite3.Error as e:
            logger.error(f"❌ 获取会话列表失败: {str(e)}")
            return []
        finally:
            conn.close()

    def get_session(self, sid: str) -> tuple | None:
        """
        🔍 根据会话ID获取会话信息
        
        参数:
            sid: 会话ID
        返回:
            会话信息元组 (sid, phone, title, created) 或 None
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT sid, phone, title, created FROM sessions WHERE sid = ?", (sid,))
            return cursor.fetchone()
            
        except sqlite3.Error as e:
            logger.error(f"❌ 获取会话失败: {str(e)}")
            return None
        finally:
            conn.close()

    # ================================ 消息管理方法 ================================

    def add_message(self, sid: str, role: str, content: str, ts: str) -> bool:
        """
        ➕ 添加消息
        
        参数:
            sid: 会话ID
            role: 消息角色 (user/assistant/system)
            content: 消息内容
            ts: 时间戳 (ISO格式)
        返回:
            是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO messages(sid, role, content, ts) VALUES(?, ?, ?, ?)",
                (sid, role, content, ts)
            )
            conn.commit()
            
            logger.info(f"✅ 消息添加成功: {sid} - {role}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"❌ 添加消息失败: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_messages(self, sid: str, limit: int | None = None) -> list[tuple]:
        """
        🔍 获取会话消息
        
        参数:
            sid: 会话ID
            limit: 返回的消息数量限制 (None表示全部)
        返回:
            消息列表 [(role, content, ts), ...]
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if limit is not None:
                cursor.execute("SELECT role, content, ts FROM messages WHERE sid = ? ORDER BY ts LIMIT ?", (sid, limit))
            else:
                cursor.execute("SELECT role, content, ts FROM messages WHERE sid = ? ORDER BY ts", (sid,))
                
            return cursor.fetchall()
            
        except sqlite3.Error as e:
            logger.error(f"❌ 获取消息失败: {str(e)}")
            return []
        finally:
            conn.close()

    # ================================ 文件管理方法 ================================

    def add_file(self, sid: str, file_path: str, file_name: str, file_type: str, uploaded_at: str) -> int | None:
        """
        ➕ 添加文件记录
        
        参数:
            sid: 会话ID
            file_path: 文件存储路径
            file_name: 原始文件名
            file_type: 文件类型 (pdf, docx等)
            uploaded_at: 上传时间 (ISO格式)
        返回:
            文件ID 或 None (失败)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO files(sid, file_path, file_name, file_type, uploaded_at) VALUES(?, ?, ?, ?, ?)",
                (sid, file_path, file_name, file_type, uploaded_at)
            )
            conn.commit()
            
            file_id = cursor.lastrowid
            logger.info(f"✅ 文件记录添加成功: {file_name} (ID: {file_id})")
            return file_id
            
        except sqlite3.Error as e:
            logger.error(f"❌ 添加文件记录失败: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_files_for_session(self, sid: str) -> list[tuple]:
        """
        🔍 获取会话的所有文件记录
        
        参数:
            sid: 会话ID
        返回:
            文件列表 [(id, file_path, file_name, file_type, uploaded_at, processed), ...]
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, file_path, file_name, file_type, uploaded_at, processed FROM files WHERE sid = ? ORDER BY uploaded_at DESC",
                (sid,)
            )
            return cursor.fetchall()
            
        except sqlite3.Error as e:
            logger.error(f"❌ 获取文件记录失败: {str(e)}")
            return []
        finally:
            conn.close()

    def mark_files_processed(self, file_ids: list[int]) -> bool:
        """
        ✅ 标记文件为已处理
        
        参数:
            file_ids: 文件ID列表
        返回:
            是否成功
        """
        if not file_ids:
            return True  # 空列表视为成功
            
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            placeholders = ",".join(["?"] * len(file_ids))
            cursor.execute(
                f"UPDATE files SET processed = 1 WHERE id IN ({placeholders})",
                file_ids
            )
            conn.commit()
            
            logger.info(f"✅ 文件标记为已处理: {file_ids}")
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"❌ 标记文件处理状态失败: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ================================ 知识库管理方法 ================================

    def add_knowledge_entry(self, file_name: str, file_path: str, title: str, author: str, tags: str, status: str, reviewer: str, review_status: str, review_comments: str, created_at: str, updated_at: str, reviewed_at: str, description: str, content_summary: str, category: str) -> int | None:
        """
        ➕ 添加知识库条目
        
        参数:
            file_name: 文件名
            file_path: 文件路径
            title: 标题
            author: 作者
            tags: 标签 (逗号分隔)
            status: 状态 (pending, pending_review, approved, rejected, deleted)
            reviewer: 审核人
            review_status: 审核状态
            review_comments: 审核意见
            created_at: 创建时间 (ISO格式)
            updated_at: 更新时间 (ISO格式)
            reviewed_at: 审核时间 (ISO格式)
            description: 描述
            content_summary: 内容摘要
            category: 分类
        返回:
            新增条目ID 或 None (失败)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT INTO knowledge_entries (
                    file_name, file_path, title, author, tags, status,
                    reviewer, review_status, review_comments, created_at,
                    updated_at, reviewed_at, description, content_summary, category
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_name, file_path, title, author, tags, status,
                    reviewer, review_status, review_comments, created_at,
                    updated_at, reviewed_at, description, content_summary, category
                )
            )
            conn.commit()
            
            entry_id = cursor.lastrowid
            logger.info(f"✅ 知识条目添加成功: ID {entry_id}")
            return entry_id
            
        except sqlite3.Error as e:
            logger.error(f"❌ 添加知识条目失败: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_knowledge_entry(self, entry_id: int) -> dict | None:
        """
        🔍 根据ID获取知识条目
        
        参数:
            entry_id: 条目ID
        返回:
            条目信息字典或 None
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT id, file_name, file_path, title, author, tags, status,
                       reviewer, review_status, review_comments, created_at,
                       updated_at, reviewed_at, description, content_summary, category
                FROM knowledge_entries WHERE id = ?
                """,
                (entry_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "file_name": row[1],
                    "file_path": row[2],
                    "title": row[3],
                    "author": row[4],
                    "tags": row[5],
                    "status": row[6],
                    "reviewer": row[7],
                    "review_status": row[8],
                    "review_comments": row[9],
                    "created_at": row[10],
                    "updated_at": row[11],
                    "reviewed_at": row[12],
                    "description": row[13],
                    "content_summary": row[14],
                    "category": row[15]
                }
            return None
            
        except sqlite3.Error as e:
            logger.error(f"❌ 获取知识条目失败: {str(e)}")
            return None
        finally:
            conn.close()

    def get_knowledge_entries(self, status: str | None = None) -> list[dict]:
        """
        🔍 获取知识条目列表
        
        参数:
            status: 筛选状态 (None表示全部)
        返回:
            条目列表
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if status:
                cursor.execute(
                    "SELECT id, file_name, title, author, tags, status, created_at, category FROM knowledge_entries WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                )
            else:
                cursor.execute(
                    "SELECT id, file_name, title, author, tags, status, created_at, category FROM knowledge_entries ORDER BY created_at DESC"
                )
                
            rows = cursor.fetchall()
            
            entries = []
            for row in rows:
                entries.append({
                    "id": row[0],
                    "file_name": row[1],
                    "title": row[2],
                    "author": row[3],
                    "tags": row[4],
                    "status": row[5],
                    "created_at": row[6],
                    "category": row[7]
                })
                
            logger.info(f"✅ 获取知识条目成功: {len(entries)} 条")
            return entries
            
        except sqlite3.Error as e:
            logger.error(f"❌ 获取知识条目列表失败: {str(e)}")
            return []
        finally:
            conn.close()

    def update_knowledge_content(self, entry_id: int, new_content: str) -> bool:
        """
        ✏️ 更新知识条目内容
        
        参数:
            entry_id: 条目ID
            new_content: 新内容
        返回:
            是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE knowledge_entries SET content_summary = ?, updated_at = ? WHERE id = ?",
                (new_content, datetime.now().isoformat(), entry_id)
            )
            conn.commit()
            
            logger.info(f"✅ 知识条目内容更新成功: ID {entry_id}")
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"❌ 更新知识条目内容失败: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def update_knowledge_status(self, entry_id: int, status: str) -> bool:
        """
        ✏️ 更新知识条目状态
        
        参数:
            entry_id: 条目ID
            status: 新状态 (pending, approved, rejected, deleted)
        返回:
            是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE knowledge_entries SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now().isoformat(), entry_id)
            )
            conn.commit()
            
            logger.info(f"✅ 知识条目状态更新成功: ID {entry_id} -> {status}")
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"❌ 更新知识条目状态失败: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def update_knowledge_review(self, entry_id: int, reviewer: str, status: str, comments: str) -> bool:
        """
        ✏️ 更新知识条目审核信息
        
        参数:
            entry_id: 条目ID
            reviewer: 审核人
            status: 审核状态 (approved, rejected)
            comments: 审核意见
        返回:
            是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                UPDATE knowledge_entries 
                SET review_status = ?, reviewer = ?, review_comments = ?, reviewed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, reviewer, comments, datetime.now().isoformat(), datetime.now().isoformat(), entry_id)
            )
            conn.commit()
            
            logger.info(f"✅ 知识条目审核更新成功: ID {entry_id}")
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"❌ 更新知识条目审核失败: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete_knowledge_entry(self, entry_id: int) -> bool:
        """
        🗑️ 删除知识条目
        
        参数:
            entry_id: 条目ID
        返回:
            是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM knowledge_entries WHERE id = ?", (entry_id,))
            conn.commit()
            
            logger.info(f"✅ 知识条目删除成功: ID {entry_id}")
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            logger.error(f"❌ 删除知识条目失败: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def set_knowledge_permissions(self, entry_id: int, roles: list[str]) -> bool:
        """
        ✏️ 设置知识条目访问权限
        
        参数:
            entry_id: 条目ID
            roles: 角色列表 (admin, reviewer, user)
        返回:
            是否成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 🗑️ 删除现有权限
            cursor.execute("DELETE FROM knowledge_permissions WHERE entry_id = ?", (entry_id,))
            
            # ➕ 添加新权限
            for role in roles:
                cursor.execute(
                    "INSERT INTO knowledge_permissions(entry_id, role) VALUES(?, ?)",
                    (entry_id, role)
                )
                
            conn.commit()
            
            logger.info(f"✅ 知识条目权限更新成功: ID {entry_id} -> {roles}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"❌ 设置知识条目权限失败: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_knowledge_permissions(self, entry_id: int) -> list[str]:
        """
        🔍 获取知识条目权限
        
        参数:
            entry_id: 条目ID
        返回:
            角色列表
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT role FROM knowledge_permissions WHERE entry_id = ?", (entry_id,))
            rows = cursor.fetchall()
            
            return [row[0] for row in rows]
            
        except sqlite3.Error as e:
            logger.error(f"❌ 获取知识条目权限失败: {str(e)}")
            return []
        finally:
            conn.close()

    # ================================ 系统维护方法 ================================

    def add_system_alert(self, message: str, level: str = "warning") -> int | None:
        """
        ➕ 添加系统告警
        
        参数:
            message: 告警消息
            level: 告警级别 (info, warning, error, critical)
        返回:
            新增告警ID 或 None (失败)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO system_alerts(message, level, created_at) VALUES(?, ?, ?)",
                (message, level, datetime.now().isoformat())
            )
            conn.commit()
            
            alert_id = cursor.lastrowid
            logger.info(f"✅ 系统告警添加成功: ID {alert_id}")
            return alert_id
            
        except sqlite3.Error as e:
            logger.error(f"❌ 添加系统告警失败: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_system_alerts(self, level: str | None = None, limit: int = 50) -> list[dict]:
        """
        🔍 获取系统告警
        
        参数:
            level: 筛选级别 (None表示全部)
            limit: 返回数量限制
        返回:
            告警列表
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if level:
                cursor.execute(
                    "SELECT id, message, level, created_at FROM system_alerts WHERE level = ? ORDER BY created_at DESC LIMIT ?",
                    (level, limit)
                )
            else:
                cursor.execute(
                    "SELECT id, message, level, created_at FROM system_alerts ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
                
            rows = cursor.fetchall()
            
            alerts = []
            for row in rows:
                alerts.append({
                    "id": row[0],
                    "message": row[1],
                    "level": row[2],
                    "created_at": row[3]
                })
                
            logger.info(f"✅ 获取系统告警成功: {len(alerts)} 条")
            return alerts
            
        except sqlite3.Error as e:
            logger.error(f"❌ 获取系统告警失败: {str(e)}")
            return []
        finally:
            conn.close()

    def add_backup_record(self, backup_path: str, version: str | None = None, size: int | None = None) -> int | None:
        """
        ➕ 添加备份记录
        
        参数:
            backup_path: 备份文件路径
            version: 系统版本
            size: 备份文件大小 (字节)
        返回:
            新增备份ID 或 None (失败)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO system_backups(backup_path, version, created_at, size) VALUES(?, ?, ?, ?)",
                (backup_path, version, datetime.now().isoformat(), size)
            )
            conn.commit()
            
            backup_id = cursor.lastrowid
            logger.info(f"✅ 系统备份记录添加成功: ID {backup_id}")
            return backup_id
            
        except sqlite3.Error as e:
            logger.error(f"❌ 添加备份记录失败: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_backup_records(self, limit: int | None = None) -> list[dict]:
        """
        🔍 获取备份记录
        
        参数:
            limit: 返回数量限制 (None表示全部)
        返回:
            备份记录列表
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if limit is not None:
                cursor.execute(
                    "SELECT id, backup_path, version, created_at, size FROM system_backups ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            else:
                cursor.execute(
                    "SELECT id, backup_path, version, created_at, size FROM system_backups ORDER BY created_at DESC"
                )
                
            rows = cursor.fetchall()
            
            backups = []
            for row in rows:
                backups.append({
                    "id": row[0],
                    "backup_path": row[1],
                    "version": row[2],
                    "created_at": row[3],
                    "size": row[4]
                })
                
            logger.info(f"✅ 获取备份记录成功: {len(backups)} 条")
            return backups
            
        except sqlite3.Error as e:
            logger.error(f"❌ 获取备份记录失败: {str(e)}")
            return []
        finally:
            conn.close()

    # ================================ 辅助方法 ================================

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _create_directories(self) -> None:
        """创建必要的目录结构"""
        for directory in [config.DB_DIR, config.UPLOADS_DIR, config.VECTOR_STORE_DIR, config.LOG_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

# 🌍 全局数据库管理实例
db_manager = DatabaseManager()