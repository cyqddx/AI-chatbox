"""
🚀 主应用入口
"""

import os
from config import config
from pathlib import Path

# 🎯 设置Gradio临时目录
os.environ["GRADIO_TEMP_DIR"] = str(config.BASE_DIR / "gradio_tmp")
Path(os.environ["GRADIO_TEMP_DIR"]).mkdir(exist_ok=True)

import random
import datetime
import threading
import time
import gradio as gr
from modules.ui_handlers import (
    SessionManager,
    MessageHandler,
    FileUploadHandler,
    AuthHandler,
)
from utils.logger import logger
from utils.database import db_manager
from modules.admin_management import admin_manager


# ----------------------- 🚀 初始化函数 -----------------------
def init_app():
    """🚀 增强的应用初始化"""
    logger.info("🚀 启动增强型应用程序初始化...")
    
    # 📁 检查并创建所有必要目录
    dirs_to_check = [
        config.LOG_DIR,
        config.DATA_DIR,
        config.UPLOADS_DIR,
        config.VECTOR_STORE_DIR,
        config.DB_DIR,
    ]
    
    for directory in dirs_to_check:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 目录就绪: {directory}")
    
    # 🗄️ 初始化数据库
    db_manager._init_db()
    logger.info("💾 数据库初始化完成")
    
    # ✅ 验证数据完整性
    validate_data_integrity()
    
    logger.info("✅ 应用程序初始化完成")


def validate_data_integrity():
    """🔍 验证数据完整性"""
    try:
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # 📊 统计会话和消息
        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM messages")
        message_count = cursor.fetchone()[0]
        
        # 🔍 验证消息与会话的关联
        cursor.execute("""
            SELECT COUNT(*) FROM messages m 
            LEFT JOIN sessions s ON m.sid = s.sid 
            WHERE s.sid IS NULL
        """)
        orphan_messages = cursor.fetchone()[0]
        
        logger.info(
            f"📊 数据完整性检查: "
            f"会话={session_count}, 消息={message_count}, "
            f"孤立消息={orphan_messages}"
        )
        
        conn.close()
    except Exception as e:
        logger.error(f"❌ 数据完整性检查失败: {str(e)}")


# ----------------------- 🎨 主应用构建函数 -----------------------
def build_app() -> gr.Blocks:
    """
    🎨 构建Gradio应用程序
    使用预加载机制确保数据完整性
    """
    with gr.Blocks(
        theme="Soft",
        css=Path(config.STATIC_DIR / "styles.css").read_text(),
        title="🎓 近屿智能课程助手 - 增强版",
    ) as app:
        
        # ------------------ 🔧 状态变量 ------------------
        current_user = gr.State("")  # 📱 当前用户手机号（字符串）
        current_sid = gr.State("")   # 🆔 当前会话ID（UUID字符串格式）
        verification_codes = gr.State({})  # 🔑 验证码字典
        user_sessions = gr.State({})  # 🗂️ 用户会话缓存
        
        # ------------------ 🔐 登录页面 ------------------
        with gr.Column(visible=True, elem_classes="login-container") as login_page:
            gr.HTML(f'<div class="auth-title">{config.i18n.get("welcome_back")}</div>')
            
            login_phone = gr.Textbox(
                label=config.i18n.get("phone_placeholder"),
                placeholder=config.i18n.get("phone_placeholder"),
                elem_classes="auth-input",
            )
            login_pwd = gr.Textbox(
                label=config.i18n.get("password_placeholder"),
                type="password",
                placeholder=config.i18n.get("password_placeholder"),
                elem_classes="auth-input",
            )
            
            login_btn = gr.Button(config.i18n.get("login"), elem_classes="auth-btn", variant="primary")
            register_link = gr.Button(
                config.i18n.get("no_account"), 
                elem_classes="auth-btn", 
                variant="secondary"
            )
            login_message = gr.HTML(elem_classes="auth-message")
        
        # ------------------ 📝 注册页面 ------------------
        with gr.Column(visible=False, elem_classes="register-container") as register_page:
            gr.HTML(f'<div class="auth-title">{config.i18n.get("create_account")}</div>')
            
            reg_username = gr.Textbox(
                label="👤 用户名",
                placeholder="请输入用户名",
                elem_classes="auth-input",
            )
            reg_phone = gr.Textbox(
                label=config.i18n.get("phone_placeholder"),
                placeholder=config.i18n.get("phone_placeholder"),
                elem_classes="auth-input",
            )
            reg_pwd = gr.Textbox(
                label=config.i18n.get("password_placeholder"),
                type="password",
                placeholder=config.i18n.get("password_placeholder"),
                elem_classes="auth-input",
            )
            reg_code = gr.Textbox(
                label="🔑 验证码", 
                placeholder="请输入验证码", 
                elem_classes="auth-input"
            )
            
            send_code_btn = gr.Button("📨 发送验证码", elem_classes="auth-btn")
            reg_btn = gr.Button(config.i18n.get("register"), elem_classes="auth-btn", variant="primary")
            back_to_login = gr.Button(
                config.i18n.get("has_account"), 
                elem_classes="auth-btn", 
                variant="secondary"
            )
            register_message = gr.HTML(elem_classes="auth-message")
        
        # ------------------ 💬 聊天页面 ------------------
        with gr.Column(visible=False, elem_classes="chat-container") as chat_page:
            # 📱 顶部导航栏
            with gr.Row(elem_classes="header-bar"):
                with gr.Column(scale=1, min_width=100):
                    user_display = gr.HTML(elem_classes="user-info")
                with gr.Column(scale=2, min_width=200):
                    gr.HTML(
                        "<div class='welcome-title'>🎓 欢迎使用近屿智能课程咨询助手</div>",
                        elem_classes="welcome-title-container"
                    )
                with gr.Column(scale=1, min_width=100):
                    logout_btn = gr.Button(config.i18n.get("exit"), elem_classes="logout-btn")
            
            # 🏗️ 主布局
            with gr.Row(scale=1, elem_classes="main-layout", equal_height=False):
                # 📋 左侧会话列表
                with gr.Column(elem_classes="sidebar", scale=2):
                    new_session_btn = gr.Button(
                        config.i18n.get("new_chat"), 
                        elem_classes="new-session-btn"
                    )
                    
                    session_radio = gr.Radio(
                        label=config.i18n.get("history_sessions"),
                        choices=[],
                        value=None,
                        interactive=True,
                        type="value",
                        elem_classes="session-radio",
                    )
                
                # 💬 右侧聊天区域
                with gr.Column(scale=8, elem_classes="chat-area-full"):
                    chatbot = gr.Chatbot(
                        label="💬 对话记录",
                        elem_classes="chatbot-container-full",
                        height=600,
                        avatar_images=(
                            "https://api.dicebear.com/7.x/avataaars/svg?seed=user",
                            "https://api.dicebear.com/7.x/bottts/svg?seed=ai"
                        ),
                        type="messages",
                    )
                    
                    # 🔮 后续问题区域
                    with gr.Row(elem_classes="next-questions-row"):
                        next_q_btn_1 = gr.Button("", visible=False, scale=1)
                        next_q_btn_2 = gr.Button("", visible=False, scale=1)
                        next_q_btn_3 = gr.Button("", visible=False, scale=1)
                    
                    # ✍️ 输入区域
                    with gr.Row(elem_classes="input-container"):
                        upload_btn = gr.UploadButton(
                            config.i18n.get("upload_file"),
                            file_count="multiple",
                            file_types=[
                                ".pdf", ".docx", ".txt", 
                                ".pptx", ".html", ".ipynb"
                            ],
                            elem_classes="upload-btn",
                            size="sm"
                        )
                        message_input = gr.Textbox(
                            placeholder=config.i18n.get("input_placeholder"),
                            scale=7,
                            container=False,
                            elem_classes="message-input"
                        )
                        send_btn = gr.Button(config.i18n.get("send_message"), elem_classes="send-btn")
        

        # ------------------ 🔗 事件绑定 ------------------
        
        # 🔄 登录/注册页面切换
        register_link.click(
            lambda: (gr.update(visible=False), gr.update(visible=True)),
            None,
            [login_page, register_page]
        )

        back_to_login.click(
            lambda: (gr.update(visible=True), gr.update(visible=False)),
            None,
            [login_page, register_page]
        )
        
        # 🔑 登录事件
        login_btn.click(
            AuthHandler.handle_login,
            [login_phone, login_pwd],
            [
                login_page, register_page, chat_page,
                current_user, current_sid, user_display,
                session_radio, session_radio, chatbot,
                login_message,
                next_q_btn_1, next_q_btn_2, next_q_btn_3
            ]
        )

        # 📝 注册事件
        reg_btn.click(
            AuthHandler.handle_register,
            [reg_username, reg_phone, reg_pwd, reg_code, verification_codes],
            [
                login_page, register_page, chat_page,
                current_user, current_sid, user_display,
                session_radio, session_radio, chatbot,
                register_message,
                next_q_btn_1, next_q_btn_2, next_q_btn_3
            ]
        )

        # 📱 发送验证码
        send_code_btn.click(
            lambda phone, codes: (
                gr.update(
                    value=(
                        "<div style='color: #28a745;'>✅ 验证码已发送</div>"
                        if AuthHandler.ver_manager.send_code(phone, codes)
                        else "<div style='color: #dc3545;'>❌ 验证码发送失败</div>"
                    )
                ),
                codes,
            ),
            [reg_phone, verification_codes],
            [register_message, verification_codes],
        )
        
        # 💬 消息发送
        send_btn.click(
            MessageHandler.process_message,
            [message_input, current_sid, current_user, chatbot],  # ✅ 正确的参数顺序
            [chatbot, message_input, current_sid, next_q_btn_1, next_q_btn_2, next_q_btn_3]
        )
        message_input.submit(
            MessageHandler.process_message,
            [message_input, current_sid, current_user, chatbot],  # ✅ 正确的参数顺序
            [chatbot, message_input, current_sid, next_q_btn_1, next_q_btn_2, next_q_btn_3]
        )
        
        # 📁 文件上传
        upload_btn.upload(
            lambda files, phone, sid, history: (
                FileUploadHandler.handle_file_upload(files, phone, sid, history)
            ),
            [upload_btn, current_user, current_sid, chatbot],
            [chatbot, current_sid, session_radio],
            show_progress="full"
        )

        # ➕ 新建会话
        new_session_btn.click(
            SessionManager.create_new_session,
            [current_user],
            [chatbot, current_sid, session_radio, next_q_btn_1, next_q_btn_2, next_q_btn_3]
        )

        # 🔄 使用更安全的会话切换
        session_radio.change(
            fn=SessionManager.safe_switch_session,
            inputs=[session_radio, current_user],
            outputs=[
                chatbot,           # 聊天历史
                current_sid,       # 当前会话ID
                next_q_btn_1,      # 后续问题按钮1
                next_q_btn_2,      # 后续问题按钮2
                next_q_btn_3       # 后续问题按钮3
            ]
        )

        # 🚪 退出登录 - 使用专门的退出处理方法
        logout_btn.click(
            fn=AuthHandler.handle_logout,  # ✅ 使用专门的退出处理方法
            inputs=None,                   # 📝 退出不需要输入参数
            outputs=[
                login_page,      # [1] 登录页面
                register_page,   # [2] 注册页面
                chat_page,       # [3] 聊天页面
                current_user,    # [4] 当前用户手机号
                current_sid,     # [5] 当前会话ID
                user_display,    # [6] 用户显示
                chatbot,         # [7] 聊天历史
                session_radio,   # [8] 会话列表（关键修复）
                session_radio,   # [9] 当前选中会话
                login_message,   # [10] 登录消息（显示退出成功）
                next_q_btn_1,    # [11] 后续问题按钮1
                next_q_btn_2,    # [12] 后续问题按钮2
                next_q_btn_3     # [13] 后续问题按钮3
            ]
        )

        # 🔮 后续问题按钮
        for btn in [next_q_btn_1, next_q_btn_2, next_q_btn_3]:
            btn.click(
                MessageHandler.select_next_question,
                [btn, current_sid, current_user, chatbot],
                [chatbot, message_input, current_sid, next_q_btn_1, next_q_btn_2, next_q_btn_3]
            )
    
    return app


# ================================ 管理员后台启动（独立线程） ================================

def start_admin_server():
    """启动管理员后台服务（独立端口）"""
    try:
        logger.info("🚀 启动管理员后台服务...")
        
        # 构建管理员界面
        admin_app = admin_manager.build_admin_interface()
        
        # 启动管理员服务
        admin_app.launch(
            server_name="0.0.0.0",
            server_port=7891,  # 管理员专用端口
            share=False,
            inbrowser=False,
            show_error=True,
            quiet=False,
            prevent_thread_lock=False  # 允许线程阻塞
        )
        
    except Exception as e:
        logger.error(f"❌ 管理员后台启动失败: {str(e)}")
        raise


# ----------------------- 🚀 主程序入口 -----------------------
if __name__ == "__main__":
    # 🚀 初始化应用程序
    init_app()
    
    # 启动管理员后台（在主线程外）
    # 延迟启动管理员后台，确保主应用先启动
    def delayed_admin_start():
        time.sleep(2)  # 延迟2秒启动管理员后台
        start_admin_server()
    
    admin_thread = threading.Thread(
        target=delayed_admin_start,
        daemon=True,
        name="AdminServer"
    )
    admin_thread.start()
    
    logger.info("🚀 管理员后台线程已启动")
    
    # 🎨 构建主应用
    app = build_app()
    
    # 🌐 启动主应用
    logger.info("="*50)
    logger.info("🌐 主应用: http://localhost:7890")
    logger.info("🌐 管理员后台: http://localhost:7891")
    logger.info("管理员账号: admin")
    logger.info("管理员密码: 123456")
    logger.info("="*50)
    
    app.launch(
        server_name="0.0.0.0",
        server_port=7890,
        share=False,
        inbrowser=True,
        show_error=True
    )