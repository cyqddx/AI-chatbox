import time
import random
import uuid
import datetime
from typing import Any
from config import config
from utils.logger import logger
from utils.database import db_manager
from utils.llm_utils import llm_utils


class ChatManager:
    """
    💬 增强型聊天管理模块
    功能：
        1. 🗂️ 完整的会话生命周期管理（使用UUID）
        2. 💾 所有消息的持久化存储（实时存储）
        3. 🚀 会话预加载和缓存
        4. 📊 批量消息操作
        5. 🎯 智能会话命名（基于内容总结）
    
    设计原则：
        1. ✅ 数据完整性 - 确保所有消息实时保存
        2. 🚀 预加载机制 - 提前加载所有会话和消息
        3. ⚡ 高效查询 - 优化的数据库查询
        4. 🔍 会话隔离 - 会话ID全局唯一
    """

    def __init__(self):
        logger.info("🚀 初始化增强型聊天管理模块")

    def create_session(self, phone: str, title: str = None) -> str:
        """
        ➕ 创建新会话并自动添加欢迎消息
        使用UUID确保全局唯一性
        
        参数:
            phone: 用户手机号
            title: 会话标题（可选，如果为空则使用序号）
        返回:
            新会话ID (UUID格式字符串)
        """
        # 🔑 生成UUID作为会话ID，确保全局唯一
        sid = str(uuid.uuid4())
        
        # 📝 如果没有提供标题，使用会话计数生成
        if not title:
            session_count = self.count_sessions(phone)
            title = f"会话{session_count + 1}"
        
        created = datetime.datetime.now().isoformat()

        # 📝 创建会话记录到数据库
        if db_manager.create_session(sid, phone, title, created):
            # 💬 立即添加欢迎消息到数据库
            welcome_msg = config.i18n.get('new_session_created')
            self.add_message(sid, "assistant", welcome_msg)
            
            # 📊 记录创建日志
            logger.info(f"✅ 创建会话成功: 用户={phone}, 会话ID={sid}, 标题='{title}'")
            
            # 🎯 记录会话创建事件
            logger.info(f"🆕 [SESSION_CREATED] 用户={phone} 创建新会话: UUID={sid}")
            return sid

        logger.error(f"❌ 创建会话失败: 用户={phone}")
        return ""

    def count_sessions(self, phone: str) -> int:
        """📊 统计用户会话数量"""
        sessions = db_manager.get_sessions(phone)
        count = len(sessions) if sessions else 0
        logger.debug(f"📊 统计会话数量: 用户={phone} -> {count}")
        return count

    def add_message(self, sid: str, role: str, content: str) -> bool:
        """
        💾 实时添加消息到会话并确保保存到数据库
        这是确保聊天记录完整性的核心方法
        
        参数:
            sid: 会话ID (UUID格式字符串)
            role: 消息角色 (user/assistant/system)
            content: 消息内容
        返回:
            是否成功保存
        """
        try:
            # 📝 确保所有参数都是字符串类型
            sid_str = str(sid)
            role_str = str(role)
            content_str = str(content)
            
            logger.debug(f"💾 开始保存消息: 会话={sid_str}, 角色={role_str}, 内容长度={len(content_str)}")
                
            success = db_manager.add_message(sid_str, role_str, content_str, datetime.datetime.now().isoformat())
        
            if success:
                logger.debug(f"✅ 消息已实时保存: 会话={sid_str}, 角色={role_str}")
                
                # 🎯 检查是否需要自动重命名会话
                if role_str == "assistant":  # 只在AI回复后检查
                    messages = self.get_messages(sid_str)
                    if len(messages) == 2:  # 第一条用户消息 + 第一条AI回复
                        logger.info(f"🔄 [AUTO_RENAME_CHECK] 会话 {sid_str} 达到重命名条件")
                        self.auto_rename_session(sid_str)
            else:
                logger.error(f"❌ 消息实时保存失败: 会话={sid_str}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 添加消息失败: {str(e)}")
            return False

    def get_messages(self, sid: str, limit: int = None) -> list[tuple[str, str, str]]:
        """
        📋 获取指定会话的所有消息（按时间升序）
        
        参数:
            sid: 会话ID (UUID格式字符串)
            limit: 限制返回消息数量（None 表示全部）
        返回:
            消息列表 [(role, content, timestamp), ...]，按时间顺序排列
        """
        try:
            sid_str = str(sid)
            messages = db_manager.get_messages(sid_str, limit=limit)
            logger.debug(f"📋 获取消息: 会话={sid_str}, 消息数={len(messages)}")
            return messages
        except Exception as e:
            logger.error(f"❌ 获取消息失败: 会话={sid}, 错误={str(e)}")
            return []

    def get_all_sessions_for_user(self, phone: str) -> list[dict[str, Any]]:
        """
        📋 获取用户的所有会话完整信息，包括所有消息
        用于页面初始化时加载完整数据
        
        参数:
            phone: 用户手机号
        返回:
            会话信息列表，包含所有消息
        """
        if not phone:
            return []
        
        logger.info(f"📋 开始加载用户完整数据: {phone}")
        
        # 📋 获取用户的所有会话
        sessions = db_manager.get_sessions(phone)
        if not sessions:
            logger.info(f"ℹ️ 用户无会话: {phone}")
            return []
        
        # 🏗️ 构建完整的会话信息
        full_sessions = []
        for sid, title, created_str in sessions:
            # 📋 获取该会话的所有消息
            messages = self.get_all_session_messages(sid)
            
            session_info = {
                "sid": sid,  # UUID格式字符串
                "title": title,
                "created": datetime.datetime.fromisoformat(created_str),
                "messages": messages,
                "message_count": len(messages)
            }
            full_sessions.append(session_info)
        
        # 📊 按创建时间倒序排列（最新在前）
        full_sessions.sort(key=lambda x: x["created"], reverse=True)
        
        total_sessions = len(full_sessions)
        total_messages = sum(s['message_count'] for s in full_sessions)
        
        logger.info(
            f"✅ 用户数据加载完成: 用户={phone}, "
            f"会话={total_sessions}, 消息={total_messages}"
        )
        
        return full_sessions

    def get_all_session_messages(self, sid: str) -> list[dict[str, str]]:
        """
        📋 获取会话的所有消息（按时间升序排列）
        确保消息的完整性和顺序
        
        参数:
            sid: 会话ID (UUID格式)
        返回:
            完整的消息列表，按时间顺序排列
        """
        sid_str = str(sid)
        messages = db_manager.get_messages(sid_str, limit=None)
        if not messages:
            return []
        
        # 📝 转换为标准格式并确保顺序
        formatted_messages = []
        for role, content, timestamp in messages:
            formatted_messages.append({
                "role": role,
                "content": content,
                "timestamp": timestamp
            })
        
        return formatted_messages

    def preload_user_data(self, phone: str) -> dict[str, Any]:
        """
        🚀 预加载用户的完整数据（会话+消息）
        在用户登录或注册后立即调用
        
        参数:
            phone: 用户手机号
        返回:
            用户完整数据字典
        """
        if not phone:
            logger.warning("⚠️ 预加载用户数据失败: 手机号为空")
            return {"sessions": [], "total_messages": 0}
        
        logger.info(f"🚀 开始预加载用户数据: {phone}")
        
        # 📋 获取所有会话和消息
        sessions = self.get_all_sessions_for_user(phone)
        
        # 📊 计算总消息数
        total_messages = sum(session["message_count"] for session in sessions)
        
        user_data = {
            "phone": phone,
            "sessions": sessions,
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "latest_session": sessions[0]["sid"] if sessions else None
        }
        
        logger.info(
            f"✅ 预加载用户数据完成: "
            f"用户={phone}, 会话={len(sessions)}, 消息={total_messages}"
        )
        
        return user_data

    def ensure_user_has_session(self, phone: str) -> str:
        """
        ✅ 确保用户至少有一个会话，如果没有则创建
        用于新用户注册或首次登录
        
        参数:
            phone: 用户手机号
        返回:
            会话ID（新创建或现有的，UUID格式）
        """
        if not phone:
            logger.warning("⚠️ 确保用户有会话失败: 手机号为空")
            return ""
        
        # 🔍 检查用户是否已有会话
        existing_sessions = db_manager.get_sessions(phone)
        
        if existing_sessions:
            # 🎯 返回最新的会话
            latest_sid = existing_sessions[0][0]
            logger.info(f"✅ 用户已有会话: {phone} -> {latest_sid}")
            return latest_sid
        
        # 🆕 创建第一个会话
        logger.info(f"🆕 为用户创建第一个会话: {phone}")
        return self.create_session(phone, "欢迎使用")

    def get_grouped_sessions_for_display(self, phone: str) -> list[tuple[str, str]]:
        """
        📋 为显示准备的会话列表（包含所有会话和消息计数）
        生成Gradio Radio需要的格式
        
        参数:
            phone: 用户手机号
        返回:
            Gradio Radio需要的格式列表 [(显示文本, 会话ID), ...]
        """
        if not phone:
            return []
        
        logger.info(f"📋 开始生成分组会话列表: {phone}")
        
        # 📋 获取完整会话数据
        sessions = self.get_all_sessions_for_user(phone)
        
        if not sessions:
            # 🆕 新用户无会话，创建第一个
            sid = self.create_session(phone, "欢迎使用")
            sessions = self.get_all_sessions_for_user(phone)
        
        # 📊 分组逻辑 - 按时间分组
        today = datetime.datetime.now().date()
        yesterday = today - datetime.timedelta(days=1)
        last_week = today - datetime.timedelta(days=7)

        grouped = {
            "今天": [],
            "昨天": [],
            "前7天": [],
            "更早": []
        }

        display_choices = []
        
        # 📊 按时间分组会话
        for session in sessions:
            created_date = session["created"].date()
            
            # 🎯 确定分组
            if created_date == today:
                group_name = "今天"
            elif created_date == yesterday:
                group_name = "昨天"
            elif created_date >= last_week:
                group_name = "前7天"
            else:
                group_name = "更早"
            
            # 📂 添加到对应分组
            grouped[group_name].append(session)
        
        # 🏗️ 构建显示列表
        for group_name, group_sessions in grouped.items():
            if group_sessions:
                # 📂 添加分组标题
                display_choices.append((
                    f"--- 📂 {group_name} ({len(group_sessions)}) ---",
                    "__GROUP__"
                ))
                
                # 📋 添加该分组的所有会话（显示消息数量）
                for session in group_sessions:
                    created_time = session["created"].strftime("%m-%d %H:%M")
                    message_count = session["message_count"]
                    display_text = f"💬 {session['title']} • {created_time} ({message_count}条消息)"
                    display_choices.append((display_text, session["sid"]))
        
        total_sessions = len([c for c in display_choices if c[1] != '__GROUP__'])
        logger.info(
            f"✅ 生成分组会话列表完成: "
            f"用户={phone}, 分组={len([g for g in grouped.values() if g])}, "
            f"总会话={total_sessions}"
        )
        
        return display_choices

    def ensure_all_sessions_loaded(self, phone: str) -> dict[str, Any]:
        """
        ✅ 确保用户所有会话和消息都已加载并可用
        这是解决注册后会话不显示的关键方法
        
        参数:
            phone: 用户手机号
        返回:
            包含所有会话信息的字典，确保UI能立即显示
        """
        if not phone:
            return {
                "sessions": [], 
                "session_choices": [("💬 欢迎使用", "")], 
                "default_sid": None,
                "total_sessions": 0,
                "total_messages": 0
            }
        
        logger.info(f"✅ 开始确保所有会话加载: {phone}")
        
        # ✅ 确保用户至少有一个会话
        existing_sessions = db_manager.get_sessions(phone)
        if not existing_sessions:
            logger.info(f"🆕 为用户创建首个会话: {phone}")
            first_sid = self.create_session(phone, "欢迎使用")
            # 🔄 重新获取会话列表
            existing_sessions = db_manager.get_sessions(phone)
        
        # 📋 获取所有会话（包含完整消息）
        sessions = self.get_all_sessions_for_user(phone)
        
        # 🏗️ 构建会话选择列表
        session_choices = self.get_grouped_sessions_for_display(phone)
        
        # 🎯 确定默认会话（最新创建的）
        default_sid = sessions[0]["sid"] if sessions else None
        
        # 🛡️ 确保有有效的会话选择
        if not session_choices and default_sid:
            session_choices = [("💬 欢迎使用", default_sid)]
        
        result = {
            "sessions": sessions,
            "session_choices": session_choices,
            "default_sid": default_sid,
            "total_sessions": len(sessions),
            "total_messages": sum(s["message_count"] for s in sessions)
        }
        
        logger.info(
            f"✅ 会话加载完成: "
            f"用户={phone}, 会话={len(sessions)}, 消息={result['total_messages']}"
        )
        
        return result

    def create_first_session_for_new_user(self, phone: str) -> str:
        """
        🎉 为新用户创建第一个会话并添加欢迎消息
        注册成功后立即调用
        
        参数:
            phone: 用户手机号
        返回:
            新创建的会话ID (UUID格式)
        """
        if not phone:
            logger.warning("⚠️ 为新用户创建会话失败: 手机号为空")
            return ""
        
        # 🆕 创建会话
        sid = self.create_session(phone, "欢迎使用")
        
        # 💬 添加欢迎消息（已自动完成）
        logger.info(f"🎉 为新用户创建首个会话: 用户={phone}, 会话ID={sid}")
        
        return sid

    def get_grouped_sessions(self, phone: str) -> dict[str, list[dict[str, Any]]]:
        """
        📋 获取分组后的用户会话（用于UI显示）
        
        参数:
            phone: 用户手机号
            
        返回:
            按时间分组的会话字典
        """
        try:
            if not phone:
                return {}
            
            logger.info(f"📋 开始获取分组会话: {phone}")
            
            # 📋 获取用户的所有会话
            sessions = db_manager.get_sessions(phone)
            
            # 📝 转换为标准格式
            formatted_sessions = []
            for sid, title, created_str in sessions:
                formatted_sessions.append({
                    "sid": sid,
                    "title": title,
                    "created": datetime.datetime.fromisoformat(created_str),
                    "message_count": 0  # 可以后续添加消息计数
                })
            
            # 📊 按时间分组
            today = datetime.datetime.now().date()
            yesterday = today - datetime.timedelta(days=1)
            last_week = today - datetime.timedelta(days=7)
            
            grouped = {
                "今天": [],
                "昨天": [],
                "前7天": [],
                "更早": []
            }
            
            for session in formatted_sessions:
                created_date = session["created"].date()
                
                if created_date == today:
                    grouped["今天"].append(session)
                elif created_date == yesterday:
                    grouped["昨天"].append(session)
                elif created_date >= last_week:
                    grouped["前7天"].append(session)
                else:
                    grouped["更早"].append(session)
            
            # 🧹 移除空分组
            grouped = {k: v for k, v in grouped.items() if v}
            
            logger.info(f"✅ 获取分组会话完成: 用户={phone}, 分组={len(grouped)}")
            return grouped
            
        except Exception as e:
            logger.error(f"❌ 获取分组会话失败: 用户={phone}, 错误={str(e)}")
            return {}

    def get_sessions(self, phone: str) -> list[tuple[str, str, str]]:
        """
        📋 获取用户的所有会话列表
        
        参数:
            phone: 用户手机号
        返回:
            会话列表 [(sid, title, created), ...]，按创建时间降序排列
        """
        try:
            if not phone:
                return []
            
            sessions = db_manager.get_sessions(phone)
            logger.debug(f"📋 获取用户会话: 用户={phone}, 会话数={len(sessions)}")
            return sessions
            
        except Exception as e:
            logger.error(f"❌ 获取用户会话失败: 用户={phone}, 错误={str(e)}")
            return []

    def auto_rename_session(self, sid: str) -> bool:
        """
        🎯 根据会话内容自动生成有意义的名称
        当会话有消息时，使用第一条用户消息和AI回复进行总结
        
        参数:
            sid: 会话ID (UUID格式)
        返回:
            是否成功重命名
        """
        try:
            # 🔍 获取会话的所有消息
            messages = self.get_messages(sid, limit=10)  # 获取前10条用于总结
            
            if not messages or len(messages) < 2:
                logger.debug(f"ℹ️ 会话 {sid} 消息不足，跳过重命名")
                return False
            
            # 📋 提取用户和助手的消息
            user_messages = [msg[1] for msg in messages if msg[0] == "user"]
            assistant_messages = [msg[1] for msg in messages if msg[0] == "assistant"]
            
            if not user_messages:
                logger.debug(f"ℹ️ 会话 {sid} 无用户消息，跳过重命名")
                return False
            
            # 📝 构建总结提示
            first_user_msg = user_messages[0][:200]  # 限制长度
            first_assistant_msg = assistant_messages[0][:200] if assistant_messages else ""
            
            prompt = f"""
            请根据以下对话内容，为这个聊天会话生成一个简洁有意义的名称（2-8个字）：
            
            用户问题：{first_user_msg}
            助手回复：{first_assistant_msg}
            
            要求：
            1. 名称要准确反映对话主题
            2. 简洁明了，易于理解
            3. 使用中文
            4. 不要包含特殊字符
            
            只返回生成的名称，不要其他解释：
            """
            
            # 🤖 使用大模型生成名称
            new_title = llm_utils.generate_text(prompt, max_tokens=20, temperature=0.3).strip()
            
            # 🧹 清理生成的名称
            new_title = new_title.replace('"', '').replace("'", "").strip()
            
            if not new_title or len(new_title) < 2:
                logger.debug(f"ℹ️ 生成的名称无效，跳过重命名")
                return False
            
            # 🔄 更新数据库中的会话名称
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET title = ? WHERE sid = ?",
                (new_title, str(sid))
            )
            conn.commit()
            conn.close()
            
            logger.info(f"🎯 [SESSION_RENAMED] 会话 {sid} 已重命名为: '{new_title}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ 会话重命名失败: {sid} - {str(e)}")
            return False

    def refresh_user_sessions(phone: str) -> dict:
        """
        🔄 强制刷新用户会话列表并返回最新状态
        用于注册/登录后立即同步UI
        """
        logger.info(f"🔄 强制刷新用户会话: {phone}")
        return ensure_all_sessions_loaded(phone)

        
# 🌍 全局聊天管理实例
chat_manager = ChatManager()