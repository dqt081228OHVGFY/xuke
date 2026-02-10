"""
Cloudflare客户端GUI适配器
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime

from cloudflare_client import CloudflareClientCore

class CloudflareClientGUI:
    """Cloudflare客户端GUI"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("学科网下载客户端 - Cloudflare版")
        self.root.geometry("1000x700")
        
        # 客户端核心
        self.client = CloudflareClientCore()
        
        # 注册回调
        self.client.register_status_callback(self.on_status_update)
        self.client.register_error_callback(self.on_error)
        
        # 创建GUI
        self._create_widgets()
        
        # 启动状态更新
        self._start_status_updater()
        
        # 尝试自动连接
        self.root.after(1000, self._auto_connect)
    
    def _create_widgets(self):
        """创建GUI组件"""
        # 创建笔记本
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 1. 连接与激活
        self._create_connection_tab()
        
        # 2. 下载管理
        self._create_download_tab()
        
        # 3. 任务历史
        self._create_history_tab()
        
        # 4. 状态信息
        self._create_status_tab()
    
    def _create_connection_tab(self):
        """创建连接标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="连接与激活")
        
        # 服务器配置
        server_frame = ttk.LabelFrame(frame, text="服务器配置", padding=10)
        server_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(server_frame, text="服务器地址:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.server_url = ttk.Entry(server_frame, width=40)
        self.server_url.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        self.server_url.insert(0, self.client.api_url)
        
        self.connect_btn = ttk.Button(server_frame, text="测试连接", 
                                     command=self.test_connection)
        self.connect_btn.grid(row=0, column=2, padx=20, pady=5)
        
        self.conn_status = ttk.Label(server_frame, text="状态: 未连接", foreground="red")
        self.conn_status.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky='w')
        
        # 用户登录
        login_frame = ttk.LabelFrame(frame, text="用户登录", padding=10)
        login_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(login_frame, text="用户名:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.username = ttk.Entry(login_frame, width=25)
        self.username.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        self.username.insert(0, self.client.config["user"].get("username", ""))
        
        ttk.Label(login_frame, text="密码:").grid(row=0, column=2, padx=5, pady=5, sticky='w')
        self.password = ttk.Entry(login_frame, width=25, show="*")
        self.password.grid(row=0, column=3, padx=5, pady=5, sticky='w')
        self.password.insert(0, self.client.config["user"].get("password", ""))
        
        self.login_btn = ttk.Button(login_frame, text="登录", command=self.login)
        self.login_btn.grid(row=0, column=4, padx=20, pady=5)
        
        self.logout_btn = ttk.Button(login_frame, text="登出", command=self.logout, state='disabled')
        self.logout_btn.grid(row=0, column=5, padx=5, pady=5)
        
        self.login_status = ttk.Label(login_frame, text="登录状态: 未登录", foreground="red")
        self.login_status.grid(row=1, column=0, columnspan=6, padx=5, pady=5, sticky='w')
        
        # 激活码验证
        license_frame = ttk.LabelFrame(frame, text="激活码验证", padding=10)
        license_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(license_frame, text="激活码:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.license_key = ttk.Entry(license_frame, width=40)
        self.license_key.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky='we')
        self.license_key.insert(0, self.client.config["user"].get("license_key", ""))
        
        self.license_btn = ttk.Button(license_frame, text="验证激活码", command=self.validate_license)
        self.license_btn.grid(row=0, column=4, padx=20, pady=5)
        
        self.license_status = ttk.Label(license_frame, text="激活状态: 未激活", foreground="red")
        self.license_status.grid(row=1, column=0, columnspan=5, padx=5, pady=5, sticky='w')
        
        # 激活信息
        info_frame = ttk.Frame(license_frame)
        info_frame.grid(row=2, column=0, columnspan=5, sticky='we', padx=5, pady=5)
        
        ttk.Label(info_frame, text="剩余天数:").pack(side='left', padx=5)
        self.days_left = ttk.Label(info_frame, text="0", foreground="blue")
        self.days_left.pack(side='left', padx=5)
        
        ttk.Label(info_frame, text="使用次数:").pack(side='left', padx=20)
        self.uses_left = ttk.Label(info_frame, text="0/0", foreground="blue")
        self.uses_left.pack(side='left', padx=5)
        
        ttk.Label(info_frame, text="过期时间:").pack(side='left', padx=20)
        self.expiry_date = ttk.Label(info_frame, text="未激活", foreground="blue")
        self.expiry_date.pack(side='left', padx=5)
    
    def _create_download_tab(self):
        """创建下载标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="下载管理")
        
        from tkinter import scrolledtext
        
        # 下载链接
        url_frame = ttk.LabelFrame(frame, text="下载链接", padding=10)
        url_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.url_text = scrolledtext.ScrolledText(url_frame, height=10)
        self.url_text.pack(fill='both', expand=True, pady=5)
        
        # URL操作按钮
        url_btn_frame = ttk.Frame(url_frame)
        url_btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(url_btn_frame, text="示例链接", command=self.add_example_urls).pack(side='left', padx=2)
        ttk.Button(url_btn_frame, text="清空列表", command=self.clear_urls).pack(side='left', padx=2)
        
        # 邮件设置
        email_frame = ttk.LabelFrame(frame, text="邮件接收设置", padding=10)
        email_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(email_frame, text="接收邮箱:").pack(side='left', padx=5)
        self.email = ttk.Entry(email_frame, width=30)
        self.email.pack(side='left', padx=5)
        
        if self.client.email:
            self.email.insert(0, self.client.email)
        
        # 控制按钮
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill='x', padx=10, pady=20)
        
        self.download_btn = ttk.Button(control_frame, text="提交下载任务", 
                                      command=self.submit_task, state='disabled')
        self.download_btn.pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="检查状态", command=self.check_status).pack(side='left', padx=5)
        
        # 进度显示
        progress_frame = ttk.LabelFrame(frame, text="任务状态", padding=10)
        progress_frame.pack(fill='x', padx=10, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="准备就绪")
        self.progress_label.pack(anchor='w')
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill='x', pady=5)
    
    def _create_history_tab(self):
        """创建历史标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="任务历史")
        
        # 历史列表
        list_frame = ttk.LabelFrame(frame, text="任务历史", padding=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        columns = ('任务ID', '状态', '进度', '文件数', '创建时间', '完成时间')
        self.history_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 操作按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(btn_frame, text="刷新", command=self.refresh_history).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="查看详情", command=self.view_task_detail).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="下载文件", command=self.download_files).pack(side='left', padx=2)
    
    def _create_status_tab(self):
        """创建状态标签页"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="系统状态")
        
        from tkinter import scrolledtext
        
        # 状态信息
        status_frame = ttk.LabelFrame(frame, text="连接状态", padding=10)
        status_frame.pack(fill='x', padx=10, pady=5)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=15)
        self.status_text.pack(fill='both', expand=True)
        
        # 服务器统计
        stats_frame = ttk.LabelFrame(frame, text="服务器统计", padding=10)
        stats_frame.pack(fill='x', padx=10, pady=5)
        
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=8)
        self.stats_text.pack(fill='both', expand=True)
        
        # 刷新按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(btn_frame, text="刷新状态", command=self.refresh_status).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="保存配置", command=self.save_config).pack(side='left', padx=5)
    
    def _start_status_updater(self):
        """启动状态更新定时器"""
        def update_status():
            status = self.client.get_status()
            
            # 更新连接状态
            if status['connected']:
                self.conn_status.config(text=f"状态: 已连接 ({status['server_url']})", foreground="green")
                self.connect_btn.config(state='disabled')
            else:
                self.conn_status.config(text="状态: 未连接", foreground="red")
                self.connect_btn.config(state='normal')
            
            # 更新登录状态
            if status['authenticated']:
                self.login_status.config(text=f"登录状态: 已登录 ({status['username']})", foreground="green")
                self.login_btn.config(state='disabled')
                self.logout_btn.config(state='normal')
            else:
                self.login_status.config(text="登录状态: 未登录", foreground="red")
                self.login_btn.config(state='normal')
                self.logout_btn.config(state='disabled')
            
            # 更新激活状态
            if status['license_valid']:
                self.license_status.config(text="激活状态: 已激活", foreground="green")
                self.license_btn.config(state='disabled')
                self.download_btn.config(state='normal')
            else:
                self.license_status.config(text="激活状态: 未激活", foreground="red")
                self.license_btn.config(state='normal')
                self.download_btn.config(state='disabled')
            
            # 更新状态文本
            status_info = f"""客户端状态:
• 服务器: {status['server_url']}
• 连接状态: {'✅ 已连接' if status['connected'] else '❌ 未连接'}
• 登录状态: {'✅ 已登录' if status['authenticated'] else '❌ 未登录'}
• 激活状态: {'✅ 已激活' if status['license_valid'] else '❌ 未激活'}
• 用户名: {status['username'] or '未登录'}
• 用户ID: {status['user_id'] or '未登录'}
• 等待任务: {status['pending_tasks']} 个
• 活动任务: {status['active_tasks']} 个
"""
            
            self.status_text.delete('1.0', 'end')
            self.status_text.insert('end', status_info)
            
            self.root.after(2000, update_status)
        
        update_status()
    
    def _auto_connect(self):
        """自动连接"""
        if self.client.config["user"].get("auto_login", False):
            self.test_connection()
            self.root.after(2000, self.auto_login)
    
    def auto_login(self):
        """自动登录"""
        username = self.client.config["user"].get("username", "")
        password = self.client.config["user"].get("password", "")
        
        if username and password:
            self.login(username, password)
    
    def test_connection(self):
        """测试连接"""
        url = self.server_url.get().strip()
        
        def connect_thread():
            success = self.client.connect(url)
            
            if success:
                self.root.after(0, lambda: messagebox.showinfo("成功", "服务器连接成功"))
            else:
                self.root.after(0, lambda: messagebox.showerror("错误", "连接服务器失败"))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def login(self, username=None, password=None):
        """登录"""
        if username is None:
            username = self.username.get().strip()
            password = self.password.get().strip()
        
        if not username:
            messagebox.showwarning("警告", "请输入用户名")
            return
        
        if not password:
            messagebox.showwarning("警告", "请输入密码")
            return
        
        def login_thread():
            success = self.client.login(username, password)
            
            if success:
                self.root.after(0, lambda: messagebox.showinfo("成功", "登录成功"))
            else:
                self.root.after(0, lambda: messagebox.showerror("错误", "登录失败"))
        
        threading.Thread(target=login_thread, daemon=True).start()
    
    def logout(self):
        """登出"""
        self.client.logout()
        messagebox.showinfo("提示", "已登出")
    
    def validate_license(self):
        """验证激活码"""
        license_key = self.license_key.get().strip()
        
        if not license_key:
            messagebox.showwarning("警告", "请输入激活码")
            return
        
        def validate_thread():
            success = self.client.validate_license(license_key)
            
            if success:
                self.root.after(0, lambda: messagebox.showinfo("成功", "激活码验证成功"))
            else:
                self.root.after(0, lambda: messagebox.showerror("错误", "激活码验证失败"))
        
        threading.Thread(target=validate_thread, daemon=True).start()
    
    def add_example_urls(self):
        """添加示例链接"""
        example_urls = """https://www.xkw.com/doc/2024/math/001
https://www.xkw.com/doc/2024/english/002
https://www.xkw.com/doc/2024/physics/003
https://www.xkw.com/doc/2024/chemistry/004
https://www.xkw.com/doc/2024/biology/005"""
        
        self.url_text.delete('1.0', 'end')
        self.url_text.insert('end', example_urls)
    
    def clear_urls(self):
        """清空URL列表"""
        if messagebox.askyesno("确认", "确定要清空所有URL吗？"):
            self.url_text.delete('1.0', 'end')
    
    def submit_task(self):
        """提交任务"""
        urls_text = self.url_text.get('1.0', 'end').strip()
        if not urls_text:
            messagebox.showwarning("警告", "请输入下载链接")
            return
        
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        email = self.email.get().strip()
        if not email:
            messagebox.showwarning("警告", "请输入接收邮箱")
            return
        
        # 更新进度
        self.progress_label.config(text="正在提交任务...")
        self.progress_bar['value'] = 0
        
        def submit_thread():
            task_id = self.client.submit_download_task(urls, email)
            
            if task_id:
                self.root.after(0, lambda: messagebox.showinfo(
                    "成功", 
                    f"任务提交成功！\n任务ID: {task_id}\n\n请等待服务器处理..."
                ))
                
                self.root.after(0, lambda: self.progress_label.config(
                    text=f"任务已提交，ID: {task_id}"
                ))
                
                # 刷新历史
                self.root.after(1000, self.refresh_history)
            else:
                self.root.after(0, lambda: messagebox.showerror("错误", "任务提交失败"))
        
        threading.Thread(target=submit_thread, daemon=True).start()
    
    def check_status(self):
        """检查状态"""
        status = self.client.get_status()
        stats = self.client.get_server_stats()
        
        status_text = f"客户端状态:\n"
        status_text += f"• 连接: {'✅已连接' if status['connected'] else '❌未连接'}\n"
        status_text += f"• 登录: {'✅已登录' if status['authenticated'] else '❌未登录'}\n"
        status_text += f"• 激活: {'✅已激活' if status['license_valid'] else '❌未激活'}\n"
        status_text += f"• 等待任务: {status['pending_tasks']} 个\n"
        status_text += f"• 活动任务: {status['active_tasks']} 个\n\n"
        
        status_text += f"服务器统计:\n"
        status_text += f"• 总用户数: {stats.get('total_users', 0)}\n"
        status_text += f"• 总任务数: {stats.get('total_tasks', 0)}\n"
        status_text += f"• 待处理: {stats.get('pending_tasks', 0)}\n"
        status_text += f"• 处理中: {stats.get('processing_tasks', 0)}\n"
        status_text += f"• 已完成: {stats.get('completed_tasks', 0)}"
        
        messagebox.showinfo("状态检查", status_text)
    
    def refresh_history(self):
        """刷新历史记录"""
        # 清空现有数据
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        try:
            tasks = self.client.get_all_tasks()
            
            for task in tasks[:20]:  # 只显示最近20条
                created_at = task.get('created_at', '')
                completed_at = task.get('completed_at', '')
                
                if created_at and len(created_at) > 10:
                    created_at = created_at[:19]
                if completed_at and len(completed_at) > 10:
                    completed_at = completed_at[:19]
                
                self.history_tree.insert('', 'end', values=(
                    task.get('task_id', ''),
                    task.get('status', ''),
                    f"{task.get('progress', 0)}%",
                    len(task.get('downloaded_files', [])),
                    created_at,
                    completed_at
                ))
        except Exception as e:
            print(f"刷新历史记录失败: {e}")
    
    def view_task_detail(self):
        """查看任务详情"""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个任务")
            return
        
        item = selection[0]
        values = self.history_tree.item(item, 'values')
        task_id = values[0]
        
        task_info = self.client.get_task_info(task_id)
        if task_info:
            detail = f"任务ID: {task_info.get('task_id')}\n"
            detail += f"状态: {task_info.get('status')}\n"
            detail += f"进度: {task_info.get('progress')}%\n"
            detail += f"用户: {task_info.get('username')}\n"
            detail += f"邮箱: {task_info.get('email')}\n"
            detail += f"创建时间: {task_info.get('created_at', '')[:19]}\n"
            detail += f"完成时间: {task_info.get('completed_at', '')[:19]}\n"
            detail += f"文件数: {len(task_info.get('downloaded_files', []))}\n"
            
            # 显示下载链接
            links = task_info.get('direct_links', [])
            if links:
                detail += f"\n下载链接:\n"
                for i, link in enumerate(links[:3], 1):
                    detail += f"{i}. {link}\n"
                if len(links) > 3:
                    detail += f"... 还有 {len(links) - 3} 个链接\n"
            
            messagebox.showinfo("任务详情", detail)
    
    def download_files(self):
        """下载文件"""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择一个任务")
            return
        
        item = selection[0]
        values = self.history_tree.item(item, 'values')
        task_id = values[0]
        status = values[1]
        
        if status != 'completed':
            messagebox.showwarning("警告", "任务未完成，无法下载")
            return
        
        links = self.client.get_download_links(task_id)
        if links:
            import webbrowser
            for link in links[:3]:  # 最多打开3个链接
                webbrowser.open(link)
            
            messagebox.showinfo("下载", f"已开始下载 {len(links)} 个文件")
        else:
            messagebox.showwarning("警告", "没有可用的下载链接")
    
    def refresh_status(self):
        """刷新状态"""
        stats = self.client.get_server_stats()
        
        stats_text = f"服务器统计信息:\n"
        stats_text += f"• 总用户数: {stats.get('total_users', 0)}\n"
        stats_text += f"• 活跃用户: {stats.get('active_users', 0)}\n"
        stats_text += f"• 总任务数: {stats.get('total_tasks', 0)}\n"
        stats_text += f"• 待处理任务: {stats.get('pending_tasks', 0)}\n"
        stats_text += f"• 处理中任务: {stats.get('processing_tasks', 0)}\n"
        stats_text += f"• 已完成任务: {stats.get('completed_tasks', 0)}\n"
        stats_text += f"• 失败任务: {stats.get('failed_tasks', 0)}\n"
        stats_text += f"• 总许可证数: {stats.get('total_licenses', 0)}\n"
        stats_text += f"• 有效许可证: {stats.get('active_licenses', 0)}\n"
        stats_text += f"• 过期许可证: {stats.get('expired_licenses', 0)}\n"
        stats_text += f"• 24小时任务数: {stats.get('tasks_last_24h', 0)}\n"
        stats_text += f"• 服务器时间: {stats.get('server_time', '')[:19]}\n"
        
        self.stats_text.delete('1.0', 'end')
        self.stats_text.insert('end', stats_text)
    
    def save_config(self):
        """保存配置"""
        try:
            # 更新配置
            self.client.config["server"]["url"] = self.server_url.get().strip()
            self.client.config["user"]["username"] = self.username.get().strip()
            self.client.config["user"]["license_key"] = self.license_key.get().strip()
            
            # 保存配置
            if self.client.save_config():
                messagebox.showinfo("成功", "配置保存成功")
            else:
                messagebox.showerror("错误", "配置保存失败")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")
    
    def on_status_update(self, status_type: str, data: dict):
        """处理状态更新"""
        if status_type == "license_valid":
            # 更新激活信息显示
            self.days_left.config(text=str(data.get("days_left", 0)))
            self.uses_left.config(text=f"{data.get('used_count', 0)}/{data.get('max_uses', 0)}")
            
            expires_at = data.get("expires_at")
            if expires_at:
                try:
                    self.expiry_date.config(text=expires_at[:10])
                except:
                    self.expiry_date.config(text=expires_at)
        
        elif status_type == "task_complete":
            # 任务完成
            task_id = data.get("task_id", "")
            files = data.get("files", [])
            direct_links = data.get("direct_links", [])
            
            message = f"任务完成！\n任务ID: {task_id}\n文件数: {len(files)}\n\n"
            
            if direct_links:
                message += "文件直链：\n"
                for i, link in enumerate(direct_links[:3], 1):
                    message += f"{i}. {link}\n"
                
                if len(direct_links) > 3:
                    message += f"... 还有 {len(direct_links) - 3} 个链接\n"
            
            self.root.after(0, lambda: messagebox.showinfo("下载完成", message))
            self.root.after(0, lambda: self.progress_label.config(text="下载完成"))
            self.root.after(0, lambda: self.progress_bar.config(value=100))
            
            # 刷新历史记录
            self.root.after(1000, self.refresh_history)
        
        elif status_type == "task_offline_saved":
            # 离线任务保存
            task_id = data.get("task_id", "")
            message = data.get("message", "")
            
            self.root.after(0, lambda: messagebox.showinfo("任务保存", 
                f"任务已保存\n任务ID: {task_id}\n\n{message}"))
    
    def on_error(self, error: Exception):
        """处理错误"""
        error_msg = str(error)
        self.root.after(0, lambda: messagebox.showerror("错误", f"发生错误:\n\n{error_msg}"))

def main():
    """主函数"""
    root = tk.Tk()
    app = CloudflareClientGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()