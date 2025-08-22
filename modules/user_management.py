from utils.database import db_manager
from utils.logger import logger
import datetime
from modules.chat_management import chat_manager


class UserManager:
    """
    👥 用户管理模块
    功能：
      1. 📝 用户注册（自动创建默认会话）
      2. 🔑 用户登录（预加载完整数据）
      3. 👤 用户信息管理
    
    设计原则：
      1. 🔒 安全性 - 不存储明文密码
      2. ✅ 数据完整性 - 确保用户数据一致性
      3. 🎯 用户体验 - 注册后立即有可用的会话
    """
    
    def register(self, phone: str, pwd: str, name: str) -> tuple:
        """
        📝 用户注册
        注册成功后自动创建第一个会话并添加欢迎消息
        
        参数:
          phone: 手机号
          pwd: 密码
          name: 用户名
        返回:
          (成功状态, 消息)
        """
        logger.info(f"📝 开始用户注册: {phone}")
        
        # ✅ 验证手机号格式
        if not (phone.isdigit() and len(phone) == 11):
            logger.warning(f"⚠️ 手机号格式错误: {phone}")
            return False, "⚠️ 请输入11位手机号"
        
        # ✅ 验证密码长度
        if len(pwd) < 6:
            logger.warning(f"⚠️ 密码长度不足: {len(pwd)} < 6")
            return False, "⚠️ 密码至少6位"
        
        # 🔍 检查用户是否已存在
        if db_manager.get_user(phone):
            logger.warning(f"⚠️ 手机号已存在: {phone}")
            return False, "⚠️ 该手机号已注册，可直接登录"
        
        # 📝 创建用户
        success, message = db_manager.add_user(phone, pwd, name or phone)
        if success:
            # ✅ 注册成功后立即创建默认会话
            try:
                sid = chat_manager.create_first_session_for_new_user(phone)
                logger.info(f"🎉 用户注册成功并创建默认会话: {phone} -> {sid}")
                return True, "✅ 注册成功，正在跳转聊天页..."
            except Exception as e:
                logger.error(f"❌ 创建默认会话失败: {phone} - {str(e)}")
                # 📝 即使会话创建失败也返回成功
                return True, "✅ 注册成功，正在跳转聊天页..."
        
        logger.error(f"❌ 注册失败: {phone} - {message}")
        return False, f"⚠️ 注册失败: {message}"
    
    def login(self, phone: str, password: str) -> tuple[bool, str]:
        """
        🔑 用户登录
        登录后预加载用户的所有会话和消息
        
        参数:
          phone: 手机号
          pwd: 密码
        返回:
          (成功状态, 消息)
        """
        logger.info(f"🔑 开始用户登录: {phone}")
        
        # 👤 获取用户信息
        user = db_manager.get_user(phone)
        if not user:
            logger.warning(f"⚠️ 手机号未注册: {phone}")
            return False, "⚠️ 该手机号未注册，请先去注册"
        
        # ✅ 验证密码
        phone_db, pwd_db, name_db, role_db = user  # 解包四个字段
        if pwd_db != password:
            logger.warning(f"⚠️ 密码错误: {phone}")
            return False, "⚠️ 密码错误"
        
        # ✅ 确保用户至少有一个会话
        chat_manager.ensure_user_has_session(phone)

        # ✅ 用户信息管理
        if role_db == 1:
            role_info = "管理员"
        else:
            role_info = "普通用户"
        
        logger.info(f"✅ 用户登录成功: {phone} (角色: {role_info})")
        return True, f"✅ 登录成功，欢迎回来，{name_db}！您是{role_info}。正在跳转聊天页..."

    def get_user_info(self, phone: str) -> dict:
        """
        👤 获取用户信息
        
        参数:
          phone: 手机号
        返回:
          用户信息字典
        """
        logger.info(f"👤 获取用户信息: {phone}")
        
        user = db_manager.get_user(phone)
        if not user:
            logger.warning(f"⚠️ 用户不存在: {phone}")
            return None
        
        phone, _, name = user
        info = {
            "phone": phone,
            "name": name
        }
        logger.info(f"✅ 获取用户信息成功: {phone} -> {name}")
        return info

# 🌍 全局用户管理实例
user_manager = UserManager()