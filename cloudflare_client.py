#!/usr/bin/env python
"""
Cloudflare客户端适配器 - 完整版本
"""
import requests
import json
import logging
import hashlib
import uuid
import time
import os
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import threading
import queue

# 消息协议类
class Message:
    """消息协议类"""
    def __init__(self, type: str, data: Dict[str, Any] = None):
        self.type = type
        self.data = data or {}
    
    @classmethod
    def create_login(cls, username: str, password: str, device_id: str):
        """创建登录消息"""
        return cls("LOGIN", {
            "username": username,
            "password": hashlib.sha256(password.encode()).hexdigest(),
            "device_id": device_id
        })
    
    @classmethod
    def create_license_check(cls, license_key: str, device_id: str):
        """创建激活码验证消息"""
        return cls("LICENSE_CHECK", {
            "license_key": license_key,
            "device_id": device_id
        })
    
    @classmethod
    def create_task_submit(cls, urls: List[str], email: str, user_id: str):
        """创建任务提交消息"""
        return cls("TASK_SUBMIT", {
            "urls": urls,
            "email": email,
            "user_id": user_id
        })
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "type": self.type,
            "data": self.data
        }

class CloudflareClientCore:
    """Cloudflare客户端核心 - 连接到网站服务器"""
    
    def __init__(self, api_url: str = "https://xuke.ambition.qzz.io"):
        self.api_url = api_url.rstrip('/')
        
        # 用户状态
        self.user_id: Optional[str] = None
        self.username: Optional[str] = None
        self.email: Optional[str] = None
        self.user_info: Optional[Dict] = None
        self.license_info: Optional[Dict] = None
        
        # 连接状态
        self.connected = True  # Cloudflare总是可连接
        self.authenticated = False
        self.license_valid = False
        
        # 任务管理
        self.tasks: Dict[str, Dict] = {}
        self.pending_tasks: List[Dict] = []
        
        # 回调函数
        self.status_callbacks: List[Any] = []
        self.message_callbacks: List[Any] = []
        self.error_callbacks: List[Any] = []
        
        # 配置
        self.config_file = "cloudflare_config.json"
        self.config = self._load_config()
        
        # 会话管理
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'XuekeDownloadClient/1.0',
            'Content-Type': 'application/json',
            'X-Client-Version': '2.0.0'
        })
        
        # 设备ID
        self.device_id = self._get_device_id()
        
        # 日志
        self._setup_logging()
        self.logger = logging.getLogger("CloudflareClient")
        
        # 心跳线程
        self.heartbeat_active = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        # 任务状态检查线程
        self.status_check_active = True
        self.status_thread = threading.Thread(target=self._status_check_loop, daemon=True)
        self.status_thread.start()
        
        self.logger.info(f"Cloudflare客户端初始化完成，服务器: {api_url}")
    
    def _setup_logging(self):
        """配置日志"""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'cloudflare_client.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def _load_config(self) -> Dict:
        """加载配置"""
        default_config = {
            "server": {
                "url": "https://xuke.ambition.qzz.io",
                "timeout": 30
            },
            "user": {
                "username": "",
                "email": "",
                "license_key": "",
                "auto_login": False,
                "password": ""  # 注意：实际使用中应该加密存储
            },
            "connection": {
                "heartbeat_interval": 60,
                "status_check_interval": 10,
                "auto_reconnect": True
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    self._merge_config(default_config, user_config)
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
        
        return default_config
    
    def _merge_config(self, default: Dict, user: Dict):
        """合并配置"""
        for key, value in user.items():
            if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                self._merge_config(default[key], value)
            else:
                default[key] = value
    
    def _get_device_id(self) -> str:
        """获取设备ID"""
        try:
            device_file = "device_id.txt"
            if os.path.exists(device_file):
                with open(device_file, 'r', encoding='utf-8') as f:
                    device_id = f.read().strip()
                    if device_id:
                        return device_id
            
            # 生成新设备ID
            device_id = str(uuid.uuid4())
            with open(device_file, 'w', encoding='utf-8') as f:
                f.write(device_id)
            
            return device_id
        except:
            return str(uuid.uuid4())
    
    def save_config(self) -> bool:
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            return False
    
    def connect(self, url: str = None) -> bool:
        """连接到服务器（对于Cloudflare总是成功）"""
        try:
            if url:
                self.api_url = url.rstrip('/')
                self.config["server"]["url"] = url
            
            # 测试连接
            response = self.session.get(f"{self.api_url}/api/ping", timeout=5)
            if response.status_code == 200:
                self.connected = True
                self._notify_status("connected", {"url": self.api_url})
                self.logger.info(f"已连接到服务器 {self.api_url}")
                return True
            else:
                self.connected = False
                return False
                
        except Exception as e:
            self.logger.error(f"连接测试失败: {e}")
            self.connected = False
            self._notify_error(e)
            return False
    
    def login(self, username: str = None, password: str = None) -> bool:
        """登录到服务器"""
        try:
            # 使用参数或配置
            username = username or self.config["user"].get("username", "")
            password = password or self.config["user"].get("password", "")
            
            if not username or not password:
                self._notify_error(Exception("用户名和密码不能为空"))
                return False
            
            # 发送登录请求
            response = self.session.post(
                f"{self.api_url}/api/auth/login",
                json={
                    'username': username,
                    'password': hashlib.sha256(password.encode()).hexdigest(),
                    'device_id': self.device_id
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    # 更新用户信息
                    self.authenticated = True
                    self.user_id = data.get('user_id')
                    self.username = username
                    self.user_info = data.get('user_info', {})
                    self.email = self.user_info.get('email', '')
                    
                    # 保存配置
                    self.config["user"]["username"] = username
                    self.config["user"]["password"] = password  # 注意：应该加密
                    self.save_config()
                    
                    # 提交等待中的任务
                    self._submit_pending_tasks()
                    
                    # 获取用户详情
                    self._get_user_details()
                    
                    self._notify_status("login_success", self.user_info)
                    self.logger.info(f"登录成功: {username}")
                    return True
                else:
                    error = data.get('error', '登录失败')
                    self._notify_status("login_failed", {"error": error})
                    self.logger.error(f"登录失败: {error}")
                    return False
            else:
                self._notify_error(Exception(f"登录请求失败: {response.status_code}"))
                return False
                
        except Exception as e:
            self.logger.error(f"登录异常: {e}")
            self._notify_error(e)
            return False
    
    def _get_user_details(self):
        """获取用户详细信息"""
        if not self.user_id:
            return
        
        try:
            response = self.session.get(f"{self.api_url}/api/users/{self.user_id}")
            if response.status_code == 200:
                user_data = response.json()
                self.user_info.update(user_data)
                
                # 更新激活信息
                if user_data.get('license_valid'):
                    self.license_valid = True
                    self.license_info = user_data.get('license_info', {})
        except Exception as e:
            self.logger.error(f"获取用户详情失败: {e}")
    
    def validate_license(self, license_key: str = None) -> bool:
        """验证激活码"""
        if not self.authenticated:
            self._notify_error(Exception("请先登录"))
            return False
        
        try:
            license_key = license_key or self.config["user"].get("license_key", "")
            
            if not license_key:
                self._notify_error(Exception("激活码不能为空"))
                return False
            
            # 发送激活码验证请求
            response = self.session.post(
                f"{self.api_url}/api/license/validate",
                json={
                    'license_key': license_key,
                    'device_id': self.device_id,
                    'user_id': self.user_id
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('valid'):
                    self.license_valid = True
                    self.license_info = data.get('license_info', {})
                    self.config["user"]["license_key"] = license_key
                    self.save_config()
                    
                    self._notify_status("license_valid", self.license_info)
                    self.logger.info("激活码验证成功")
                    return True
                else:
                    error = data.get('error', '激活码无效')
                    self._notify_status("license_invalid", {"error": error})
                    self.logger.error(f"激活码验证失败: {error}")
                    return False
            else:
                self._notify_error(Exception(f"验证请求失败: {response.status_code}"))
                return False
                
        except Exception as e:
            self.logger.error(f"验证激活码异常: {e}")
            self._notify_error(e)
            return False
    
    def submit_download_task(self, urls: List[str], email: str) -> Optional[str]:
        """提交下载任务"""
        # 检查输入
        if not urls:
            self._notify_error(Exception("下载链接不能为空"))
            return None
        
        if not email:
            self._notify_error(Exception("邮箱不能为空"))
            return None
        
        # 生成任务ID
        import hashlib
        task_id = f"cf_{int(time.time())}_{hashlib.md5(str(urls).encode()).hexdigest()[:8]}"
        
        # 创建任务
        task = {
            "task_id": task_id,
            "urls": urls,
            "email": email,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "user_id": self.user_id,
            "username": self.username
        }
        
        if self.authenticated and self.license_valid:
            # 在线状态，立即提交
            return self._submit_task_online(task)
        else:
            # 离线状态，保存到等待队列
            return self._save_task_offline(task)
    
    def _submit_task_online(self, task: Dict) -> Optional[str]:
        """在线提交任务"""
        try:
            response = self.session.post(
                f"{self.api_url}/api/tasks",
                json={
                    'user_id': self.user_id,
                    'urls': task["urls"],
                    'email': task["email"],
                    'submitted_by': self.username
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    server_task = data['task']
                    task_id = server_task['task_id']
                    
                    # 保存任务
                    self.tasks[task_id] = {
                        **task,
                        **server_task
                    }
                    
                    # 保存到历史
                    self._add_to_history(task)
                    
                    # 通知状态
                    self._notify_status("task_submitted", {
                        "task_id": task_id,
                        "url_count": len(task["urls"]),
                        "email": task["email"]
                    })
                    
                    self.logger.info(f"任务提交成功: {task_id}")
                    return task_id
            
            return None
            
        except Exception as e:
            self.logger.error(f"提交任务失败: {e}")
            self._notify_error(e)
            return None
    
    def _save_task_offline(self, task: Dict) -> str:
        """保存离线任务"""
        task["status"] = "offline_pending"
        self.pending_tasks.append(task)
        
        # 保存到本地
        self._save_pending_tasks()
        
        # 通知状态
        self._notify_status("task_offline_saved", {
            "task_id": task["task_id"],
            "message": "任务已保存，将在验证激活码后自动提交"
        })
        
        self.logger.info(f"任务保存为离线: {task['task_id']}")
        return task["task_id"]
    
    def _submit_pending_tasks(self):
        """提交等待中的任务"""
        if not self.authenticated or not self.license_valid:
            return
        
        tasks_to_submit = self.pending_tasks.copy()
        self.pending_tasks.clear()
        
        for task in tasks_to_submit:
            task_id = self._submit_task_online(task)
            if task_id:
                self.logger.info(f"提交等待任务: {task_id}")
        
        # 更新保存文件
        self._save_pending_tasks()
    
    def _save_pending_tasks(self):
        """保存等待任务到文件"""
        try:
            pending_file = "pending_tasks.json"
            with open(pending_file, 'w', encoding='utf-8') as f:
                json.dump(self.pending_tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存等待任务失败: {e}")
    
    def _load_pending_tasks(self):
        """从文件加载等待任务"""
        try:
            pending_file = "pending_tasks.json"
            if os.path.exists(pending_file):
                with open(pending_file, 'r', encoding='utf-8') as f:
                    self.pending_tasks = json.load(f)
        except Exception as e:
            self.logger.error(f"加载等待任务失败: {e}")
            self.pending_tasks = []
    
    def _add_to_history(self, task: Dict):
        """添加到历史记录"""
        try:
            history_file = "download_history.json"
            history = []
            
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            # 添加新记录
            history_entry = {
                "task_id": task["task_id"],
                "urls": task["urls"][:3],  # 只保存前3个URL
                "email": task["email"],
                "status": task["status"],
                "created_at": task["created_at"],
                "completed_at": None,
                "server": "cloudflare"
            }
            
            history.append(history_entry)
            
            # 只保留最近50条
            if len(history) > 50:
                history = history[-50:]
            
            # 保存
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"保存历史记录失败: {e}")
    
    def _heartbeat_loop(self):
        """心跳循环"""
        interval = self.config.get("connection", {}).get("heartbeat_interval", 60)
        
        while self.heartbeat_active:
            try:
                if self.authenticated:
                    response = self.session.get(f"{self.api_url}/api/ping", timeout=5)
                    if response.status_code == 200:
                        # 更新用户活动
                        if self.user_id:
                            self.session.post(
                                f"{self.api_url}/api/users/{self.user_id}/activity",
                                timeout=5
                            )
            except:
                pass
            
            time.sleep(interval)
    
    def _status_check_loop(self):
        """状态检查循环"""
        interval = self.config.get("connection", {}).get("status_check_interval", 10)
        
        while self.status_check_active:
            try:
                if self.authenticated and self.user_id:
                    # 检查用户任务状态
                    self._check_user_tasks()
            except Exception as e:
                self.logger.error(f"状态检查失败: {e}")
            
            time.sleep(interval)
    
    def _check_user_tasks(self):
        """检查用户任务状态"""
        try:
            response = self.session.get(f"{self.api_url}/api/users/{self.user_id}/tasks")
            if response.status_code == 200:
                tasks = response.json()
                
                for task in tasks:
                    task_id = task.get('task_id')
                    if task_id:
                        # 更新本地任务状态
                        if task_id in self.tasks:
                            old_status = self.tasks[task_id].get('status')
                            new_status = task.get('status')
                            
                            if old_status != new_status:
                                self.tasks[task_id].update(task)
                                
                                # 通知状态变化
                                if new_status == 'completed':
                                    self._notify_status("task_complete", task)
                                elif new_status == 'processing':
                                    self._notify_status("task_status", {
                                        "task_id": task_id,
                                        "status": new_status,
                                        "progress": task.get('progress', 0)
                                    })
        except Exception as e:
            self.logger.error(f"检查任务状态失败: {e}")
    
    def get_task_info(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        try:
            response = self.session.get(f"{self.api_url}/api/tasks/{task_id}")
            if response.status_code == 200:
                return response.json()
        except:
            pass
        
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        if self.authenticated and self.user_id:
            try:
                response = self.session.get(f"{self.api_url}/api/users/{self.user_id}/tasks")
                if response.status_code == 200:
                    return response.json()
            except:
                pass
        
        return list(self.tasks.values())
    
    def get_download_links(self, task_id: str) -> List[str]:
        """获取下载链接"""
        try:
            response = self.session.get(f"{self.api_url}/api/tasks/{task_id}/download")
            if response.status_code == 200:
                data = response.json()
                return data.get('direct_links', [])
        except Exception as e:
            self.logger.error(f"获取下载链接失败: {e}")
        
        return []
    
    def get_server_stats(self) -> Dict:
        """获取服务器统计"""
        try:
            response = self.session.get(f"{self.api_url}/api/stats")
            if response.status_code == 200:
                return response.json()
        except:
            pass
        
        return {}
    
    def logout(self):
        """登出"""
        if self.authenticated:
            try:
                self.session.post(f"{self.api_url}/api/auth/logout", timeout=5)
            except:
                pass
        
        self.authenticated = False
        self.license_valid = False
        self.user_id = None
        self.username = None
        self.user_info = None
        
        self._notify_status("logout", {})
        self.logger.info("用户已登出")
    
    def disconnect(self):
        """断开连接"""
        self.heartbeat_active = False
        self.status_check_active = False
        
        if self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=1)
        
        if self.status_thread.is_alive():
            self.status_thread.join(timeout=1)
        
        self.connected = False
        self._notify_status("disconnected", {})
        self.logger.info("已断开连接")
    
    def _notify_status(self, status_type: str, data: Dict):
        """通知状态更新"""
        for callback in self.status_callbacks:
            try:
                callback(status_type, data)
            except Exception as e:
                self.logger.error(f"状态回调执行失败: {e}")
    
    def _notify_error(self, error: Exception):
        """通知错误"""
        for callback in self.error_callbacks:
            try:
                callback(error)
            except Exception as e:
                self.logger.error(f"错误回调执行失败: {e}")
    
    # 回调注册
    def register_status_callback(self, callback):
        """注册状态回调"""
        if callback not in self.status_callbacks:
            self.status_callbacks.append(callback)
    
    def register_message_callback(self, callback):
        """注册消息回调"""
        if callback not in self.message_callbacks:
            self.message_callbacks.append(callback)
    
    def register_error_callback(self, callback):
        """注册错误回调"""
        if callback not in self.error_callbacks:
            self.error_callbacks.append(callback)
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "connected": self.connected,
            "authenticated": self.authenticated,
            "license_valid": self.license_valid,
            "username": self.username,
            "user_id": self.user_id,
            "email": self.email,
            "pending_tasks": len(self.pending_tasks),
            "active_tasks": len([t for t in self.tasks.values() if t.get("status") in ["processing", "downloading"]]),
            "server_url": self.api_url
        }