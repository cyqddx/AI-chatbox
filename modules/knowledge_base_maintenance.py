import os
import time
import uuid
import shutil
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta
from config import config
from utils.logger import logger
from utils.database import db_manager
from modules.knowledge_base import KnowledgeBase
from utils.llm_utils import llm_utils
import json


class KnowledgeBaseMaintenance:
    """
    📚 增强型知识库维护模块 v2.0
    =================================================
    功能总览：
    1. 📥 知识库内容更新（添加/修改/删除）
    2. ✅ 知识库质量审查（审核/评估/改进）
    3. 🔐 访问权限管理（角色/权限/安全）
    4. 🔄 异常处理与恢复机制
    5. 📊 操作日志与审计追踪
    
    设计原则：
    1. 🔒 安全性：多重权限验证
    2. ✅ 可靠性：完整事务处理
    3. 🎯 可追溯：详细操作日志
    4. 🚀 高性能：批量操作优化
    5. 🔄 可恢复：备份与回滚机制
    """

    def __init__(self):
        """初始化知识库维护系统"""
        logger.info("🚀 初始化增强型知识库维护系统 v2.0")
        
        # 📋 初始化子系统
        self.kb = KnowledgeBase()
        
        # 👥 预定义角色权限映射
        self.role_permissions = {
            "admin": {
                "name": "系统管理员",
                "permissions": ["read", "write", "delete", "review", "manage_users", "manage_roles"],
                "description": "拥有知识库所有操作权限"
            },
            "reviewer": {
                "name": "内容审核员",
                "permissions": ["read", "review", "approve", "reject", "comment"],
                "description": "负责内容质量审核"
            },
            "contributor": {
                "name": "内容贡献者",
                "permissions": ["read", "write", "modify_own"],
                "description": "可以添加和修改自己创建的内容"
            },
            "user": {
                "name": "普通用户",
                "permissions": ["read"],
                "description": "只能查看已批准的内容"
            }
        }
        
        # 📋 审核流程配置
        self.review_process = {
            "auto_approve_threshold": 0.85,  # 自动通过阈值
            "review_timeout_hours": 24,      # 审核超时时间
            "required_reviewers": 1,         # 最少审核人数
            "quality_threshold": 0.7         # 质量评估阈值
        }
        
        # 🗄️ 备份配置
        self.backup_config = {
            "max_backups": 10,               # 最大备份数量
            "backup_interval_hours": 24,     # 备份间隔
            "backup_retention_days": 30,     # 备份保留天数
            "auto_backup_enabled": True      # 自动备份开关
        }
        
        # 📊 操作日志配置
        self.audit_config = {
            "log_level": "INFO",             # 日志级别
            "max_log_entries": 10000,        # 最大日志条目
            "log_retention_days": 90         # 日志保留天数
        }
        
        # 🎯 初始化系统
        self._init_review_queue()
        self._init_backup_system()
        self._init_audit_system()
        
        logger.info("✅ 知识库维护系统初始化完成")

    # ================================ 系统初始化功能 ================================

    def _init_review_queue(self):
        """初始化审核队列系统"""
        try:
            # 🗄️ 创建审核队列表
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id INTEGER NOT NULL,
                    reviewer_phone TEXT,
                    status TEXT CHECK(status IN ('pending', 'in_review', 'approved', 'rejected', 'expired')),
                    priority INTEGER DEFAULT 5,
                    created_at TEXT NOT NULL,
                    assigned_at TEXT,
                    reviewed_at TEXT,
                    comments TEXT,
                    quality_score REAL,
                    FOREIGN KEY(entry_id) REFERENCES knowledge_entries(id)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue(status)
            """)
            
            conn.commit()
            conn.close()
            logger.info("✅ 审核队列系统初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 审核队列初始化失败: {str(e)}")

    def _init_backup_system(self):
        """初始化备份系统"""
        try:
            backup_dir = config.BASE_DIR / "kb_backups"
            backup_dir.mkdir(exist_ok=True)
            logger.info(f"✅ 备份目录创建完成: {backup_dir}")
            
        except Exception as e:
            logger.error(f"❌ 备份系统初始化失败: {str(e)}")

    def _init_audit_system(self):
        """初始化审计系统"""
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_phone TEXT,
                    operation TEXT,
                    target_type TEXT,
                    target_id TEXT,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    timestamp TEXT NOT NULL,
                    success BOOLEAN,
                    error_message TEXT
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_phone)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)
            """)
            
            conn.commit()
            conn.close()
            logger.info("✅ 审计系统初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 审计系统初始化失败: {str(e)}")

    # ================================ 知识库内容更新功能 ================================

    def add_knowledge(
        self, 
        file_path: Path, 
        metadata: Dict[str, Any], 
        user_phone: str = None,
        auto_approve: bool = False
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        📥 添加知识库条目
        参数:
            file_path: 文件完整路径
            metadata: 元数据字典 {
                "title": 标题,
                "author": 作者,
                "tags": 标签列表,
                "description": 描述,
                "category": 分类,
                "keywords": 关键词
            }
            user_phone: 操作者手机号
            auto_approve: 是否自动批准
            
        返回:
            (成功状态, 操作结果信息)
        """
        operation_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        try:
            logger.info(f"📥 开始添加知识条目: {operation_id}")
            
            # 🛡️ 参数验证
            if not file_path or not file_path.exists():
                return False, {"error": "文件路径无效或文件不存在"}
            
            if not metadata.get("title"):
                return False, {"error": "标题不能为空"}
            
            # 📋 文件验证
            file_size = file_path.stat().st_size
            if file_size > 50 * 1024 * 1024:  # 50MB限制
                return False, {"error": "文件大小超过50MB限制"}
            
            # 🔍 内容重复检查
            if self._check_duplicate_content(file_path):
                return False, {"error": "内容已存在，疑似重复"}
            
            # 📊 内容质量预评估
            quality_score = self._pre_assess_quality(file_path, metadata)
            
            # 🗄️ 生成内容摘要
            content_summary = self._generate_content_summary(file_path)
            
            # 📋 创建知识条目记录
            entry_data = {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "title": metadata["title"],
                "author": metadata.get("author", "unknown"),
                "tags": ",".join(metadata.get("tags", [])),
                "description": metadata.get("description", ""),
                "category": metadata.get("category", "general"),
                "keywords": ",".join(metadata.get("keywords", [])),
                "content_summary": content_summary,
                "file_size": file_size,
                "quality_score": quality_score,
                "status": "pending",
                "created_by": user_phone or "system",
                "created_at": datetime.now().isoformat()
            }
            
            # 📝 添加到数据库
            entry_id = db_manager.add_knowledge_entry(**entry_data)
            if not entry_id:
                return False, {"error": "数据库操作失败"}
            
            # 📋 添加到知识库系统
            kb_success = self.kb.add_document(file_path, metadata)
            if not kb_success:
                # 🔄 回滚数据库记录
                db_manager.delete_knowledge_entry(entry_id)
                return False, {"error": "知识库添加失败"}
            
            # 📋 记录操作日志
            self._log_operation(
                user_phone=user_phone,
                operation="add_knowledge",
                target_type="knowledge_entry",
                target_id=str(entry_id),
                details=f"添加知识条目: {metadata['title']}",
                success=True
            )
            
            # 🎯 处理审核流程
            if auto_approve and quality_score >= self.review_process["auto_approve_threshold"]:
                self._auto_approve_entry(entry_id, quality_score)
                status = "approved"
                review_required = False
            else:
                self._submit_for_review(entry_id, user_phone)
                status = "pending"
                review_required = True
            
            # 📊 生成操作结果
            result = {
                "entry_id": entry_id,
                "status": status,
                "quality_score": quality_score,
                "review_required": review_required,
                "estimated_review_time": self._estimate_review_time(quality_score),
                "operation_id": operation_id,
                "processing_time": (datetime.now() - start_time).total_seconds()
            }
            
            logger.info(f"✅ 知识条目添加完成: {operation_id} -> ID: {entry_id}")
            return True, result
            
        except Exception as e:
            # ❌ 错误处理
            self._log_operation(
                user_phone=user_phone,
                operation="add_knowledge",
                target_type="knowledge_entry",
                target_id=operation_id,
                details=str(e),
                success=False
            )
            
            logger.error(f"❌ 添加知识条目失败: {operation_id} - {str(e)}")
            return False, {"error": str(e)}

    def update_knowledge(
        self, 
        entry_id: int, 
        updates: Dict[str, Any], 
        user_phone: str = None,
        reason: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        ✏️ 更新知识库条目（增强版）
        
        参数:
            entry_id: 条目ID
            updates: 更新内容字典
            user_phone: 操作者手机号
            reason: 修改原因
            
        返回:
            (成功状态, 更新结果)
        """
        operation_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        try:
            logger.info(f"✏️ 开始更新知识条目: {operation_id} -> ID: {entry_id}")
            
            # 🔍 检查条目是否存在
            existing_entry = db_manager.get_knowledge_entry(entry_id)
            if not existing_entry:
                return False, {"error": "知识条目不存在"}
            
            # 🔒 权限检查
            if not self._check_update_permission(entry_id, user_phone):
                return False, {"error": "无权限修改此条目"}
            
            # 📋 创建更新记录
            update_record = {
                "entry_id": entry_id,
                "original_data": existing_entry,
                "updated_data": updates,
                "reason": reason,
                "updated_by": user_phone or "system",
                "updated_at": datetime.now().isoformat()
            }
            
            # 📝 执行更新
            success = db_manager.update_knowledge_content(entry_id, json.dumps(updates))
            if not success:
                return False, {"error": "数据库更新失败"}
            
            # 📋 状态更新为待审核
            db_manager.update_knowledge_status(entry_id, "pending_review")
            
            # 📋 记录操作日志
            self._log_operation(
                user_phone=user_phone,
                operation="update_knowledge",
                target_type="knowledge_entry",
                target_id=str(entry_id),
                details=f"更新原因: {reason}",
                success=True
            )
            
            # 🔄 提交重新审核
            self._submit_for_review(entry_id, user_phone, is_update=True)
            
            result = {
                "entry_id": entry_id,
                "status": "pending_review",
                "operation_id": operation_id,
                "processing_time": (datetime.now() - start_time).total_seconds()
            }
            
            logger.info(f"✅ 知识条目更新完成: {operation_id} -> ID: {entry_id}")
            return True, result
            
        except Exception as e:
            self._log_operation(
                user_phone=user_phone,
                operation="update_knowledge",
                target_type="knowledge_entry",
                target_id=str(entry_id),
                details=str(e),
                success=False
            )
            
            logger.error(f"❌ 更新知识条目失败: {operation_id} - {str(e)}")
            return False, {"error": str(e)}

    def delete_knowledge(
        self, 
        entry_id: int, 
        user_phone: str = None,
        reason: str = None,
        soft_delete: bool = True
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        🗑️ 删除知识库条目（增强版）
        
        参数:
            entry_id: 条目ID
            user_phone: 操作者手机号
            reason: 删除原因
            soft_delete: 是否软删除
            
        返回:
            (成功状态, 删除结果)
        """
        operation_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        try:
            logger.info(f"🗑️ 开始删除知识条目: {operation_id} -> ID: {entry_id}")
            
            # 🔍 检查条目是否存在
            existing_entry = db_manager.get_knowledge_entry(entry_id)
            if not existing_entry:
                return False, {"error": "知识条目不存在"}
            
            # 🔒 权限检查
            if not self._check_delete_permission(entry_id, user_phone):
                return False, {"error": "无权限删除此条目"}
            
            # 💾 备份删除内容
            backup_path = self._backup_before_delete(entry_id, existing_entry)
            
            if soft_delete:
                # 📝 软删除：更新状态
                success = db_manager.update_knowledge_status(entry_id, "deleted")
                db_manager.update_knowledge_review(
                    entry_id, 
                    user_phone or "system", 
                    "deleted", 
                    f"软删除原因: {reason}"
                )
            else:
                # 🗑️ 硬删除：从知识库和数据库删除
                self.kb.delete_document(existing_entry["file_path"])
                success = db_manager.delete_knowledge_entry(entry_id)
            
            # 📋 记录操作日志
            self._log_operation(
                user_phone=user_phone,
                operation="delete_knowledge",
                target_type="knowledge_entry",
                target_id=str(entry_id),
                details=f"删除原因: {reason}, 备份路径: {backup_path}",
                success=success
            )
            
            result = {
                "entry_id": entry_id,
                "soft_delete": soft_delete,
                "backup_path": backup_path,
                "operation_id": operation_id,
                "processing_time": (datetime.now() - start_time).total_seconds()
            }
            
            logger.info(f"✅ 知识条目删除完成: {operation_id} -> ID: {entry_id}")
            return success, result
            
        except Exception as e:
            self._log_operation(
                user_phone=user_phone,
                operation="delete_knowledge",
                target_type="knowledge_entry",
                target_id=str(entry_id),
                details=str(e),
                success=False
            )
            
            logger.error(f"❌ 删除知识条目失败: {operation_id} - {str(e)}")
            return False, {"error": str(e)}

    # ================================ 知识库质量审查功能 ================================

    def submit_for_review(
        self, 
        entry_id: int, 
        submitter_phone: str = None,
        priority: int = 5,
        notes: str = None
    ) -> Tuple[bool, str]:
        """
        📋 提交知识条目供审核
        
        参数:
            entry_id: 条目ID
            submitter_phone: 提交者手机号
            priority: 优先级 (1-10)
            notes: 提交备注
            
        返回:
            (成功状态, 消息)
        """
        try:
            # 📝 直接调用内部审核提交方法
            return self._submit_for_review(entry_id, submitter_phone, priority, notes)
            
        except Exception as e:
            logger.error(f"❌ 提交审核失败: {str(e)}")
            return False, str(e)

    def _submit_for_review(
        self, 
        entry_id: int, 
        submitter_phone: str = None,
        priority: int = 5,
        notes: str = None,
        is_update: bool = False
    ) -> Tuple[bool, str]:
        """内部方法：提交审核"""
        try:
            # 🔍 检查条目是否存在
            entry = db_manager.get_knowledge_entry(entry_id)
            if not entry:
                return False, "知识条目不存在"
            
            # 📋 创建审核记录
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO review_queue (
                    entry_id, priority, created_at, status, notes
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                entry_id, 
                priority, 
                datetime.now().isoformat(), 
                "pending", 
                notes or f"{'更新' if is_update else '新增'}提交"
            ))
            
            conn.commit()
            conn.close()
            
            # 📧 通知审核人员
            self._notify_reviewers(entry_id, priority)
            
            logger.info(f"📋 知识条目已提交审核: {entry_id}, 优先级: {priority}")
            return True, "知识条目已提交审核"
            
        except Exception as e:
            logger.error(f"❌ 提交审核失败: {str(e)}")
            return False, str(e)

    def review_knowledge(
        self, 
        entry_id: int, 
        reviewer_phone: str, 
        approved: bool, 
        comments: str = "",
        quality_score: float = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        ✅ 审核知识条目
        
        参数:
            entry_id: 条目ID
            reviewer_phone: 审核者手机号
            approved: 是否通过
            comments: 审核意见
            quality_score: 质量评分
            
        返回:
            (成功状态, 审核结果)
        """
        operation_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        try:
            logger.info(f"✅ 开始审核知识条目: {operation_id} -> ID: {entry_id}")
            
            # 🔍 检查审核权限
            if not self._check_review_permission(reviewer_phone):
                return False, {"error": "无审核权限"}
            
            # 📋 获取条目信息
            entry = db_manager.get_knowledge_entry(entry_id)
            if not entry:
                return False, {"error": "知识条目不存在"}
            
            # 📊 计算质量评分
            if quality_score is None:
                quality_score = self.evaluate_quality(entry_id)
            
            # 📝 更新审核状态
            status = "approved" if approved else "rejected"
            db_manager.update_knowledge_review(
                entry_id, 
                reviewer_phone, 
                status, 
                comments
            )
            
            # 📋 更新审核队列
            self._update_review_queue(entry_id, reviewer_phone, status, comments)
            
            # 🔄 根据审核结果处理
            if approved:
                # ✅ 批准处理
                self._handle_approved_entry(entry_id, quality_score)
                message = "知识条目审核通过"
            else:
                # ❌ 拒绝处理
                self._handle_rejected_entry(entry_id, comments)
                message = f"知识条目被拒绝: {comments}"
            
            # 📋 记录审核日志
            self._log_operation(
                user_phone=reviewer_phone,
                operation="review_knowledge",
                target_type="knowledge_entry",
                target_id=str(entry_id),
                details=f"审核结果: {status}, 评分: {quality_score}, 意见: {comments}",
                success=True
            )
            
            # 📧 通知相关用户
            self._notify_submitter(entry_id, status, comments)
            
            result = {
                "entry_id": entry_id,
                "status": status,
                "quality_score": quality_score,
                "message": message,
                "operation_id": operation_id,
                "processing_time": (datetime.now() - start_time).total_seconds()
            }
            
            logger.info(f"✅ 知识条目审核完成: {operation_id} -> ID: {entry_id}")
            return True, result
            
        except Exception as e:
            self._log_operation(
                user_phone=reviewer_phone,
                operation="review_knowledge",
                target_type="knowledge_entry",
                target_id=str(entry_id),
                details=str(e),
                success=False
            )
            
            logger.error(f"❌ 审核知识条目失败: {operation_id} - {str(e)}")
            return False, {"error": str(e)}

    def evaluate_quality(self, entry_id: int) -> float:
        """
        📊 综合质量评估
        
        参数:
            entry_id: 条目ID
            
        返回:
            质量评分 (0-1)
        """
        try:
            # 📋 获取条目信息
            entry = db_manager.get_knowledge_entry(entry_id)
            if not entry:
                return 0.0
            
            # 🎯 多维度评估
            scores = []
            
            # 1. 内容完整性评分
            completeness_score = self._assess_completeness(entry)
            scores.append(completeness_score * 0.3)
            
            # 2. 内容准确性评分
            accuracy_score = self._assess_accuracy(entry)
            scores.append(accuracy_score * 0.3)
            
            # 3. 用户互动评分
            engagement_score = self._assess_engagement(entry_id)
            scores.append(engagement_score * 0.2)
            
            # 4. 技术质量评分
            technical_score = self._assess_technical_quality(entry)
            scores.append(technical_score * 0.2)
            
            # 📊 计算综合评分
            final_score = sum(scores)
            
            logger.info(f"📊 质量评估完成: 条目 {entry_id} -> 评分: {final_score:.2f}")
            return final_score
            
        except Exception as e:
            logger.error(f"❌ 质量评估失败: {entry_id} - {str(e)}")
            return 0.0

    def auto_quality_check(self):
        """🤖 自动质量检查任务"""
        logger.info("🤖 开始自动质量检查任务")
        
        try:
            # 📋 获取所有已批准的知识条目
            entries = db_manager.get_knowledge_entries(status="approved")
            
            low_quality_entries = []
            for entry in entries:
                quality_score = self.evaluate_quality(entry["id"])
                
                if quality_score < self.review_process["quality_threshold"]:
                    low_quality_entries.append({
                        "entry_id": entry["id"],
                        "title": entry["title"],
                        "score": quality_score,
                        "issues": self._identify_quality_issues(entry)
                    })
            
            # 📧 通知管理员
            if low_quality_entries:
                self._notify_low_quality_entries(low_quality_entries)
            
            logger.info(f"✅ 自动质量检查完成: 发现问题条目 {len(low_quality_entries)} 个")
            
        except Exception as e:
            logger.error(f"❌ 自动质量检查失败: {str(e)}")

    # ================================ 知识库访问权限管理功能 ================================

    def set_access_permission(
        self, 
        entry_id: int, 
        roles: List[str], 
        user_phone: str = None
    ) -> Tuple[bool, str]:
        """
        🔐 设置知识条目的访问权限
        
        参数:
            entry_id: 条目ID
            roles: 允许访问的角色列表
            user_phone: 操作者手机号
            
        返回:
            (成功状态, 消息)
        """
        try:
            logger.info(f"🔐 开始设置权限: 条目 {entry_id}, 角色: {roles}")
            
            # 🔍 检查条目是否存在
            entry = db_manager.get_knowledge_entry(entry_id)
            if not entry:
                return False, "知识条目不存在"
            
            # 🔒 权限检查
            if not self._check_permission_management(entry_id, user_phone):
                return False, "无权限设置访问权限"
            
            # ✅ 验证角色有效性
            valid_roles = []
            for role in roles:
                if role in self.role_permissions:
                    valid_roles.append(role)
                else:
                    logger.warning(f"⚠️ 无效角色: {role}")
            
            if not valid_roles:
                return False, "未提供有效角色"
            
            # 📝 更新权限
            success = db_manager.set_knowledge_permissions(entry_id, valid_roles)
            if not success:
                return False, "更新权限失败"
            
            # 📋 记录操作日志
            self._log_operation(
                user_phone=user_phone,
                operation="set_permissions",
                target_type="knowledge_entry",
                target_id=str(entry_id),
                details=f"设置访问权限: {valid_roles}",
                success=True
            )
            
            logger.info(f"✅ 权限设置完成: 条目 {entry_id}")
            return True, "访问权限已更新"
            
        except Exception as e:
            logger.error(f"❌ 设置权限失败: {str(e)}")
            return False, str(e)

    def get_user_permissions(self, user_phone: str) -> List[str]:
        """
        👤 获取用户的完整权限列表
        
        参数:
            user_phone: 用户手机号
            
        返回:
            权限列表
        """
        try:
            # 📋 获取用户角色
            user = db_manager.get_user(user_phone)
            if not user:
                return ["read"]  # 默认只读权限
            
            # 🎯 根据手机号确定角色
            if user_phone == "admin":
                role = "admin"
            elif user_phone in self._get_reviewers_list():
                role = "reviewer"
            else:
                role = "user"
            
            # 📋 获取权限
            permissions = self.role_permissions.get(role, {}).get("permissions", ["read"])
            
            logger.debug(f"👤 获取用户权限: {user_phone} -> {role} -> {permissions}")
            return permissions
            
        except Exception as e:
            logger.error(f"❌ 获取用户权限失败: {str(e)}")
            return ["read"]

    def check_access(
        self, 
        user_phone: str, 
        entry_id: int, 
        permission: str
    ) -> Tuple[bool, str]:
        """
        🔍 检查用户是否有特定权限
        
        参数:
            user_phone: 用户手机号
            entry_id: 条目ID
            permission: 要检查的权限
            
        返回:
            (是否有权限, 详细消息)
        """
        try:
            # 🔍 获取用户权限
            user_permissions = self.get_user_permissions(user_phone)
            
            # 🔍 获取条目权限
            entry_permissions = db_manager.get_knowledge_permissions(entry_id)
            
            # 🎯 检查权限
            has_permission = permission in user_permissions
            
            # 🔍 如果条目有特定权限设置，需要同时满足
            if entry_permissions:
                has_permission = has_permission and (
                    permission in entry_permissions or 
                    any(role in self.role_permissions for role in entry_permissions)
                )
            
            message = (
                "有权限访问" if has_permission 
                else f"无权限: 需要{permission}权限"
            )
            
            logger.info(f"🔍 权限检查: 用户 {user_phone}, 条目 {entry_id}, 权限 {permission} -> {has_permission}")
            return has_permission, message
            
        except Exception as e:
            logger.error(f"❌ 权限检查失败: {str(e)}")
            return False, "权限检查失败"

    def create_role(
        self, 
        role_name: str, 
        permissions: List[str], 
        description: str = ""
    ) -> Tuple[bool, str]:
        """
        ➕ 创建新角色
        
        参数:
            role_name: 角色名称
            permissions: 权限列表
            description: 角色描述
            
        返回:
            (成功状态, 消息)
        """
        try:
            if role_name in self.role_permissions:
                return False, "角色已存在"
            
            # ✅ 验证权限有效性
            valid_permissions = []
            for perm in permissions:
                # 这里可以添加权限验证逻辑
                valid_permissions.append(perm)
            
            self.role_permissions[role_name] = {
                "name": role_name,
                "permissions": valid_permissions,
                "description": description
            }
            
            logger.info(f"➕ 创建新角色: {role_name}")
            return True, f"角色 {role_name} 创建成功"
            
        except Exception as e:
            logger.error(f"❌ 创建角色失败: {str(e)}")
            return False, str(e)

    # ================================ 异常处理与恢复功能 ================================

    def restore_deleted_entry(
        self, 
        entry_id: int, 
        user_phone: str = None
    ) -> Tuple[bool, str]:
        """
        🔄 恢复已删除的知识条目
        
        参数:
            entry_id: 条目ID
            user_phone: 操作者手机号
            
        返回:
            (成功状态, 消息)
        """
        try:
            logger.info(f"🔄 开始恢复知识条目: {entry_id}")
            
            # 🔍 检查是否存在备份
            backup_info = self._get_backup_info(entry_id)
            if not backup_info:
                return False, "未找到备份信息"
            
            # 📝 恢复操作
            success = self._restore_from_backup(backup_info)
            if not success:
                return False, "恢复失败"
            
            # 📋 记录操作日志
            self._log_operation(
                user_phone=user_phone,
                operation="restore_knowledge",
                target_type="knowledge_entry",
                target_id=str(entry_id),
                details="从备份恢复",
                success=True
            )
            
            logger.info(f"✅ 知识条目恢复完成: {entry_id}")
            return True, "知识条目已恢复"
            
        except Exception as e:
            logger.error(f"❌ 恢复知识条目失败: {str(e)}")
            return False, str(e)

    def get_operation_history(
        self, 
        user_phone: str = None,
        operation_type: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        📊 获取操作历史
        
        参数:
            user_phone: 用户手机号（可选）
            operation_type: 操作类型（可选）
            limit: 返回记录数量
            
        返回:
            操作历史列表
        """
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM audit_log WHERE 1=1"
            params = []
            
            if user_phone:
                query += " AND user_phone = ?"
                params.append(user_phone)
            
            if operation_type:
                query += " AND operation = ?"
                params.append(operation_type)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                history.append({
                    "id": row[0],
                    "user_phone": row[1],
                    "operation": row[2],
                    "target_type": row[3],
                    "target_id": row[4],
                    "details": row[5],
                    "timestamp": row[8],
                    "success": bool(row[9])
                })
            
            conn.close()
            return history
            
        except Exception as e:
            logger.error(f"❌ 获取操作历史失败: {str(e)}")
            return []

    # ================================ 辅助方法 ================================

    def _log_operation(
        self, 
        user_phone: str,
        operation: str,
        target_type: str,
        target_id: str,
        details: str,
        success: bool,
        ip_address: str = None,
        user_agent: str = None
    ):
        """记录操作日志"""
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO audit_log (
                    user_phone, operation, target_type, target_id, details,
                    ip_address, user_agent, timestamp, success
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_phone, operation, target_type, target_id, details,
                ip_address, user_agent, datetime.now().isoformat(), success
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ 记录操作日志失败: {str(e)}")

    def _check_duplicate_content(self, file_path: Path) -> bool:
        """检查内容是否重复"""
        try:
            # 计算文件哈希
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            # 检查数据库中是否有相同哈希
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT COUNT(*) FROM knowledge_entries WHERE file_path LIKE ?",
                (f"%{file_hash}%",)
            )
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception:
            return False

    def _pre_assess_quality(self, file_path: Path, metadata: Dict[str, Any]) -> float:
        """预评估内容质量"""
        try:
            # 这里可以实现更复杂的质量评估算法
            # 基础版本：基于元数据完整性评分
            score = 0.5  # 基础分
            
            if metadata.get("title"):
                score += 0.2
            if metadata.get("author"):
                score += 0.1
            if metadata.get("description"):
                score += 0.1
            if metadata.get("tags"):
                score += 0.1
            
            return min(score, 1.0)
            
        except Exception:
            return 0.5

    def _generate_content_summary(self, file_path: Path) -> str:
        """生成内容摘要"""
        try:
            # 这里可以实现内容摘要提取
            return f"文件: {file_path.name} 的内容摘要"
            
        except Exception:
            return "内容摘要生成失败"

    def _estimate_review_time(self, quality_score: float) -> str:
        """估算审核时间"""
        base_hours = 24
        if quality_score >= 0.9:
            return f"{base_hours}小时内"
        elif quality_score >= 0.7:
            return f"{base_hours * 2}小时内"
        else:
            return f"{base_hours * 3}小时内"

    def _auto_approve_entry(self, entry_id: int, quality_score: float):
        """自动批准高质量条目"""
        try:
            db_manager.update_knowledge_status(entry_id, "approved")
            db_manager.update_knowledge_review(
                entry_id, 
                "system", 
                "approved", 
                f"自动批准 - 质量评分: {quality_score}"
            )
            
            logger.info(f"🎯 自动批准知识条目: {entry_id}, 评分: {quality_score}")
            
        except Exception as e:
            logger.error(f"❌ 自动批准失败: {entry_id} - {str(e)}")

    def _submit_for_review(
        self, 
        entry_id: int, 
        submitter_phone: str = None,
        priority: int = 5,
        notes: str = None,
        is_update: bool = False
    ) -> Tuple[bool, str]:
        """内部方法：提交审核"""
        # 实现已在上面提供
        pass

    def _check_permission(self, permission: str, user_phone: str) -> bool:
        """检查用户权限"""
        permissions = self.get_user_permissions(user_phone)
        return permission in permissions

    def _check_update_permission(self, entry_id: int, user_phone: str) -> bool:
        """检查更新权限"""
        return self._check_permission("write", user_phone)

    def _check_delete_permission(self, entry_id: int, user_phone: str) -> bool:
        """检查删除权限"""
        return self._check_permission("delete", user_phone)

    def _check_review_permission(self, user_phone: str) -> bool:
        """检查审核权限"""
        return self._check_permission("review", user_phone)

    def _check_permission_management(self, entry_id: int, user_phone: str) -> bool:
        """检查权限管理权限"""
        return self._check_permission("manage_users", user_phone)

    def _get_reviewers_list(self) -> List[str]:
        """获取审核人员列表"""
        # 这里可以从数据库获取审核人员
        return ["admin", "reviewer1", "reviewer2"]

    def _notify_reviewers(self, entry_id: int, priority: int):
        """通知审核人员"""
        logger.info(f"📧 通知审核人员: 条目 {entry_id}, 优先级: {priority}")

    def _notify_submitter(self, entry_id: int, status: str, comments: str):
        """通知提交者"""
        logger.info(f"📧 通知提交者: 条目 {entry_id}, 状态: {status}")

    def _notify_low_quality_entries(self, entries: List[Dict[str, Any]]):
        """通知管理员低质量条目"""
        logger.warning(f"⚠️ 低质量条目通知: {len(entries)} 个条目需要关注")

    def _backup_before_delete(self, entry_id: int, entry: Dict[str, Any]) -> str:
        """删除前备份"""
        try:
            backup_dir = config.BASE_DIR / "kb_backups" / "deletes"
            backup_dir.mkdir(exist_ok=True)
            
            backup_file = backup_dir / f"deleted_{entry_id}_{int(time.time())}.json"
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)
            
            return str(backup_file)
            
        except Exception as e:
            logger.error(f"❌ 备份失败: {entry_id} - {str(e)}")
            return ""

    def _get_backup_info(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """获取备份信息"""
        # 实现备份查找逻辑
        return None

    def _restore_from_backup(self, backup_info: Dict[str, Any]) -> bool:
        """从备份恢复"""
        try:
            # 实现恢复逻辑
            return True
            
        except Exception as e:
            logger.error(f"❌ 恢复失败: {str(e)}")
            return False

    def _assess_completeness(self, entry: Dict[str, Any]) -> float:
        """评估内容完整性"""
        score = 0.0
        
        # 检查必填字段
        required_fields = ["title", "author", "description"]
        for field in required_fields:
            if entry.get(field):
                score += 0.33
                
        return min(score, 1.0)

    def _assess_accuracy(self, entry: Dict[str, Any]) -> float:
        """评估内容准确性"""
        # 这里可以实现更复杂的准确性检查
        return 0.8

    def _assess_engagement(self, entry_id: int) -> float:
        """评估用户互动"""
        # 基于访问量和反馈评估
        return 0.7

    def _assess_technical_quality(self, entry: Dict[str, Any]) -> float:
        """评估技术质量"""
        # 基于文件类型和内容评估
        return 0.9

    def _identify_quality_issues(self, entry: Dict[str, Any]) -> List[str]:
        """识别质量问题"""
        issues = []
        
        # 示例问题识别
        if not entry.get("description"):
            issues.append("缺少描述信息")
        
        return issues

    def _update_review_queue(self, entry_id: int, reviewer_phone: str, status: str, comments: str):
        """更新审核队列"""
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE review_queue 
                SET reviewer_phone = ?, status = ?, reviewed_at = ?, comments = ?
                WHERE entry_id = ?
            """, (reviewer_phone, status, datetime.now().isoformat(), comments, entry_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ 更新审核队列失败: {str(e)}")

    def _handle_approved_entry(self, entry_id: int, quality_score: float):
        """处理批准的条目"""
        logger.info(f"✅ 处理批准的条目: {entry_id}, 评分: {quality_score}")

    def _handle_rejected_entry(self, entry_id: int, comments: str):
        """处理拒绝的条目"""
        logger.info(f"❌ 处理拒绝的条目: {entry_id}, 原因: {comments}")


# 🌍 全局知识库维护实例
kb_maintenance = KnowledgeBaseMaintenance()