"""
🎨 UI处理模块
将Gradio界面相关的处理逻辑集中管理
包括会话管理、消息处理、文件上传等
"""

import datetime
import random
import re
import uuid
from typing import Any
import gradio as gr
from pathlib import Path
from config import config
from utils.logger import logger
from utils.database import db_manager
from modules import (
    chat_management,
    file_processing,
    user_management,
    intent_recognition,
    intent_router,
    next_questions,
)


class SessionManager:
    """🗂️ 会话管理器 - 负责管理用户的聊天会话"""
    
    @staticmethod
    def build_session_choices(phone: str) -> list[tuple[str, str]]:
        """
        🏗️ 构建会话选择列表 - 修复空值问题
        
        参数:
            phone: 用户手机号
            
        返回:
            会话选择列表，确保不会返回空Radio值
        """
        
        if not phone:
            # 🎯 返回默认选项而不是空列表
            return [("💬 欢迎使用", "__DEFAULT__")]
        
        try:
            # 📋 获取分组后的会话
            grouped_sessions = chat_management.chat_manager.get_grouped_sessions(phone)
            session_choices = []
            
            # 🏗️ 按分组添加会话到选择列表
            for group_name, group_sessions in grouped_sessions.items():
                if group_sessions:
                    # 📂 添加分组标题
                    session_choices.append((f"--- 📂 {group_name} ({len(group_sessions)}) ---", "__GROUP__"))
                    
                    # 📋 添加该分组下的所有会话
                    for session in group_sessions:
                        created_time = session["created"].strftime("%m-%d %H:%M")
                        display_text = f"💬 {session['title']} • {created_time}"
                        session_choices.append((display_text, session["sid"]))
            
            # 🆕 如果没有会话，创建默认会话
            if not session_choices:
                # 创建默认会话而不是返回空列表
                default_sid = chat_management.chat_manager.ensure_user_has_session(phone)
                created_time = datetime.datetime.now().strftime("%m-%d %H:%M")
                display_text = f"💬 欢迎使用 • {created_time}"
                session_choices = [(display_text, default_sid)]
                logger.info(f"🆕 为新用户{phone}创建默认会话: UUID={default_sid}")
            
            # 🎯 确保至少有一个有效选项
            if not session_choices:
                session_choices = [("💬 欢迎使用", "__DEFAULT__")]
            
            logger.info(f"📋 构建会话选择列表完成: 用户={phone}, 会话数={len([c for c in session_choices if c[1] not in ['__GROUP__', '__DEFAULT__']])}")
            return session_choices
            
        except Exception as e:
            logger.error(f"❌ 构建会话列表失败: {str(e)}")
            # 🎯 返回默认选项而不是空列表
            return [("💬 欢迎使用", "__DEFAULT__")]

    @staticmethod
    def create_new_session(phone: str) -> tuple[str, list, Any, Any, Any, Any]:
        """
        ➕ 创建新会话并立即预加载所有会话数据
        使用UUID确保会话ID全局唯一
        
        参数:
            phone: 用户手机号
        返回:
            包含新会话信息的元组
        """
        if not phone:
            return "", [], gr.update(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        
        try:
            # ➕ 创建新会话（自动生成UUID）
            sid = chat_management.chat_manager.create_session(phone)
            
            # 🎯 记录会话创建事件
            logger.info(f"🆕 [CREATE_SESSION] 用户={phone} 创建新会话: UUID={sid}")
            
            # 🔄 获取更新后的会话列表
            session_choices = SessionManager.build_session_choices(phone)
            
            # 📋 获取新会话的所有消息
            messages = chat_management.chat_manager.get_messages(sid, limit=None)
            history = [{"role": role, "content": content} for role, content, _ in messages]
            
            logger.info(f"✅ 创建新会话成功: 用户={phone}, 会话UUID={sid}")
            
            return (
                history,
                sid,
                gr.update(choices=session_choices, value=sid),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False)
            )
            
        except Exception as e:
            logger.error(f"❌ 创建新会话失败: {str(e)}")
            return "", [], gr.update(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

    @staticmethod
    def switch_session(new_sid: str, phone: str) -> tuple[list[dict[str, str]], str, Any, Any, Any]:
        """
        🔄 切换会话 - 修复返回值数量问题
        
        参数:
            new_sid: 新的会话ID (UUID格式字符串)
            phone: 用户手机号
            
        返回:
            5个值的元组：(聊天历史, 会话ID, 按钮1, 按钮2, 按钮3)
        """
        # 🛡️ 输入验证：处理None值
        if new_sid is None or not new_sid or new_sid == "__GROUP__":
            logger.warning(f"⚠️ [SWITCH_SESSION] 无效会话ID: {new_sid}")
            # 返回5个值，确保数量匹配
            return [], "", gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        
        # 🔍 严格验证UUID格式
        try:
            uuid.UUID(str(new_sid))
            sid_str = str(new_sid)
        except (ValueError, TypeError):
            logger.error(f"❌ [SWITCH_SESSION] 无效的UUID格式: {new_sid}")
            return [], "", gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        
        try:
            logger.info(f"🔄 [SWITCH_SESSION] 开始切换会话: 用户={phone}, 会话UUID={sid_str}")
            
            # 📋 获取会话消息
            messages = chat_management.chat_manager.get_messages(sid_str)
            
            # 🏗️ 构建聊天历史
            chat_history = []
            for role, content, _ in messages:
                chat_history.append({"role": role, "content": content})
            
            logger.info(f"✅ [SWITCH_SESSION] 切换会话完成: 用户={phone}, 会话UUID={sid_str}, 消息数={len(chat_history)}")
            
            # 🎯 关键：返回5个值，与Gradio组件匹配
            return (
                chat_history,                    # [1] 聊天历史
                sid_str,                        # [2] 当前会话ID
                gr.update(visible=False),        # [3] 后续问题按钮1
                gr.update(visible=False),        # [4] 后续问题按钮2
                gr.update(visible=False)         # [5] 后续问题按钮3
            )
            
        except Exception as e:
            logger.error(f"❌ [SWITCH_SESSION] 切换会话失败: 用户={phone}, 会话={new_sid}, 错误={str(e)}")
            return [], "", gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

    @staticmethod
    def get_latest_or_create_session(phone: str) -> str:
        """
        🎯 获取用户最新会话，如果没有则创建
        
        参数:
            phone: 用户手机号
            
        返回:
            会话ID
        """
        if not phone:
            return ""
        
        try:
            sid = chat_management.chat_manager.ensure_user_has_session(phone)
            logger.info(f"✅ 获取会话成功: 用户={phone}, 会话ID={sid}")
            return sid
            
        except Exception as e:
            logger.error(f"❌ 获取会话失败: {str(e)}")
            return ""

    @staticmethod
    def refresh_session_list(phone: str) -> Any:
        """
        🔄 刷新会话列表
        
        参数:
            phone: 用户手机号
            
        返回:
            更新后的会话列表组件
        """
        if not phone:
            return gr.update()
        
        try:
            # 🔄 获取更新后的会话列表
            session_choices = SessionManager.build_session_choices(phone)
            logger.info(f"🔄 会话列表刷新完成: 用户={phone}, 会话数={len([c for c in session_choices if c[1] != '__GROUP__'])}")
            return gr.update(choices=session_choices)
            
        except Exception as e:
            logger.error(f"❌ 刷新会话列表失败: {str(e)}")
            return gr.update()

    @staticmethod
    def safe_switch_session(new_sid: str, phone: str) -> tuple:
        """
        🔒 安全的会话切换方法 - 修复Radio值问题
        
        参数:
            new_sid: 新的会话ID
            phone: 用户手机号
        
        返回:
            总是返回5个值的元组，确保Radio值有效
        """
        # 🛡️ 防御式编程：处理所有可能的None值
        safe_phone = str(phone) if phone else ""
        
        # 🎯 处理Radio组件的空值问题
        if new_sid is None or new_sid == [] or new_sid == "__GROUP__":
            logger.warning(f"⚠️ [SAFE_SWITCH] 处理无效Radio值: {new_sid}")
            
            # 🔄 获取用户的最新会话作为默认值
            sessions = chat_management.chat_manager.get_sessions(safe_phone)
            if sessions:
                safe_sid = sessions[0][0]  # 最新的会话
            else:
                # 🆕 创建默认会话
                safe_sid = chat_management.chat_manager.ensure_user_has_session(safe_phone)
            
            # 📋 获取默认会话的内容
            messages = chat_management.chat_manager.get_messages(safe_sid)
            chat_history = [{"role": role, "content": content} for role, content, _ in messages]
            
            return chat_history, safe_sid, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        
        # 🔍 验证会话ID格式
        try:
            uuid.UUID(str(new_sid))
            safe_sid = str(new_sid)
        except (ValueError, TypeError):
            logger.error(f"❌ [SAFE_SWITCH] 无效的UUID格式: {new_sid}")
            return [], str(new_sid), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        
        # 🔄 正常的会话切换逻辑
        return SessionManager.switch_session(safe_sid, safe_phone)

    # 🛠️ 修复：确保传入的是UUID字符串，而非历史对象
    @staticmethod
    def _normalize_sid(sid: Any) -> str:
        """确保会话ID是有效的UUID字符串"""
        if isinstance(sid, dict) and "sid" in sid:
            return str(sid["sid"])
        if isinstance(sid, list) and len(sid) == 1 and isinstance(sid[0], str):
            return str(sid[0])
        if isinstance(sid, str):
            try:
                uuid.UUID(sid)
                return sid
            except ValueError:
                pass
        return str(uuid.uuid4())  # 兜底：生成新UUID


class MessageHandler:
    """💬 消息处理器 - 处理用户发送的消息"""
    
    @staticmethod
    def process_message(
        text: str, 
        sid: str,
        phone: str, 
        chat_history: list[dict[str, str]]
    ) -> tuple[list[dict[str, str]], str, str, Any, Any, Any]:
        """
        💬 处理用户消息 - 确保每条消息都实时保存
        
        参数:
            text: 用户输入的文本
            sid: 当前会话ID (UUID格式字符串)
            phone: 用户手机号
            chat_history: 当前聊天历史
            
        返回:
            包含新消息、清空输入框、会话ID、预测问题的元组
        """
        # 🧹 清理输入文本
        text = str(text).strip() if text else ""
        
        # 🛡️ 检查空消息
        if not text:
            return chat_history, "", sid, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        
        # 📝 确保会话ID是字符串格式（UUID）
        sid_str = str(sid) if sid else ""
        
        # 🔍 验证UUID格式
        try:
            uuid.UUID(sid_str)
            logger.info(f"💬 开始处理消息: 用户={phone}, 会话={sid_str}")
        except (ValueError, TypeError):
            # ❌ 无效的会话ID，创建新会话
            logger.warning(f"⚠️ 无效的会话ID格式: {sid}, 创建新会话")
            sid_str = chat_management.chat_manager.create_session(phone)
            logger.info(f"🆕 创建新会话处理消息: 用户={phone}, 会话ID={sid_str}")
        
        try:
            # 1. 💾 立即保存用户消息到数据库
            chat_management.chat_manager.add_message(sid, "user", text)
            logger.debug("💾 用户消息已保存")
            
            # 2. 📋 获取完整对话历史（包含刚保存的消息）
            db_messages = chat_management.chat_manager.get_messages(sid)
            
            # 3. 📝 格式化历史记录给意图识别器
            formatted_messages = []
            for msg in db_messages:
                if len(msg) >= 2:
                    role, content = msg[0], msg[1]
                    formatted_messages.append((role, content))
            
            # 4. 🎯 识别用户意图
            intent = intent_recognition.intent_recognizer.recognize(text)
            logger.info(f"🎯 识别到意图: 意图={intent}, 用户={phone}, 会话={sid}")
            
            # 5. 🚀 路由到对应处理器生成回复
            reply = intent_router.intent_router.route(intent, text, sid, formatted_messages)
            logger.info(f"🤖 生成回复: 用户={phone}, 会话={sid}, 回复长度: {len(reply)}")
            
            # 6. 💾 立即保存AI回复到数据库
            chat_management.chat_manager.add_message(sid, "assistant", reply)
            logger.debug("💾 AI回复已保存")
            
            # 7. 📋 获取更新后的完整消息列表
            updated_messages = chat_management.chat_manager.get_messages(sid)
            new_history = []
            for role, content, _ in updated_messages:
                new_history.append({"role": role, "content": content})
            
            # 8. 🔮 预测后续问题
            recent_history = []
            for role, content, _ in updated_messages[-10:]:
                recent_history.append((role, content))
            
            predicted_questions = next_questions.question_predictor.predict(text, recent_history)
            logger.info(f"🔮 预测后续问题: 用户={phone}, 会话={sid}, 问题={predicted_questions}")
            
            # 9. 🔄 更新后续问题按钮
            btn_updates = MessageHandler._update_next_question_buttons(predicted_questions)
            
        except Exception as e:
            # ❌ 错误处理
            logger.error(f"❌ 消息处理失败: 用户={phone}, 会话={sid}, 错误={str(e)}")
            error_reply = config.i18n.get('error_occurred')
            
            # 💾 保存错误回复
            chat_management.chat_manager.add_message(sid, "assistant", error_reply)
            
            # 📋 获取包含错误回复的完整消息列表
            updated_messages = chat_management.chat_manager.get_messages(sid)
            new_history = []
            for role, content, _ in updated_messages:
                new_history.append({"role": role, "content": content})
            btn_updates = (gr.update(visible=False), gr.update(visible=False), gr.update(visible=False))
        
        logger.info(f"✅ 消息处理完成: 用户={phone}, 会话={sid}, 总消息数={len(new_history)}")
        return new_history, "", sid, *btn_updates
    
    @staticmethod
    def _update_next_question_buttons(questions: list[str]) -> tuple[Any, Any, Any]:
        """
        🔄 更新后续问题按钮的显示状态和文本
        
        参数:
            questions: 预测的问题列表
            
        返回:
            三个按钮的更新状态
        """
        if not questions or len(questions) == 0:
            # 🙈 没有预测问题时，隐藏所有按钮
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        
        # ✂️ 确保最多3个问题
        questions = questions[:3]
        
        # 🎯 为每个问题创建按钮更新
        btn_updates = []
        for i, question in enumerate(questions):
            btn_updates.append(gr.update(visible=True, value=question))
        
        # 🙈 填充剩余按钮为隐藏状态
        while len(btn_updates) < 3:
            btn_updates.append(gr.update(visible=False))
        
        return tuple(btn_updates)
    
    @staticmethod
    def select_next_question(
        question: str, 
        sid: str, 
        phone: str, 
        history: list[dict[str, str]]
    ) -> tuple[list[dict[str, str]], str, str, Any, Any, Any]:
        """
        🎯 选择并发送预测的问题
        
        参数:
            question: 预测的问题文本
            sid: 当前会话ID (UUID格式)
            phone: 用户手机号
            history: 当前聊天历史
            
        返回:
            处理后的消息结果
        """
        # 📝 直接使用UUID格式的会话ID
        logger.info(f"🎯 选择预测问题: 问题='{question}', 会话={sid}")
        
        # 🛡️ 空问题不处理
        if not question or question.strip() == "":
            return history, "", sid, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        
        # 🔄 使用现有的消息处理逻辑
        return MessageHandler.process_message(question, sid, phone, history)

    @staticmethod
    def build_session_content(sid: str, phone: str) -> list[dict[str, str]]:
        """
        🏗️ 构建会话的完整内容，包括消息和文件状态
        
        参数:
            sid: 会话ID (UUID格式字符串)
            phone: 用户手机号
        
        返回:
            完整的内容列表，包含消息和文件状态
        """
        try:
            # 🔍 验证会话ID
            uuid.UUID(str(sid))
            sid_str = str(sid)
            
            # 📋 获取所有消息
            messages = chat_management.chat_manager.get_messages(sid_str)
            
            # 📋 获取文件状态
            file_status = file_processing.file_processor.get_session_file_status(sid_str)
            
            # 🏗️ 构建完整内容
            content_list = []
            
            # 📁 添加文件状态提示
            if file_status['processed'] > 0:
                content_list.append({
                    "role": "system",
                    "content": f"📁 当前会话已加载 {file_status['processed']} 个文件"
                })
            
            if file_status['unprocessed'] > 0:
                content_list.append({
                    "role": "system",
                    "content": f"📁 当前会话有 {file_status['unprocessed']} 个文件待处理"
                })
            
            # 📋 添加所有消息
            for role, content, timestamp in messages:
                content_list.append({
                    "role": role,
                    "content": content,
                    "timestamp": timestamp
                })
            
            logger.info(
                f"🏗️ 构建会话内容完成: "
                f"会话={sid_str}, 消息={len(messages)}, 文件={file_status['total']}"
            )
            
            return content_list
            
        except Exception as e:
            logger.error(f"❌ 构建会话内容失败: 会话={sid}, 错误={str(e)}")
            return [{"role": "system", "content": "加载会话内容时出错"}]


class FileUploadHandler:
    """📁 文件上传处理器 - 处理用户上传的文件"""

    @staticmethod
    def handle_file_upload(
        files: list[Any], 
        phone: str, 
        sid: str, 
        chat_history: list[dict[str, str]]
    ) -> tuple[list[dict[str, str]], str, Any]:
        """
        📁 处理文件上传 - 修复参数验证和错误处理
        
        参数:
            files: Gradio上传的文件列表
            phone: 用户手机号
            sid: 当前会话ID
            chat_history: 当前聊天历史
            
        返回:
            元组：(更新后的聊天历史, 实际使用的会话ID, 更新的会话列表组件)
        """
        try:
            # 🛡️ 严格的参数验证
            phone = str(phone).strip() if phone else ""
            actual_sid = str(sid).strip() if sid else ""
            
            logger.info(f"📁 开始处理文件上传: 用户={phone}, 会话={actual_sid}, 文件数={len(files)}")
            
            # 🔍 参数验证
            if not phone or not phone.isdigit() or len(phone) != 11:
                error_msg = "❌ 无效的手机号参数"
                logger.error(error_msg)
                return chat_history, actual_sid, gr.update()
                
            # 🔍 会话ID验证 - 确保是有效的UUID
            try:
                uuid.UUID(actual_sid)
            except (ValueError, TypeError):
                logger.warning("⚠️ 无效的会话ID格式，创建新会话")
                actual_sid = chat_management.chat_manager.create_session(phone, "文件上传会话")
            
            if not files or not isinstance(files, (list, tuple)):
                logger.warning("⚠️ 无效的文件列表")
                return chat_history, actual_sid, gr.update()
            
            processed_count = 0
            failed_files = []
            
            # 📁 逐个处理文件
            for idx, file_data in enumerate(files):
                try:
                    # 🔍 获取文件名
                    if hasattr(file_data, 'name'):
                        original_filename = str(Path(file_data.name).name)
                    elif hasattr(file_data, 'orig_name'):
                        original_filename = str(Path(file_data.orig_name).name)
                    else:
                        original_filename = str(file_data).split('/')[-1]
                    
                    # 🧹 使用清理后的文件名
                    original_filename = file_processing.file_processor.sanitize_filename(original_filename)
                    file_type = Path(original_filename).suffix.lower().lstrip(".")
                    
                    logger.info(f"🔍 处理第{idx + 1}个文件: {original_filename}")
                    
                    # 🛡️ 文件类型验证
                    if file_type not in config.SUPPORTED_FILE_FORMATS:
                        error_msg = f"❌ 不支持的文件格式: {file_type}"
                        chat_management.chat_manager.add_message(actual_sid, "system", error_msg)
                        failed_files.append(original_filename)
                        continue
                    
                    # 📁 保存文件到本地
                    try:
                        file_path = file_processing.file_processor.save_file(
                            file_data, 
                            phone, 
                            actual_sid
                        )
                        
                        if not file_path or not Path(file_path).exists():
                            raise ValueError("文件保存失败")
                    
                    except Exception as save_error:
                        logger.error(f"❌ 文件保存异常: {save_error}")
                        fail_msg = f"❌ 文件保存失败: {original_filename}"
                        chat_management.chat_manager.add_message(actual_sid, "system", fail_msg)
                        failed_files.append(original_filename)
                        continue
                    
                    # 🔄 处理文件（向量化存储）
                    try:
                        success = file_processing.file_processor.process_file(
                            actual_sid, 
                            Path(file_path), 
                            original_filename, 
                            file_type
                        )
                        
                        if success:
                            processed_count += 1
                            success_msg = f"✅ 文件处理完成: {original_filename}"
                            chat_management.chat_manager.add_message(actual_sid, "assistant", success_msg)
                        else:
                            failed_files.append(original_filename)
                            fail_msg = f"❌ 文件处理失败: {original_filename}"
                            chat_management.chat_manager.add_message(actual_sid, "system", fail_msg)
                    
                    except Exception as process_error:
                        logger.error(f"❌ 文件处理异常: {process_error}")
                        fail_msg = f"❌ 文件处理异常: {original_filename}"
                        chat_management.chat_manager.add_message(actual_sid, "system", fail_msg)
                        failed_files.append(original_filename)
                
                except Exception as e:
                    logger.error(f"💥 第{idx + 1}个文件总体异常: {str(e)}")
                    failed_files.append(str(file_data))
                    continue
            
            # 📋 获取最新聊天记录
            messages = chat_management.chat_manager.get_messages(actual_sid)
            new_history = [
                {"role": role, "content": content} 
                for role, content, _ in messages
            ]
            
            # 📊 生成处理总结
            if processed_count > 0 or failed_files:
                summary_parts = []
                if processed_count > 0:
                    summary_parts.append(f"✅ 成功处理 {processed_count} 个文件")
                if failed_files:
                    summary_parts.append(f"❌ 失败 {len(failed_files)} 个")
                
                summary_msg = " | ".join(summary_parts)
                if summary_msg:
                    chat_management.chat_manager.add_message(actual_sid, "assistant", summary_msg)
            
            logger.info(
                f"📊 文件上传完成: 用户={phone}, 会话={actual_sid}, "
                f"成功={processed_count}, 失败={len(failed_files)}"
            )
            
            # 🔄 刷新左侧会话列表
            session_update = SessionManager.refresh_session_list(phone)
            
            return new_history, actual_sid, session_update
            
        except Exception as e:
            logger.error(f"❌ 文件上传处理总体失败: {str(e)}")
            # 🔄 无论如何都尝试刷新会话列表
            try:
                session_update = SessionManager.refresh_session_list(str(phone))
            except:
                session_update = gr.update()
            return chat_history, str(sid), session_update


class VerificationManager:
    """
    🔑 验证码管理器
    支持开发(dev)与正式(prod)两种环境：
      - dev：直接控制台打印并返回 4 位随机数字
      - prod：调用真实接码平台（示例里给出调用桩）
    使用同一个 send_code 方法，调用方无感切换。
    """

    def __init__(self, env: str = "dev"):
        """
        env: "dev" | "prod"
        """
        self.env = env.lower()
        logger.info(f"🔑 [VerificationManager] 初始化验证码管理器，环境={self.env}")

    def send_code(self, phone: str, code_dict: dict[str, str]) -> bool:
        """
        📱 生成/发送验证码，并把生成的验证码写入 code_dict
        返回 True 表示"成功"，False 表示"失败"
        """
        code = self._generate_code()

        if self.env == "dev":
            # 💻 开发环境：直接生成并存入字典，控制台打印
            logger.info(f"💻 [DEV] 验证码已生成 → 📱 {phone}: 🔑 {code}")
            code_dict[phone] = code
            return True

        elif self.env == "prod":
            # 🚀 正式环境：调用真实接码平台
            try:
                logger.info(f"🚀 [PROD] 正在调用接码平台 → 📱 {phone}")
                success = self._send_via_sms_platform(phone, code)
                if success:
                    code_dict[phone] = code
                    logger.info(f"✅ [PROD] 接码平台返回成功 → 📱 {phone}: 🔑 {code}")
                else:
                    logger.error(f"❌ [PROD] 接码平台返回失败 → 📱 {phone}")
                return success
            except Exception as e:
                logger.error(f"💥 [PROD] 接码平台异常 → 📱 {phone}: {e}")
                return False

        else:
            logger.error(f"❌ [VerificationManager] 未知环境配置: {self.env}")
            return False

    def _generate_code(self) -> str:
        """🔢 生成 4 位数字验证码"""
        code = f"{random.randint(1000, 9999)}"
        logger.debug(f"🔢 生成验证码: {code}")
        return code

    def _send_via_sms_platform(self, phone: str, code: str) -> bool:
        """
        📱 真实接码平台调用示例（桩代码）
        这里可以替换成任意 SMS 服务商 SDK
        """
        # 📝 替换为真实的短信发送逻辑
        logger.info(f"📱 [SMS_STUB] 假设已发送短信 → 📱 {phone} 验证码 🔑 {code}")
        return True   # ✅ 演示默认成功


class AuthHandler:
    """🔐 认证处理器 - 处理用户登录和注册"""
    
    ver_manager = VerificationManager(env="dev")

    @staticmethod
    def handle_login(phone: str, password: str) -> tuple:
        """
        🔑 处理用户登录
        
        参数:
            phone: 用户手机号
            password: 用户密码
            
        返回:
            Gradio界面更新元组，包含完整的会话和消息数据
        """
        logger.info(f"🔑 开始处理用户登录: {phone}")
        
        # 👤 获取用户信息
        user = db_manager.get_user(phone)
        if not user:
            logger.warning(f"⚠️ 手机号未注册: {phone}")
            return (gr.update(),) * 12 + (
                gr.update(value="<div style='color: #dc3545;'>❌ 该手机号未注册，请先去注册</div>"),
            )

        # ✅ 验证密码
        phone_db, pwd_db, name_db, role_db = user

        if pwd_db != password:
            logger.warning(f"⚠️ 密码错误: {phone}")
            return (gr.update(),) * 12 + (
                gr.update(value="<div style='color: #dc3545;'>❌ 密码错误</div>"),
            )

        # ✅ 登录成功后
        try:
            # 🚀 预加载用户所有数据
            user_data = chat_management.chat_manager.ensure_all_sessions_loaded(phone)
            
            # 📝 获取显示名称
            display_name = name_db if name_db else phone
            user_html = config.i18n.get('welcome_user', display_name, phone)
            
            # ✅ 确保有默认会话
            if not user_data["default_sid"]:
                user_data["default_sid"] = chat_management.chat_manager.create_session(phone, "欢迎使用")
                user_data = chat_management.chat_manager.ensure_all_sessions_loaded(phone)
            
            # 📋 获取默认会话的消息
            messages = chat_management.chat_manager.get_messages(
                user_data["default_sid"], 
                limit=None
            )
            history = [{"role": role, "content": content} for role, content, _ in messages]
            
            logger.info(
                f"🎉 用户登录成功: {phone}, "
                f"会话总数={user_data['total_sessions']}, "
                f"消息总数={user_data['total_messages']}"
            )

            # 🎯 获取用户角色
            user_role = "管理员" if role_db == 1 else "普通用户"

            return (
                gr.update(visible=False),  # 隐藏登录页
                gr.update(visible=False),  # 隐藏注册页
                gr.update(visible=True),   # 显示聊天页
                phone,                     # 当前用户手机号
                user_data["default_sid"],  # 默认会话ID
                user_html,                 # 用户欢迎信息
                gr.update(choices=user_data["session_choices"], value=user_data["default_sid"]),  # 会话列表
                user_data["default_sid"],  # 当前选中的会话
                history,                   # 聊天历史
                gr.update(value=""),       # 清空登录提示
                gr.update(visible=False),  # 隐藏后续问题按钮1
                gr.update(visible=False),  # 隐藏后续问题按钮2
                gr.update(visible=False),  # 隐藏后续问题按钮3
            )
        
        except Exception as e:
            logger.error(f"❌ 登录后数据加载失败: {str(e)}")
            # 🆕 创建基础会话作为后备
            fallback_sid = chat_management.chat_manager.create_session(phone, "欢迎使用")
            messages = chat_management.chat_manager.get_messages(fallback_sid)
            history = [{"role": role, "content": content} for role, content, _ in messages]
            
            # 🔄 刷新会话列表
            session_choices = SessionManager.build_session_choices(phone)
            
            return (
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=True),
                phone,
                fallback_sid,
                config.i18n.get('welcome_user', name_db or phone, phone),
                gr.update(choices=session_choices, value=fallback_sid),  # 刷新会话列表
                fallback_sid,
                history,
                gr.update(value=""),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
            )


    @staticmethod
    def handle_register(
        name: str, 
        phone: str, 
        password: str, 
        code: str, 
        codes_dict: dict
    ) -> tuple:
        """
        📝 处理用户注册 - 确保注册后立即显示会话
        
        参数:
            name: 用户名
            phone: 手机号
            password: 密码
            code: 验证码
            codes_dict: 验证码字典
            
        返回:
            Gradio界面更新元组，包含新会话和欢迎消息
        """
        logger.info(f"📝 开始处理用户注册: {phone}")

        # 🔍 验证验证码
        if not code:
            return (gr.update(),) * 12 + (
                gr.update(value="<div style='color: #dc3545;'>❌ 请输入验证码</div>"),
                gr.update(),
            )
        
        stored_code = codes_dict.get(phone, "")
        if not stored_code or code != stored_code:
            return (gr.update(),) * 12 + (
                gr.update(value="<div style='color: #dc3545;'>❌ 验证码错误或已过期</div>"),
                gr.update(),
            )
        
        # ✅ 验证码正确，从字典中移除
        if phone in codes_dict:
            del codes_dict[phone]
            logger.info(f"🔑 [AuthHandler] 验证码已使用并移除")
        
        # 📝 注册用户（会自动创建默认会话）
        success, message = user_management.user_manager.register(phone, password, name)
        
        if success:
            # ✅ 注册成功后
            try:
                # 🚀 预加载用户所有数据
                user_data = chat_management.chat_manager.ensure_all_sessions_loaded(phone)
                
                # 📝 获取显示名称
                display_name = name if name else phone
                user_html = config.i18n.get('welcome_user', display_name, phone)
                
                # ✅ 确保有默认会话
                if not user_data["default_sid"]:
                    user_data["default_sid"] = chat_management.chat_manager.create_session(phone, "欢迎使用")
                    user_data = chat_management.chat_manager.ensure_all_sessions_loaded(phone)
                
                # 📋 获取默认会话的消息
                messages = chat_management.chat_manager.get_messages(
                    user_data["default_sid"], 
                    limit=None
                )
                history = [{"role": role, "content": content} for role, content, _ in messages]
                
                logger.info(
                    f"🎊 用户注册成功: {phone}, "
                    f"创建会话={user_data['total_sessions']}, "
                    f"消息={user_data['total_messages']}"
                )
                # ✅ 注册成功后立即刷新会话列表
                session_choices = SessionManager.build_session_choices(phone)
                
                return (
                    gr.update(visible=False),  # 🙈 隐藏登录页
                    gr.update(visible=False),  # 🙈 隐藏注册页
                    gr.update(visible=True),   # 👁️ 显示聊天页
                    phone,                     # 📱 当前用户手机号
                    user_data["default_sid"],  # 🆔 默认会话ID
                    user_html,                 # 👤 用户欢迎信息
                    gr.update(choices=session_choices, value=user_data["default_sid"]),  # ✅ 强制刷新会话列表
                    user_data["default_sid"],  # 🎯 当前选中的会话
                    history,                   # 💬 聊天历史（所有消息）
                    gr.update(value=""),       # 🧹 清空注册提示
                    gr.update(visible=False),  # 🙈 隐藏后续问题按钮1
                    gr.update(visible=False),  # 🙈 隐藏后续问题按钮2
                    gr.update(visible=False),  # 🙈 隐藏后续问题按钮3
                )
                
            except Exception as e:
                logger.error(f"❌ 注册后数据加载失败: {str(e)}")
                # 🆕 创建基础会话作为后备
                fallback_sid = chat_management.chat_manager.create_session(phone, "欢迎使用")
                messages = chat_management.chat_manager.get_messages(fallback_sid)
                history = [{"role": role, "content": content} for role, content, _ in messages]
                
                # ✅ 立即刷新会话列表
                session_choices = SessionManager.build_session_choices(phone)
                
                return (
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=True),
                    phone,
                    fallback_sid,
                    config.i18n.get('welcome_user', name or phone, phone),
                    gr.update(choices=session_choices, value=fallback_sid),  # ✅ 刷新会话列表
                    fallback_sid,
                    history,
                    gr.update(value=""),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                )

        # ❌ 注册失败
        logger.warning(f"❌ 注册失败: {phone} - {message}")
        return (gr.update(),) * 12 + (
            gr.update(value=f"<div style='color: #dc3545;'>❌ {message}</div>"),
        )


    @staticmethod
    def handle_logout() -> tuple:
        """
        🚪 安全退出登录
        
        功能特点：
        1. ✅ 彻底解决空值警告问题
        2. 🎯 显示友好的退出成功提示
        3. 🛡️ 防止会话切换事件触发
        4. 🔄 完整重置所有界面状态
        
        设计思路：
        - 优先清空Radio组件，防止None值触发
        - 分步骤处理，确保每个组件状态正确
        - 添加清晰的退出确认消息
        
        返回:
            完整的13个Gradio组件更新元组
        """
        
        logger.info("🚪 开始处理用户退出登录")
        
        try:
            # 🎯 创建友好的退出成功提示
            exit_success_msg = """
            <div style='text-align: center; padding: 15px;'>
                <h3 style='color: #28a745; margin: 0;'>✅ 退出成功！</h3>
                <p style='color: #6c757d; margin: 5px 0;'>感谢您的使用，期待下次再见！</p>
                <small style='color: #6c757d;'>您的数据已安全保存</small>
            </div>
            """
            
            # 🔄 完整的界面重置状态（13个组件）
            return (
                gr.update(visible=True),                     # [1] 显示登录页
                gr.update(visible=False),                    # [2] 隐藏注册页
                gr.update(visible=False),                    # [3] 隐藏聊天页
                gr.update(value=""),                         # [4] 清空当前用户手机号
                gr.update(value=""),                         # [5] 清空当前会话ID
                gr.update(value=""),                         # [6] 清空用户显示信息
                gr.update(value=[]),                         # [7] 清空聊天历史
                gr.update(choices=[], value=None, interactive=False),  # [8] 关键：清空会话列表并禁用
                gr.update(value=None),                       # [9] 确保会话选择器无值
                gr.update(value=exit_success_msg),           # [10] 显示退出成功消息
                gr.update(visible=False),                    # [11] 隐藏后续问题按钮1
                gr.update(visible=False),                    # [12] 隐藏后续问题按钮2
                gr.update(visible=False),                    # [13] 隐藏后续问题按钮3
            )
            
        except Exception as e:
            # ❌ 错误兜底处理 - 确保界面总能正确重置
            logger.error(f"❌ 退出登录异常: {str(e)} - 执行兜底重置")
            
            # 🛡️ 安全兜底：无论如何都要重置界面
            return (
                gr.update(visible=True),                     # [1] 显示登录页
                gr.update(visible=False),                    # [2] 隐藏注册页
                gr.update(visible=False),                    # [3] 隐藏聊天页
                gr.update(value=""),                         # [4] 清空当前用户手机号
                gr.update(value=""),                         # [5] 清空当前会话ID
                gr.update(value=""),                         # [6] 清空用户显示信息
                gr.update(value=[]),                         # [7] 清空聊天历史
                gr.update(choices=[], value=None, interactive=False),  # [8] 关键：清空会话列表
                gr.update(value=None),                       # [9] 确保会话选择器无值
                gr.update(value="<div style='color: #dc3545;'>⚠️ 退出完成（遇到小问题，但已安全登出）</div>"),
                gr.update(visible=False),                    # [11] 隐藏后续问题按钮1
                gr.update(visible=False),                    # [12] 隐藏后续问题按钮2
                gr.update(visible=False),                    # [13] 隐藏后续问题按钮3
            )

    @staticmethod
    def handle_logout_with_confirmation() -> tuple:
        """
        🚪 带确认对话框的退出登录 - 增强版
        
        功能特点：
        1. 📊 记录详细的退出日志
        2. 💬 添加退出确认提示
        3. 🧹 彻底清理用户会话数据
        
        返回:
            与 handle_logout 相同的13个组件更新元组
        """
        
        logger.info("🚪 用户确认退出登录，开始执行数据清理...")
        
        # 📝 记录退出时间
        exit_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"📊 用户退出登录时间: {exit_time}")
        
        # 🔄 使用主退出逻辑
        return AuthHandler.handle_logout()

    @staticmethod
    def handle_logout_js_confirmation() -> str:
        """
        🖱️ JavaScript退出确认对话框
        
        返回:
            JavaScript确认代码
        """
        return """
        function confirmLogout() {
            return confirm('确定要退出登录吗？\\n\\n您的所有聊天记录已自动保存。');
        }
        """