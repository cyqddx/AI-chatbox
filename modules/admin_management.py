"""
🎓 近屿智能课程助手 - 系统管理后台
功能：集成增强版知识库维护模块的完整管理界面
版本：v2.2 - 最终修复版
最后更新：2025-08-21
"""

import gradio as gr
import sqlite3
import uuid
import os
import shutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple
import json
import pandas as pd

# 导入系统模块
from utils.database import db_manager
from utils.logger import logger
from config import config
from modules.knowledge_base_maintenance import kb_maintenance
from modules.knowledge_base import KnowledgeBase
from modules.system_maintenance import SystemMaintenance


class AdminManager:
    """
    🔧 增强型系统管理员类
    新增功能：
    1. 📚 知识库管理增强版
    2. ✅ 内容审核工作流
    3. 🔐 权限管理界面
    4. 📊 质量监控仪表板
    5. 🔄 异常恢复机制
    """
    
    def __init__(self):
        """初始化"""
        logger.info("🚀 初始化增强型系统管理员管理器 v2.2...")
        
        # 初始化子系统
        self.kb_maintenance = kb_maintenance  # 使用增强版
        self.kb_system = KnowledgeBase()
        self.sys_maintenance = SystemMaintenance()
        
        # 管理员配置
        self.admin_phone = "admin"
        self.admin_pwd = "123456"
        
        # 邮件配置
        self.smtp_config = {
            "server": None,
            "port": 587,
            "username": None,
            "password": None,
            "enabled": False
        }
        
        # 初始化管理员
        self._init_admin_account()
        
        logger.info("✅ 增强型系统管理员管理器初始化完成")

    # ================================ 管理员账户 ================================

    def _init_admin_account(self):
        """初始化管理员账户"""
        logger.info("🔍 初始化管理员账户...")
        
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            # 检查admin用户是否存在
            cursor.execute("SELECT phone FROM users WHERE phone = ?", (self.admin_phone,))
            exists = cursor.fetchone()
            
            if not exists:
                # 创建管理员账户
                cursor.execute(
                    "INSERT INTO users(phone, pwd, name, role) VALUES(?, ?, ?, ?)",
                    (self.admin_phone, self.admin_pwd, "系统管理员", 1)
                )
                conn.commit()
                logger.info("✅ 管理员账户创建成功")
            else:
                # 确保是管理员
                cursor.execute(
                    "UPDATE users SET role = 1 WHERE phone = ?",
                    (self.admin_phone,)
                )
                conn.commit()
                logger.info("✅ 管理员账户权限已更新")
                
        except Exception as e:
            logger.error(f"❌ 管理员账户初始化失败: {str(e)}")
        finally:
            conn.close()

    def admin_login(self, phone: str, password: str) -> Tuple[bool, str]:
        """管理员专用登录验证"""
        try:
            logger.info(f"🧩 管理员登录验证: {phone}")
            
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            # 查询用户信息（包含所有字段）
            cursor.execute(
                "SELECT phone, pwd, name, role FROM users WHERE phone = ?",
                (phone,)
            )
            user = cursor.fetchone()
            conn.close()
            
            if not user:
                return False, "用户不存在"
            
            phone_db, pwd_db, name_db, role_db = user
            
            # 验证密码和角色
            if pwd_db != password:
                return False, "密码错误"
            
            if role_db != 1:
                return False, "非管理员权限"
            
            logger.info(f"✅ 管理员登录成功: {phone}")
            return True, "登录成功"
            
        except Exception as e:
            logger.error(f"❌ 管理员登录验证失败: {str(e)}")
            return False, "登录验证失败"

    # ================================ 用户管理功能 ================================

    def get_all_users(self) -> pd.DataFrame:
        """获取所有用户（返回DataFrame）"""
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT phone, name, role, 
                    (SELECT COUNT(*) FROM sessions WHERE phone = users.phone) as session_count,
                    (SELECT COUNT(*) FROM messages WHERE sid IN 
                        (SELECT sid FROM sessions WHERE phone = users.phone)) as message_count
                FROM users
                ORDER BY phone
            """)
            
            columns = ["手机号", "用户名", "角色代码", "会话数", "消息数"]
            data = cursor.fetchall()
            
            if not data:  # 🎯 添加空数据检查
                # 返回有表头的空DataFrame
                return pd.DataFrame(columns=columns)
            
            # 格式化角色
            formatted_data = []
            for row in data:
                formatted_row = list(row)
                formatted_row[2] = "管理员" if row[2] == 1 else "普通用户"
                formatted_data.append(formatted_row)
            
            conn.close()
            return pd.DataFrame(formatted_data, columns=columns)
            
        except Exception as e:
            logger.error(f"❌ 获取用户列表失败: {str(e)}")
            return pd.DataFrame(columns=["手机号", "用户名", "角色代码", "会话数", "消息数"])

    def add_user(self, phone: str, name: str, role: int = 0) -> Tuple[bool, str]:
        """添加新用户"""
        try:
            # 验证手机号格式
            if not (phone.isdigit() and len(phone) == 11):
                return False, "请输入有效的11位手机号"
            
            # 检查用户是否已存在
            if db_manager.get_user(phone):
                return False, "该手机号已存在"
            
            # 添加用户（默认密码123456）
            success, message = db_manager.add_user(phone, "123456", name)
            if success and role == 1:
                # 设置为管理员
                db_manager.update_user_role(phone, 1)
            
            return success, message
            
        except Exception as e:
            return False, f"添加用户失败: {str(e)}"
    
    def update_user_role(self, phone: str, role: int) -> Tuple[bool, str]:
        """更新用户角色"""
        try:
            if not db_manager.get_user(phone):
                return False, "用户不存在"
            
            success = db_manager.update_user_role(phone, role)
            role_name = "管理员" if role == 1 else "普通用户"
            
            return success, f"用户角色已更新为: {role_name}"
            
        except Exception as e:
            return False, f"更新用户角色失败: {str(e)}"
    
    def delete_user(self, phone: str) -> Tuple[bool, str]:
        """删除用户及其所有数据"""
        try:
            if not db_manager.get_user(phone):
                return False, "用户不存在"
            
            # 删除用户的所有会话和消息
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            # 获取用户的会话ID
            cursor.execute("SELECT sid FROM sessions WHERE phone = ?", (phone,))
            sessions = cursor.fetchall()
            
            # 删除相关数据
            for session in sessions:
                sid = session[0]
                cursor.execute("DELETE FROM messages WHERE sid = ?", (sid,))
                cursor.execute("DELETE FROM files WHERE sid = ?", (sid,))
            
            cursor.execute("DELETE FROM sessions WHERE phone = ?", (phone,))
            cursor.execute("DELETE FROM users WHERE phone = ?", (phone,))
            
            conn.commit()
            conn.close()
            
            return True, "用户及其所有数据已删除"
            
        except Exception as e:
            return False, f"删除用户失败: {str(e)}"

    # ================================ 增强版知识库管理功能 ================================

    def get_all_knowledge_entries(self) -> pd.DataFrame:
        """获取知识库条目"""
        try:
            entries = db_manager.get_knowledge_entries()
            if not entries:
                return pd.DataFrame(columns=[
                    'ID', '文件名', '标题', '作者', '标签', '状态', '审核人', 
                    '创建时间', '更新时间', '质量评分', '访问权限'
                ])
            
            # 转换为DataFrame
            df = pd.DataFrame(entries)
            if df.empty:
                return pd.DataFrame(columns=[
                    'ID', '文件名', '标题', '作者', '标签', '状态', '审核人', 
                    '创建时间', '更新时间', '质量评分', '访问权限'
                ])
            
            # 添加质量评分
            df['质量评分'] = df.apply(lambda row: self.kb_maintenance.evaluate_quality(row['id']), axis=1)
            
            # 格式化状态
            status_map = {
                'pending': '待审核',
                'pending_review': '审核中',
                'approved': '已批准',
                'rejected': '已拒绝',
                'deleted': '已删除'
            }
            df['状态'] = df['status'].map(status_map)
            
            # 获取访问权限
            df['访问权限'] = df.apply(lambda row: ",".join(
                db_manager.get_knowledge_permissions(row['id']) or ['user']
            ), axis=1)
            
            # 选择并重命名列
            df = df[[
                'id', 'file_name', 'title', 'author', 'tags', '状态', 
                'reviewer', 'created_at', 'updated_at', '质量评分', '访问权限'
            ]]
            df.columns = [
                'ID', '文件名', '标题', '作者', '标签', '状态', '审核人', 
                '创建时间', '更新时间', '质量评分', '访问权限'
            ]
            
            return df
            
        except Exception as e:
            logger.error(f"❌ 获取知识库条目失败: {str(e)}")
            return pd.DataFrame(columns=[
                'ID', '文件名', '标题', '作者', '标签', '状态', '审核人', 
                '创建时间', '更新时间', '质量评分', '访问权限'
            ])

    def add_knowledge_entry_admin(
        self, 
        file_path: str, 
        title: str, 
        author: str, 
        tags: str,
        description: str = "",
        category: str = "general",
        auto_approve: bool = False
    ) -> Tuple[bool, str]:
        """管理员添加知识库条目"""
        try:
            path = Path(file_path)
            if not path.exists():
                return False, "文件不存在"
            
            # 解析标签
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            
            # 添加知识条目
            success, result = self.kb_maintenance.add_knowledge(
                file_path=path,
                metadata={
                    "title": title,
                    "author": author,
                    "tags": tag_list,
                    "description": description,
                    "category": category
                },
                user_phone="admin",
                auto_approve=auto_approve
            )
            
            if success:
                return True, f"知识条目添加成功 (ID: {result['entry_id']})"
            else:
                return False, result.get("error", "添加失败")
            
        except Exception as e:
            return False, f"添加知识条目失败: {str(e)}"

    def update_knowledge_status_admin(
        self, 
        entry_id: int, 
        status: str, 
        reviewer: str = None, 
        comments: str = ""
    ) -> Tuple[bool, str]:
        """管理员更新知识条目状态"""
        try:
            success, result = self.kb_maintenance.review_knowledge(
                entry_id=entry_id,
                reviewer_phone="admin",
                approved=(status == "approved"),
                comments=comments
            )
            
            if success:
                return True, f"状态已更新为: {status}"
            else:
                return False, result.get("error", "更新失败")
            
        except Exception as e:
            return False, f"更新状态失败: {str(e)}"

    def delete_knowledge_entry_admin(self, entry_id: int, reason: str = "") -> Tuple[bool, str]:
        """管理员删除知识条目"""
        try:
            success, result = self.kb_maintenance.delete_knowledge(
                entry_id=entry_id,
                user_phone="admin",
                reason=reason or "管理员删除",
                soft_delete=True
            )
            
            if success:
                return True, "知识条目已删除"
            else:
                return False, result.get("error", "删除失败")
            
        except Exception as e:
            return False, f"删除知识条目失败: {str(e)}"

    def get_knowledge_quality_report(self) -> pd.DataFrame:
        """获取知识库质量报告"""
        try:
            entries = db_manager.get_knowledge_entries()
            if not entries:
                return pd.DataFrame(columns=['条目ID', '标题', '状态', '质量评分', '问题描述'])
            
            quality_data = []
            for entry in entries:
                quality_score = self.kb_maintenance.evaluate_quality(entry['id'])
                issues = self.kb_maintenance._identify_quality_issues(entry)
                
                quality_data.append({
                    '条目ID': entry['id'],
                    '标题': entry['title'],
                    '状态': entry['status'],
                    '质量评分': f"{quality_score:.2f}",
                    '问题描述': "; ".join(issues) if issues else "无问题"
                })
            
            return pd.DataFrame(quality_data)
            
        except Exception as e:
            logger.error(f"❌ 获取质量报告失败: {str(e)}")
            return pd.DataFrame(columns=['条目ID', '标题', '状态', '质量评分', '问题描述'])

    # ================================ 权限管理功能 ================================

    def get_knowledge_permissions(self, entry_id: int) -> List[str]:
        """获取知识条目权限"""
        try:
            return db_manager.get_knowledge_permissions(entry_id)
        except Exception:
            return []

    def set_knowledge_permissions_admin(
        self, 
        entry_id: int, 
        roles_input: str
    ) -> Tuple[bool, str]:
        """管理员设置知识条目权限"""
        try:
            role_list = [role.strip() for role in roles_input.split(",") if role.strip()]
            
            success, message = self.kb_maintenance.set_access_permission(
                entry_id=entry_id,
                roles=role_list,
                user_phone="admin"
            )
            
            return success, message
            
        except Exception as e:
            return False, f"设置权限失败: {str(e)}"

    def get_available_roles(self) -> List[str]:
        """获取可用角色列表"""
        return list(self.kb_maintenance.role_permissions.keys())

    # ================================ 系统监控功能 ================================

    def get_system_metrics(self) -> Dict[str, str]:
        """获取系统监控指标"""
        return self.sys_maintenance.get_system_metrics()

    def get_system_alerts(self) -> pd.DataFrame:
        """获取系统告警（增强版）"""
        try:
            alerts = db_manager.get_system_alerts(limit=50)
            if not alerts:
                return pd.DataFrame(columns=['ID', '消息', '级别', '时间', '状态'])
            
            df = pd.DataFrame(alerts)
            if df.empty:
                return pd.DataFrame(columns=['ID', '消息', '级别', '时间', '状态'])
            
            df['ID'] = df['id']
            df['消息'] = df['message']
            df['级别'] = df['level']
            df['时间'] = df['created_at'].str[:19]
            
            # 添加状态指示
            level_map = {
                'info': '正常',
                'warning': '警告',
                'error': '错误',
                'critical': '严重'
            }
            df['状态'] = df['level'].map(level_map)
            
            return df[['ID', '消息', '级别', '时间', '状态']]
            
        except Exception as e:
            logger.error(f"❌ 获取告警记录失败: {str(e)}")
            return pd.DataFrame(columns=['ID', '消息', '级别', '时间', '状态'])

    # ================================ 数据备份与恢复功能 ================================

    def backup_data(self) -> Tuple[bool, str, str]:
        """执行数据备份"""
        return self.sys_maintenance.backup_data()

    def restore_data(self, backup_file: str) -> Tuple[bool, str]:
        """从备份恢复数据"""
        backup_path = Path(backup_file)
        return self.sys_maintenance.restore_data(backup_path)

    def get_backup_files(self) -> pd.DataFrame:
        """获取备份文件（增强版）"""
        try:
            backups = db_manager.get_backup_records(limit=20)
            if not backups:
                return pd.DataFrame(columns=['ID', '文件名', '版本', '创建时间', '大小(MB)', '状态'])
            
            df = pd.DataFrame(backups)
            if df.empty:
                return pd.DataFrame(columns=['ID', '文件名', '版本', '创建时间', '大小(MB)', '状态'])
            
            df['版本'] = df['version']
            df['ID'] = df['id']
            df['文件名'] = df['backup_path'].apply(lambda x: Path(x).name)
            df['大小(MB)'] = (df['size'] / 1024 / 1024).round(2)
            df['创建时间'] = df['created_at'].str[:19]
            df['状态'] = '可用'
            
            return df[['ID', '文件名', '版本', '创建时间', '大小(MB)', '状态']]
            
        except Exception as e:
            logger.error(f"❌ 获取备份文件失败: {str(e)}")
            return pd.DataFrame(columns=['ID', '文件名', '版本', '创建时间', '大小(MB)', '状态'])

    # ================================ 邮件配置功能 ================================

    def configure_email(self, server: str, port: int, username: str, password: str) -> Tuple[bool, str]:
        """配置邮件服务器"""
        try:
            self.smtp_config.update({
                "server": server,
                "port": port,
                "username": username,
                "password": password,
                "enabled": True
            })
            return True, "邮件服务器配置成功"
        except Exception as e:
            return False, f"邮件配置失败: {str(e)}"

    def send_test_email(self, recipient: str, subject: str, message: str) -> Tuple[bool, str]:
        """发送测试邮件"""
        try:
            if not self.smtp_config["enabled"]:
                return False, "邮件服务器未配置"
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config["username"]
            msg['To'] = recipient
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain'))
            
            # 发送邮件
            server = smtplib.SMTP(self.smtp_config["server"], self.smtp_config["port"])
            server.starttls()
            server.login(self.smtp_config["username"], self.smtp_config["password"])
            server.send_message(msg)
            server.quit()
            
            return True, "测试邮件发送成功"
            
        except Exception as e:
            return False, f"邮件发送失败: {str(e)}"

    # ================================ 数据库管理功能 ================================

    def get_all_tables_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有数据库表的数据"""
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            all_data = {}
            
            for table in tables:
                table_name = table[0]
                
                # 获取列名
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                # 获取数据
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 100")
                rows = cursor.fetchall()
                
                # 格式化数据
                table_data = []
                for row in rows:
                    row_dict = {}
                    for i, value in enumerate(row):
                        row_dict[column_names[i]] = value
                    table_data.append(row_dict)
                
                all_data[table_name] = table_data
            
            conn.close()
            return all_data
            
        except Exception as e:
            logger.error(f"❌ 获取表数据失败: {str(e)}")
            return {}

    def execute_sql_query(self, query: str) -> Tuple[bool, str, Any]:
        """执行SQL查询"""
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(query)
            
            if query.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                # 转换为DataFrame便于展示
                df = pd.DataFrame(rows, columns=columns)
                result = df.to_dict('records')
                
                conn.close()
                return True, f"查询成功，返回 {len(result)} 行数据", result
            else:
                conn.commit()
                affected = cursor.rowcount
                conn.close()
                return True, f"命令执行成功，影响 {affected} 行", None
                
        except Exception as e:
            return False, f"SQL执行失败: {str(e)}", None

    def export_database(self, export_path: str) -> Tuple[bool, str]:
        """导出数据库"""
        try:
            export_file = Path(export_path)
            shutil.copy2(db_manager.db_path, export_file)
            return True, f"数据库已导出到: {export_file}"
        except Exception as e:
            return False, f"数据库导出失败: {str(e)}"

    def import_database(self, import_file: str) -> Tuple[bool, str]:
        """导入数据库"""
        try:
            import_path = Path(import_file)
            if not import_path.exists():
                return False, "导入文件不存在"
            
            # 备份当前数据库
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            backup_path = Path("backups") / backup_name
            backup_path.parent.mkdir(exist_ok=True)
            shutil.copy2(db_manager.db_path, backup_path)
            
            # 导入新数据库
            shutil.copy2(import_path, db_manager.db_path)
            
            return True, f"数据库已导入，原数据库已备份到: {backup_path}"
        except Exception as e:
            return False, f"数据库导入失败: {str(e)}"

    # ================================ 管理员界面构建 ================================

    def build_admin_interface(self) -> gr.Blocks:
        """构建增强型管理员界面 - 最终修复版"""
        
        def handle_admin_login(phone, password):
            """管理员登录处理函数"""
            success, message = self.admin_login(phone, password)
            if success:
                initial_data = self._load_initial_data()
                return (
                    gr.update(visible=False),  # 隐藏登录页
                    gr.update(visible=True),   # 显示管理界面
                    *initial_data  # 加载所有初始数据
                )
            else:
                # 返回默认值
                empty_data = [
                    pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 
                    {}, "0%", "0%", "0%", pd.DataFrame()
                ]
                return (
                    gr.update(visible=True),   # 保持登录页可见
                    gr.update(visible=False),  # 保持管理界面隐藏
                    *empty_data
                )

        def handle_user_add(phone, name):
            """添加用户处理函数"""
            return self._handle_operation(
                self.add_user, [phone, name], "添加用户", self.get_all_users
            )

        def handle_user_update(phone, role):
            """更新用户角色处理函数"""
            return self._handle_operation(
                self.update_user_role, [phone, 1 if role == "管理员" else 0], 
                "更新角色", self.get_all_users
            )

        def handle_user_delete(phone):
            """删除用户处理函数"""
            return self._handle_operation(
                self.delete_user, [phone], "删除用户", self.get_all_users
            )

        def handle_kb_add(file_path, title, author, tags):
            """添加知识条目处理函数"""
            return self._handle_operation(
                self.add_knowledge_entry_admin,
                [file_path, title, author, tags],
                "添加知识条目",
                self.get_all_knowledge_entries
            )

        def handle_kb_review(entry_id, status, comments):
            """审核知识条目处理函数"""
            return self._handle_operation(
                self.update_knowledge_status_admin,
                [entry_id, status, comments],
                "更新知识状态",
                self.get_all_knowledge_entries
            )

        def handle_kb_delete(entry_id):
            """删除知识条目处理函数"""
            return self._handle_operation(
                self.delete_knowledge_entry_admin,
                [entry_id, "管理员删除"],
                "删除知识条目",
                self.get_all_knowledge_entries
            )

        def handle_backup():
            """备份处理函数"""
            return self._handle_operation(
                self.backup_data, [], "备份数据", self.get_backup_files
            )

        def handle_restore(file):
            """恢复处理函数"""
            return self._handle_operation(
                self.restore_data, [file], "恢复数据", self.get_backup_files
            )

        def handle_export(path):
            """导出数据库处理函数"""
            return self._handle_operation(
                self.export_database, [path], "导出数据库", None
            )

        def handle_import(file):
            """导入数据库处理函数"""
            return self._handle_operation(
                self.import_database, [file], "导入数据库", None
            )

        def handle_sql_execute(query):
            """执行SQL处理函数"""
            try:
                success, message, result = self.execute_sql_query(query)
                if result is not None:
                    return pd.DataFrame(result)
                return pd.DataFrame([{"结果": message}])
            except Exception as e:
                return pd.DataFrame([{"错误": str(e)}])

        def handle_refresh_all():
            """刷新所有数据"""
            return [
                self.get_all_users(),
                self.get_all_knowledge_entries(),
                self.get_backup_files(),
                self.get_all_tables_data(),
                *list(self.get_system_metrics().values()),
                self.get_system_alerts()
            ]

        # 开始构建界面
        with gr.Blocks(
            theme="soft",
            title="🎓 系统管理后台 - 知识库增强版",
            css="""
                .login-container { max-width: 400px; margin: 100px auto; padding: 40px; background: #f8f9fa; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }
                .admin-title { text-align: center; font-size: 24px; margin-bottom: 30px; color: #495057; }
                .refresh-bar { background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #007bff; }
                .operation-panel { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 10px 0; }
                .btn-primary { background-color: #007bff; color: white; border: none; border-radius: 5px; padding: 8px 15px; cursor: pointer; font-weight: bold; }
                .btn-secondary { background-color: #6c757d; color: white; border: none; border-radius: 5px; padding: 8px 15px; cursor: pointer; font-weight: bold; }
                .btn-success { background-color: #28a745; color: white; border: none; border-radius: 5px; padding: 8px 15px; cursor: pointer; font-weight: bold; }
                .btn-danger { background-color: #dc3545; color: white; border: none; border-radius: 5px; padding: 8px 15px; cursor: pointer; font-weight: bold; }
            """
        ) as admin_app:
            
            # 状态变量
            current_admin = gr.State("")
            
            # 登录页面
            with gr.Column(visible=True, elem_classes="login-container") as login_page:
                gr.Markdown("### 🔐 管理员登录", elem_classes="admin-title")
                admin_phone = gr.Textbox(label="管理员账号", placeholder="请输入管理员账号", value="admin")
                admin_password = gr.Textbox(label="🔒 密码", type="password", placeholder="请输入密码", value="123456")
                login_btn = gr.Button("🚀 登录", variant="primary")
                login_feedback = gr.Markdown()
            
            # 管理界面
            with gr.Column(visible=False) as admin_main:
                gr.Markdown("# 🎓 系统管理后台")
                
                # 全局刷新
                with gr.Row(elem_classes="refresh-bar"):
                    refresh_all_btn = gr.Button("🔄 刷新所有数据", variant="primary")
                
                with gr.Tabs():
                    
                    # 用户管理
                    with gr.TabItem("👤 用户管理"):
                        with gr.Row():
                            users_table = gr.Dataframe(
                                headers=["手机号", "用户名", "角色", "会话数", "消息数"],
                                label="用户列表"
                            )
                        with gr.Row():
                            with gr.Column():
                                new_phone = gr.Textbox(label="📱 手机号", placeholder="11位手机号")
                                new_name = gr.Textbox(label="👤 用户名", placeholder="用户姓名")
                                add_user_btn = gr.Button("✓ 添加用户", variant="success")
                            with gr.Column():
                                update_phone = gr.Textbox(label="📱 手机号")
                                new_role = gr.Radio(["普通用户", "管理员"], label="🔄 新角色")
                                update_role_btn = gr.Button("✓ 更新角色", variant="secondary")
                                delete_phone = gr.Textbox(label="📱 手机号")
                                delete_user_btn = gr.Button("✗ 删除用户", variant="danger")
                        user_feedback = gr.Markdown()
                    
                    # 知识库管理
                    with gr.TabItem("📚 知识库管理"):
                        knowledge_table = gr.Dataframe(
                            headers=['ID', '文件名', '标题', '作者', '标签', '状态', '审核人', '创建时间', '更新时间'],
                            label="知识库条目"
                        )
                        with gr.Row():
                            kb_file_path = gr.Textbox(label="📄 文件路径")
                            kb_title = gr.Textbox(label="🔖 标题")
                            kb_author = gr.Textbox(label="✍️ 作者")
                            kb_tags = gr.Textbox(label="🏷️ 标签", placeholder="tag1,tag2")
                        with gr.Row():
                            kb_entry_id = gr.Number(label="条目ID", precision=0)
                            kb_status = gr.Radio(["approved", "rejected"], label="状态")
                            kb_comments = gr.Textbox(label="意见", lines=2)
                        with gr.Row():
                            add_kb_btn = gr.Button("✓ 添加", variant="success")
                            update_kb_btn = gr.Button("✓ 更新", variant="secondary")
                            delete_kb_btn = gr.Button("✗ 删除", variant="danger")
                        kb_feedback = gr.Markdown()
                    
                    # 数据管理
                    with gr.TabItem("💾 数据管理"):
                        with gr.Row():
                            backup_btn = gr.Button("✓ 立即备份", variant="success")
                            restore_btn = gr.UploadButton("📥 恢复备份", file_types=[".zip"])
                            export_path = gr.Textbox(label="导出路径", value="db_backup.db")
                            export_btn = gr.Button("✓ 导出数据库")
                            import_btn = gr.UploadButton("📥 导入数据库", file_types=[".db"])
                        backup_files = gr.Dataframe(
                            headers=["ID", "文件名", "版本", "创建时间", "大小(MB)"],
                            label="备份文件"
                        )
                    
                    # 数据库管理
                    with gr.TabItem("🗄️ 数据库管理"):
                        tables_display = gr.JSON(label="数据库表数据")
                        sql_query = gr.Textbox(
                            label="SQL语句",
                            lines=5,
                            placeholder="SELECT * FROM users LIMIT 10"
                        )
                        execute_sql_btn = gr.Button("✓ 执行查询", variant="primary")
                        sql_result = gr.Dataframe(label="查询结果")
                    
                    # 系统监控
                    with gr.TabItem("📊 系统监控"):
                        with gr.Row():
                            cpu_metric = gr.Textbox(label="💻 CPU使用率", interactive=False)
                            mem_metric = gr.Textbox(label="🧠 内存使用率", interactive=False)
                            disk_metric = gr.Textbox(label="💾 磁盘使用率", interactive=False)
                        alerts_table = gr.Dataframe(
                            headers=["ID", "消息", "级别", "时间"],
                            label="系统告警"
                        )

            # 事件绑定
            login_btn.click(
                fn=handle_admin_login,
                inputs=[admin_phone, admin_password],
                outputs=[
                    login_page, admin_main, users_table, knowledge_table,
                    backup_files, tables_display, cpu_metric, mem_metric, disk_metric, alerts_table
                ]
            )

            # 用户管理事件
            add_user_btn.click(
                fn=handle_user_add,
                inputs=[new_phone, new_name],
                outputs=[user_feedback, users_table]
            )

            update_role_btn.click(
                fn=handle_user_update,
                inputs=[update_phone, new_role],
                outputs=[user_feedback, users_table]
            )

            delete_user_btn.click(
                fn=handle_user_delete,
                inputs=[delete_phone],
                outputs=[user_feedback, users_table]
            )

            # 知识库管理事件
            add_kb_btn.click(
                fn=handle_kb_add,
                inputs=[kb_file_path, kb_title, kb_author, kb_tags],
                outputs=[kb_feedback, knowledge_table]
            )

            update_kb_btn.click(
                fn=handle_kb_review,
                inputs=[kb_entry_id, kb_status, kb_comments],
                outputs=[kb_feedback, knowledge_table]
            )

            delete_kb_btn.click(
                fn=handle_kb_delete,
                inputs=[kb_entry_id],
                outputs=[kb_feedback, knowledge_table]
            )

            # 数据管理事件
            backup_btn.click(
                fn=handle_backup,
                outputs=[tables_display, backup_files]
            )

            restore_btn.upload(
                fn=handle_restore,
                inputs=[restore_btn],
                outputs=[tables_display, backup_files]
            )

            export_btn.click(
                fn=handle_export,
                inputs=[export_path],
                outputs=[tables_display]
            )

            import_btn.upload(
                fn=handle_import,
                inputs=[import_btn],
                outputs=[tables_display]
            )

            execute_sql_btn.click(
                fn=handle_sql_execute,
                inputs=[sql_query],
                outputs=[sql_result]
            )

            refresh_all_btn.click(
                fn=handle_refresh_all,
                outputs=[
                    users_table, knowledge_table, backup_files, tables_display,
                    cpu_metric, mem_metric, disk_metric, alerts_table
                ]
            )

        return admin_app

    # ================================ 辅助方法 ================================

    def _handle_operation(self, operation_func, params, operation_name, refresh_func=None):
        """统一处理操作"""
        try:
            if params:
                success, message = operation_func(*params)
            else:
                success, message = operation_func()
                
            if refresh_func and success:
                return message, refresh_func()
            return message, None
            
        except Exception as e:
            return f"{operation_name}失败: {str(e)}", None

    def _handle_user_operation(self, operation_func, params, operation_name):
        """统一处理用户操作"""
        try:
            if params:
                success, message = operation_func(*params)
            else:
                success, message = operation_func()
                
            if not success:
                return f"{operation_name}失败: {message}", None
            return message, None
            
        except Exception as e:
            return f"{operation_name}失败: {str(e)}", None

    def _handle_knowledge_operation(self, operation_func, params, operation_name):
        """统一处理知识库操作"""
        try:
            if params:
                success, message = operation_func(*params)
            else:
                success, message = operation_func()
                
            if not success:
                return f"{operation_name}失败: {message}", None
            return message, None
            
        except Exception as e:
            return f"{operation_name}失败: {str(e)}", None

    def _handle_data_operation(self, operation_func, operation_name, refresh_func=None):
        """统一处理数据操作"""
        try:
            result = operation_func()
            if isinstance(result, tuple):
                success, message = result[:2]
            else:
                success, message = result, f"{operation_name}成功"
            
            if refresh_func and success:
                return message, refresh_func()
            return message, None
            
        except Exception as e:
            return f"{operation_name}失败: {str(e)}", None

    def _execute_sql_with_result(self, query):
        """执行SQL并返回结果"""
        try:
            success, message, result = self.execute_sql_query(query)
            if result is not None:
                return pd.DataFrame(result)
            return pd.DataFrame([{"结果": message}])
        except Exception as e:
            return pd.DataFrame([{"错误": str(e)}])

    def _load_initial_data(self):
        """加载初始数据"""
        return [
            self.get_all_users(),
            self.get_all_knowledge_entries(),
            self.get_backup_files(),
            self.get_all_tables_data(),
            *list(self.get_system_metrics().values()),
            self.get_system_alerts()
        ]

# 创建全局管理员实例
admin_manager = AdminManager()