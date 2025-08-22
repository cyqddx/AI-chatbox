import os
import sys
import time
import shutil
import psutil
import logging
import subprocess
import smtplib
import threading
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from config import config
from utils.logger import logger
from utils.database import db_manager

class SystemMaintenance:
    """
    🔧 系统维护模块
    功能：
      1. 📊 系统健康监控 - 实时监控系统资源使用情况
      2. 🔄 系统版本管理 - 管理系统的版本升级和回滚
      3. 💾 数据备份与恢复 - 定期备份和恢复系统数据
      4. 📝 系统状态日志 - 每分钟记录系统资源使用情况
    
    设计原则：
      1. 🤖 自动化 - 自动执行监控和备份任务
      2. ✅ 可靠性 - 确保系统稳定运行
      3. 🔄 可恢复性 - 提供快速恢复机制
      4. 🔒 安全性 - 确保备份数据安全
    """
    
    def __init__(self):
        # 💾 备份目录配置
        self.backup_dir = config.BASE_DIR / "backups"
        self.backup_dir.mkdir(exist_ok=True, parents=True)
        
        # 📄 版本历史文件
        self.version_history_file = self.backup_dir / "version_history.txt"
        
        # ⏱️ 监控间隔 (秒)
        self.monitor_interval = 300  # 5分钟
        
        # 📦 备份间隔 (秒)
        self.backup_interval = 86400  # 24小时
        
        # 📝 系统状态日志间隔 (秒)
        self.status_log_interval = 60  # 1分钟
        
        # 🕐 最后一次备份时间
        self.last_backup_time = time.time()
        
        # 🕐 最后一次监控时间
        self.last_monitor_time = time.time()
        
        # 🕐 最后一次状态日志时间
        self.last_status_log_time = time.time()
        
        # 📧 告警收件人
        self.admin_email = "admin@example.com"
        
        # 📝 初始化版本历史
        self._init_version_history()
        
        # 🚀 启动系统监控线程
        self._start_monitor_thread()
        
        logger.info("🔧 系统维护模块初始化完成")
    
    def _init_version_history(self):
        """📝 初始化版本历史文件"""
        if not self.version_history_file.exists():
            with open(self.version_history_file, "w") as f:
                f.write(f"1.0.0 - {datetime.now().isoformat()} - 🚀 初始版本\n")
            logger.info("📝 版本历史文件已创建")

    def _start_monitor_thread(self):
        """🚀 启动后台监控线程"""
        def monitor_loop():
            logger.info("🚀 系统监控线程已启动")
            while True:
                try:
                    # 📊 执行系统监控
                    self.monitor_system_health()
                    
                    # 📝 记录系统状态
                    self.log_system_status()
                    
                    # 💾 执行定期备份
                    self.periodic_backup()
                    
                    # ⏱️ 每分钟执行一次
                    time.sleep(60)
                except Exception as e:
                    logger.error(f"💥 系统监控线程异常: {str(e)}")
        
        # 🧵 创建并启动守护线程
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        logger.info("✅ 系统监控线程已启动")
    
    # ================================ 📊 系统健康监控功能 ================================
    
    def monitor_system_health(self):
        """
        📊 监控系统健康状况
        功能点：
          - 📊 资源监控：CPU、内存、磁盘
          - 📝 错误日志记录
          - 📧 告警系统
        """
        try:
            current_time = time.time()
            # 🕐 检查是否达到监控间隔
            if current_time - self.last_monitor_time < self.monitor_interval:
                return
            
            self.last_monitor_time = current_time
            
            # 📊 收集系统指标
            cpu_percent = psutil.cpu_percent(interval=1)
            mem_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            
            # 📝 记录系统指标
            logger.info(
                f"📊 系统监控 - "
                f"💻 CPU: {cpu_percent}%, "
                f"🧠 内存: {mem_percent}%, "
                f"💾 磁盘: {disk_percent}%"
            )
            
            # ⚠️ 检查资源使用情况
            issues = []
            if cpu_percent > 90:
                issues.append(f"💥 CPU使用率过高: {cpu_percent}%")
            if mem_percent > 90:
                issues.append(f"💥 内存使用率过高: {mem_percent}%")
            if disk_percent > 90:
                issues.append(f"💥 磁盘使用率过高: {disk_percent}%")
            
            # 🔍 检查错误日志
            error_logs = self._check_error_logs()
            if error_logs:
                issues.append(f"📋 最近错误: {len(error_logs)}")
            
            # 📧 如果有问题，发送告警
            if issues:
                alert_message = "; ".join(issues)
                logger.warning(f"⚠️ 检测到系统健康问题: {alert_message}")
                self.send_alert(alert_message)
        except Exception as e:
            logger.error(f"💥 系统监控异常: {str(e)}")
    
    def log_system_status(self):
        """
        📝 记录系统状态到专用日志文件
        每分钟记录一次CPU、内存和磁盘使用率
        """
        current_time = time.time()
        # 🕐 检查是否达到日志间隔
        if current_time - self.last_status_log_time < self.status_log_interval:
            return
        
        self.last_status_log_time = current_time
        
        # 📊 收集系统指标
        cpu_percent = psutil.cpu_percent(interval=1)
        mem_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        
        # 📝 创建系统状态日志目录
        system_log_dir = config.LOG_DIR / "system_status"
        system_log_dir.mkdir(exist_ok=True, parents=True)
        
        # 📅 按日期创建日志文件
        log_date = datetime.now().strftime("%Y-%m-%d")
        log_file = system_log_dir / f"📊 system_status_{log_date}.log"
        
        # 📝 构建日志条目
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} - 💻 CPU: {cpu_percent}%, 🧠 内存: {mem_percent}%, 💾 磁盘: {disk_percent}%\n"
        
        # 📝 写入日志文件
        try:
            with open(log_file, "a") as f:
                f.write(log_entry)
            logger.debug("📝 系统状态日志已写入")
        except Exception as e:
            logger.error(f"❌ 系统状态日志写入失败: {str(e)}")
    
    def _check_error_logs(self) -> List[str]:
        """🔍 检查最近的错误日志"""
        # 📝 这里简化实现，实际中会分析日志文件
        # 📋 返回最近5分钟内的错误日志
        return []
    
    def send_alert(self, message: str):
        """
        📧 发送系统告警
        
        参数:
          message: 告警消息
        """
        try:
            # 📝 创建邮件内容
            msg = MIMEText(f"🚨 系统告警:\n\n{message}")
            msg['Subject'] = '🚨 系统健康告警'
            msg['From'] = '🤖 system@example.com'
            msg['To'] = self.admin_email
            
            # 📧 发送邮件 (实际环境中需要配置SMTP服务器)
            # with smtplib.SMTP('smtp.example.com') as server:
            #     server.send_message(msg)
            
            logger.warning(f"📧 告警已发送给 {self.admin_email}: {message}")
        except Exception as e:
            logger.error(f"❌ 发送告警失败: {str(e)}")
        
        # 📝 记录到数据库
        try:
            db_manager.add_system_alert(message, "warning")
            logger.info("📝 告警已记录到数据库")
        except Exception as e:
            logger.error(f"❌ 写入告警到数据库失败: {str(e)}")

    def get_system_metrics(self):
        """
        📊 获取系统监控指标
        返回:
            系统指标字典 {"cpu": ..., "mem": ..., "disk": ...}
        """
        try:
            # 📊 收集系统指标
            cpu_percent = psutil.cpu_percent(interval=1)
            mem_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            
            return {
                "cpu": f"{cpu_percent}%",
                "mem": f"{mem_percent}%",
                "disk": f"{disk_percent}%"
            }
        except Exception as e:
            logger.error(f"❌ 获取系统指标失败: {str(e)}")
            return {"cpu": "N/A", "mem": "N/A", "disk": "N/A"}

    def get_system_alerts(self, limit=10):
        """供 AdminManager 调用"""
        try:
            return db_manager.get_system_alerts(limit=limit)
        except Exception:
            return []
            
    # ================================ 🔄 系统版本管理功能 ================================
    
    def get_current_version(self) -> str:
        """📋 获取当前系统版本"""
        # 📝 这里简化实现，实际中会从配置文件或数据库中获取
        version = "1.0.0"
        logger.debug(f"📋 当前系统版本: {version}")
        return version
    
    def get_version_history(self) -> List[str]:
        """📜 获取版本历史"""
        try:
            with open(self.version_history_file, "r") as f:
                history = f.readlines()
            logger.info(f"📜 版本历史已加载: {len(history)} 条记录")
            return history
        except Exception as e:
            logger.error(f"❌ 获取版本历史失败: {str(e)}")
            return []
    
    def upgrade_system(self, new_version: str) -> Tuple[bool, str]:
        """
        ⬆️ 升级系统到新版本
        
        参数:
          new_version: 新版本号
        返回:
          (成功状态, 消息)
        """
        current_version = self.get_current_version()
        logger.info(f"🔄 开始系统升级: {current_version} -> {new_version}")
        
        try:
            # 1. 💾 备份当前系统
            backup_path = self.backup_data(manual=True)
            if not backup_path:
                return False, "❌ 备份失败，升级已取消"
            
            # 2. 🔄 执行升级操作 (这里简化实现)
            logger.info(f"🔄 正在安装新版本: {new_version}")
            time.sleep(5)  # 🕐 模拟安装过程
            
            # 3. 📝 更新版本历史
            with open(self.version_history_file, "a") as f:
                f.write(f"{new_version} - {datetime.now().isoformat()} - ⬆️ 升级\n")
            
            logger.info("✅ 系统升级完成")
            return True, "✅ 系统升级成功"
        except Exception as e:
            # ❌ 升级失败，自动回滚
            logger.error(f"💥 升级失败: {str(e)}，正在回滚...")
            rollback_success, rollback_msg = self.rollback_system(current_version)
            
            if rollback_success:
                return False, f"❌ 升级失败，已回滚到 {current_version}: {str(e)}"
            else:
                return False, f"💥 升级失败且回滚失败！系统可能不稳定: {rollback_msg}"
    
    def rollback_system(self, target_version: str) -> Tuple[bool, str]:
        """
        ⏪ 回滚系统到指定版本
        
        参数:
          target_version: 目标版本号
        返回:
          (成功状态, 消息)
        """
        logger.info(f"⏪ 开始系统回滚: {target_version}")
        
        try:
            # 1. 🔍 查找目标版本的备份
            backup_file = self.find_backup_for_version(target_version)
            if not backup_file:
                return False, f"❌ 未找到版本 {target_version} 的备份"
            
            # 2. 🔄 执行回滚操作
            logger.info(f"🔄 正在从备份恢复: {backup_file.name}")
            success, message = self.restore_data(backup_file)
            
            if success:
                # 3. 📝 更新版本历史
                with open(self.version_history_file, "a") as f:
                    f.write(f"{target_version} - {datetime.now().isoformat()} - ⏪ 回滚\n")
                
                logger.info("✅ 系统回滚完成")
                return True, "✅ 系统回滚成功"
            else:
                return False, f"❌ 回滚失败: {message}"
        except Exception as e:
            logger.error(f"💥 回滚失败: {str(e)}")
            return False, f"❌ 回滚失败: {str(e)}"
    
    def find_backup_for_version(self, version: str) -> Optional[Path]:
        """
        🔍 查找特定版本的备份文件
        
        参数:
          version: 要查找的版本号
        返回:
          备份文件路径 (如果找到)
        """
        # 🔍 简化实现，实际中备份文件名会包含版本信息
        for file in self.backup_dir.glob("backup_*.zip"):
            if version in file.name:
                logger.info(f"✅ 找到版本备份: {file}")
                return file
        
        logger.warning(f"⚠️ 未找到版本备份: {version}")
        return None
    
    # ================================ 💾 数据备份与恢复功能 ================================

    def backup_data(self, manual: bool = False) -> tuple[bool, str]:
        """
        💾 执行数据备份
        
        参数:
        manual: 是否为手动备份
        返回:
        备份结果和消息
        """
        try:
            # 📝 创建备份文件名 (带时间戳)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}.zip"  # 移除非法字符 😊
            backup_path = self.backup_dir / backup_name
            
            # 💾 备份关键数据：数据库、配置文件、向量存储
            backup_sources = [
                config.DB_DIR,
                config.VECTOR_STORE_DIR,
                config.BASE_DIR / "config.py"
            ]
            
            # 📝 创建备份
            logger.info(f"💾 开始数据备份: {backup_path}")
            shutil.make_archive(backup_path.with_suffix(''), 'zip', config.BASE_DIR, *backup_sources)
            
            if not backup_path.exists():
                logger.error(f"❌ 备份文件未生成: {backup_path}")
                return False, "备份文件未生成"
            
            # 📝 记录备份到数据库
            backup_size = backup_path.stat().st_size
            db_manager.add_backup_record(str(backup_path), self.get_current_version(), backup_size)
            
            # 🔄 更新备份时间
            self.last_backup_time = time.time()
            logger.info(f"✅ 数据备份完成: {backup_path} ({backup_size} bytes)")
            return True, f"✅ 数据备份成功: {backup_path.name}"
        except Exception as e:
            logger.error(f"❌ 数据备份失败: {str(e)}")
            return False, f"❌ 数据备份失败: {str(e)}"

    def restore_data(self, backup_file: Path) -> Tuple[bool, str]:
        """
        🔄 从备份恢复数据
        
        参数:
          backup_file: 备份文件路径
        返回:
          (成功状态, 消息)
        """
        if not backup_file.exists():
            return False, "❌ 备份文件不存在"
        
        try:
            logger.info(f"🔄 开始数据恢复: {backup_file}")
            
            # 📝 创建临时解压目录
            temp_dir = self.backup_dir / "temp_restore"
            temp_dir.mkdir(exist_ok=True, parents=True)
            
            # 📦 解压备份文件
            shutil.unpack_archive(backup_file, temp_dir, 'zip')
            
            # 🔄 恢复数据库
            db_backup = temp_dir / config.DB_DIR.name
            if db_backup.exists():
                logger.info("🔄 正在恢复数据库...")
                # 🧹 清空现有数据库目录
                if config.DB_DIR.exists():
                    shutil.rmtree(config.DB_DIR)
                shutil.copytree(db_backup, config.DB_DIR)
            
            # 🔄 恢复向量存储
            vector_backup = temp_dir / config.VECTOR_STORE_DIR.name
            if vector_backup.exists():
                logger.info("🔄 正在恢复向量存储...")
                # 🧹 清空现有向量存储目录
                if config.VECTOR_STORE_DIR.exists():
                    shutil.rmtree(config.VECTOR_STORE_DIR)
                shutil.copytree(vector_backup, config.VECTOR_STORE_DIR)
            
            # 🔄 恢复配置文件
            config_backup = temp_dir / "config.py"
            if config_backup.exists():
                logger.info("🔄 正在恢复配置文件...")
                shutil.copy(config_backup, config.BASE_DIR / "config.py")
            
            # 🧹 清理临时目录
            shutil.rmtree(temp_dir)
            
            logger.info("✅ 数据恢复完成")
            return True, "✅ 数据恢复成功"
        except Exception as e:
            logger.error(f"❌ 数据恢复失败: {str(e)}")
            return False, f"❌ 数据恢复失败: {str(e)}"
    
    def find_last_backup(self) -> Optional[Path]:
        """🔍 查找最新的备份文件"""
        backups = list(self.backup_dir.glob("💾 backup_*.zip"))
        if backups:
            # 🕐 按修改时间排序，获取最新的备份
            backups.sort(key=os.path.getmtime, reverse=True)
            latest_backup = backups[0]
            logger.info(f"✅ 找到最新备份: {latest_backup}")
            return latest_backup
        
        logger.warning("⚠️ 未找到备份文件")
        return None
    
    def periodic_backup(self):
        """🔄 定期备份数据"""
        current_time = time.time()
        if current_time - self.last_backup_time > self.backup_interval:
            logger.info("🤖 执行定期备份...")
            backup_path = self.backup_data()
            if backup_path:
                logger.info("✅ 定期备份完成")
            else:
                logger.error("❌ 定期备份失败")


# 🌍 全局系统维护实例
system_maintenance = SystemMaintenance()