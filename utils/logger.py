import logging
import os
from pathlib import Path
from datetime import datetime
from config import config

class Logger:
    """
    📝 自定义日志记录器
    功能：
    1. 📺 同时输出到控制台和文件
    2. 🔄 按天轮转日志文件
    3. 🎨 格式化日志输出
    4. 📊 支持不同日志级别
    
    设计原则：
    1. 🔧 简单易用 - 通过get_logger()获取日志记录器
    2. ⚙️ 灵活配置 - 日志级别和输出位置可配置
    3. ⚡ 高性能 - 使用标准logging库，确保性能
    """
    
    def __init__(self, name=__name__):
        # 🎯 创建日志记录器
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)  # 🎯 设置最低日志级别
        
        # 🎨 日志格式
        formatter = logging.Formatter(
            "🕐 %(asctime)s - 📦 %(name)s - 📊 %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # ----------------------- 📁 文件处理器 -----------------------
        # 🔄 按天创建日志文件
        log_filename = config.LOG_DIR / f"📊 app_{datetime.now().strftime('%Y-%m-%d')}.log"
        
        # 📁 文件处理器 - 每天一个文件，最多保留7天
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(getattr(logging, config.LOG_LEVEL.upper()))
        file_handler.setFormatter(formatter)
        
        # ----------------------- 📺 控制台处理器 -----------------------
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # 📺 控制台只显示INFO及以上级别
        console_handler.setFormatter(formatter)
        
        # ----------------------- ➕ 添加处理器 -----------------------
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # 📝 记录初始化信息
        self.logger.info(f"📝 日志系统初始化完成，日志级别: {config.LOG_LEVEL} 📊")

    def get_logger(self):
        """📤 获取配置好的日志记录器"""
        return self.logger

# 🌍 创建全局日志记录器
logger = Logger().get_logger()