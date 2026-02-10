// Cloudflare Worker - 完整版本
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    // CORS 头
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Client-Version',
      'Access-Control-Max-Age': '86400',
    };

    // 处理预检请求
    if (method === 'OPTIONS') {
      return new Response(null, {
        headers: corsHeaders,
      });
    }

    try {
      // API 路由
      if (path === '/' || path === '/index.html') {
        return serveFrontend();
      } else if (path === '/api/ping') {
        return handlePing();
      } else if (path === '/api/auth/login' && method === 'POST') {
        return await handleLogin(request, env);
      } else if (path === '/api/auth/logout' && method === 'POST') {
        return await handleLogout(request, env);
      } else if (path === '/api/license/validate' && method === 'POST') {
        return await handleValidateLicense(request, env);
      } else if (path === '/api/users' && method === 'GET') {
        return await handleGetUsers(env);
      } else if (path === '/api/users' && method === 'POST') {
        return await handleCreateUser(request, env);
      } else if (path.startsWith('/api/users/')) {
        const userId = path.split('/')[3];
        if (method === 'GET') {
          return await handleGetUser(userId, env);
        } else if (path.endsWith('/activity') && method === 'POST') {
          return await handleUserActivity(userId, env);
        } else if (path.endsWith('/tasks') && method === 'GET') {
          return await handleGetUserTasks(userId, env);
        }
      } else if (path === '/api/tasks' && method === 'GET') {
        return await handleGetTasks(env);
      } else if (path === '/api/tasks' && method === 'POST') {
        return await handleCreateTask(request, env);
      } else if (path.startsWith('/api/tasks/')) {
        const taskId = path.split('/')[3];
        if (method === 'GET') {
          return await handleGetTask(taskId, env);
        } else if (path.endsWith('/process') && method === 'POST') {
          return await handleProcessTask(taskId, env);
        } else if (path.endsWith('/download') && method === 'GET') {
          return await handleDownloadTask(taskId, env);
        } else if (path.endsWith('/status') && method === 'GET') {
          return await handleGetTaskStatus(taskId, env);
        }
      } else if (path === '/api/stats' && method === 'GET') {
        return await handleGetStats(env);
      } else if (path === '/api/settings' && method === 'POST') {
        return await handleSaveSettings(request, env);
      } else if (path === '/api/backup' && method === 'GET') {
        return await handleBackup(env);
      } else if (path === '/api/cleanup' && method === 'POST') {
        return await handleCleanup(env);
      } else if (path.startsWith('/download/')) {
        return await handleDownload(request, env);
      } else {
        return jsonResponse({ error: 'Not Found' }, 404);
      }
    } catch (error) {
      console.error('处理请求失败:', error);
      return jsonResponse({ error: 'Internal Server Error', details: error.message }, 500);
    }
  },
};

// ========== 前端页面 ==========
function serveFrontend() {
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<!-- 这里插入完整的前端HTML代码 -->
</html>`;
  
  return new Response(html, {
    headers: {
      'Content-Type': 'text/html;charset=UTF-8',
      'Cache-Control': 'no-cache',
    },
  });
}

// ========== 基础API ==========
function handlePing() {
  return jsonResponse({
    status: 'ok',
    timestamp: new Date().toISOString(),
    service: 'xueke-download-system',
    version: '2.0.0'
  });
}

// ========== 用户认证 ==========
async function handleLogin(request, env) {
  try {
    const data = await request.json();
    const { username, password, device_id } = data;
    
    // 验证输入
    if (!username || !password) {
      return jsonResponse({ success: false, error: '用户名和密码不能为空' }, 400);
    }
    
    // 获取用户列表
    const users = await getUsers(env);
    
    // 查找用户
    const user = users.find(u => 
      u.username === username && 
      u.password_hash === password // 注意：实际应该使用加密验证
    );
    
    if (!user) {
      // 记录登录失败
      await logEvent(env, 'login_failed', { username, reason: '用户不存在或密码错误' });
      return jsonResponse({ success: false, error: '用户名或密码错误' }, 401);
    }
    
    if (!user.is_active) {
      await logEvent(env, 'login_failed', { username, reason: '账户已被禁用' });
      return jsonResponse({ success: false, error: '账户已被禁用' }, 403);
    }
    
    // 更新最后登录时间
    const now = new Date().toISOString();
    user.last_login = now;
    user.last_activity = now;
    user.device_id = device_id;
    
    // 保存用户信息
    await saveUsers(env, users);
    
    // 获取用户许可证信息
    const licenses = await getLicenses(env);
    const userLicenses = licenses.filter(l => l.user_id === user.id);
    const activeLicense = userLicenses.find(l => l.is_active && new Date(l.expires_at) > new Date());
    
    // 创建用户信息响应
    const userInfo = {
      user_id: user.id,
      username: user.username,
      email: user.email,
      user_type: user.user_type,
      created_at: user.created_at,
      last_login: user.last_login,
      license_count: userLicenses.length,
      license_valid: !!activeLicense,
      license_info: activeLicense || null
    };
    
    // 记录登录成功
    await logEvent(env, 'login_success', { 
      user_id: user.id, 
      username,
      device_id 
    });
    
    return jsonResponse({
      success: true,
      message: '登录成功',
      user_id: user.id,
      user_info: userInfo
    });
    
  } catch (error) {
    console.error('登录处理失败:', error);
    return jsonResponse({ success: false, error: '登录处理失败' }, 500);
  }
}

async function handleLogout(request, env) {
  try {
    const data = await request.json();
    const { user_id, username } = data;
    
    if (user_id) {
      await logEvent(env, 'logout', { user_id, username });
    }
    
    return jsonResponse({ success: true, message: '登出成功' });
  } catch (error) {
    return jsonResponse({ success: false, error: '登出失败' }, 500);
  }
}

// ========== 许可证管理 ==========
async function handleValidateLicense(request, env) {
  try {
    const data = await request.json();
    const { license_key, device_id, user_id } = data;
    
    if (!license_key) {
      return jsonResponse({ valid: false, error: '激活码不能为空' }, 400);
    }
    
    // 获取许可证列表
    const licenses = await getLicenses(env);
    
    // 查找许可证
    const license = licenses.find(l => l.license_key === license_key);
    
    if (!license) {
      return jsonResponse({ valid: false, error: '激活码不存在' }, 404);
    }
    
    if (!license.is_active) {
      return jsonResponse({ valid: false, error: '激活码已失效' }, 400);
    }
    
    // 检查过期时间
    const expiresAt = new Date(license.expires_at);
    const now = new Date();
    
    if (expiresAt < now) {
      return jsonResponse({ valid: false, error: '激活码已过期' }, 400);
    }
    
    // 检查使用次数
    if (license.max_uses > 0 && license.used_count >= license.max_uses) {
      return jsonResponse({ 
        valid: false, 
        error: `激活码使用次数已达上限 (${license.used_count}/${license.max_uses})` 
      }, 400);
    }
    
    // 检查设备绑定
    if (license.device_id && device_id && license.device_id !== device_id) {
      return jsonResponse({ valid: false, error: '激活码已绑定到其他设备' }, 400);
    }
    
    // 检查用户绑定
    if (user_id && license.user_id !== user_id) {
      return jsonResponse({ valid: false, error: '激活码不属于当前用户' }, 400);
    }
    
    // 更新许可证信息
    license.used_count += 1;
    license.last_use = now.toISOString();
    
    if (device_id && !license.device_id) {
      license.device_id = device_id;
      license.activated_at = now.toISOString();
    }
    
    // 保存许可证
    await saveLicenses(env, licenses);
    
    // 计算剩余天数
    const daysLeft = Math.ceil((expiresAt - now) / (1000 * 60 * 60 * 24));
    
    // 许可证信息
    const licenseInfo = {
      license_key: license.license_key,
      user_id: license.user_id,
      username: license.username,
      days: license.days,
      max_uses: license.max_uses,
      used_count: license.used_count,
      created_at: license.created_at,
      expires_at: license.expires_at,
      days_left: daysLeft,
      activated_at: license.activated_at,
      device_id: license.device_id
    };
    
    // 记录许可证使用
    await logEvent(env, 'license_validated', {
      license_key,
      user_id,
      device_id
    });
    
    return jsonResponse({
      valid: true,
      message: `激活码验证成功，剩余 ${daysLeft} 天`,
      license_info: licenseInfo
    });
    
  } catch (error) {
    console.error('验证激活码失败:', error);
    return jsonResponse({ valid: false, error: '验证激活码失败' }, 500);
  }
}

// ========== 用户管理 ==========
async function handleGetUsers(env) {
  try {
    const users = await getUsers(env);
    
    // 移除敏感信息
    const safeUsers = users.map(user => ({
      id: user.id,
      username: user.username,
      email: user.email,
      user_type: user.user_type,
      is_active: user.is_active,
      created_at: user.created_at,
      last_login: user.last_login,
      last_activity: user.last_activity,
      license_count: 0 // 需要从许可证计算
    }));
    
    // 获取许可证计数
    const licenses = await getLicenses(env);
    safeUsers.forEach(user => {
      user.license_count = licenses.filter(l => l.user_id === user.id).length;
    });
    
    return jsonResponse(safeUsers);
  } catch (error) {
    console.error('获取用户列表失败:', error);
    return jsonResponse({ error: '获取用户列表失败' }, 500);
  }
}

async function handleCreateUser(request, env) {
  try {
    const data = await request.json();
    const { username, email, password, user_type = 'user' } = data;
    
    // 验证输入
    if (!username || !email || !password) {
      return jsonResponse({ success: false, error: '缺少必要字段' }, 400);
    }
    
    // 获取现有用户
    const users = await getUsers(env);
    
    // 检查用户名是否已存在
    if (users.some(u => u.username === username)) {
      return jsonResponse({ success: false, error: '用户名已存在' }, 400);
    }
    
    // 检查邮箱是否已存在
    if (users.some(u => u.email === email)) {
      return jsonResponse({ success: false, error: '邮箱已存在' }, 400);
    }
    
    // 创建新用户
    const newUser = {
      id: generateId('user'),
      username,
      email,
      password_hash: password, // 注意：实际应该加密存储
      user_type,
      is_active: true,
      created_at: new Date().toISOString(),
      last_login: null,
      last_activity: null,
      device_id: null
    };
    
    users.push(newUser);
    
    // 保存用户
    await saveUsers(env, users);
    
    // 记录事件
    await logEvent(env, 'user_created', {
      user_id: newUser.id,
      username,
      email,
      user_type
    });
    
    return jsonResponse({
      success: true,
      message: '用户创建成功',
      user_id: newUser.id,
      user: {
        id: newUser.id,
        username: newUser.username,
        email: newUser.email,
        user_type: newUser.user_type
      }
    });
    
  } catch (error) {
    console.error('创建用户失败:', error);
    return jsonResponse({ success: false, error: '创建用户失败' }, 500);
  }
}

async function handleGetUser(userId, env) {
  try {
    const users = await getUsers(env);
    const user = users.find(u => u.id === userId);
    
    if (!user) {
      return jsonResponse({ error: '用户不存在' }, 404);
    }
    
    // 获取用户许可证
    const licenses = await getLicenses(env);
    const userLicenses = licenses.filter(l => l.user_id === userId);
    const activeLicense = userLicenses.find(l => l.is_active && new Date(l.expires_at) > new Date());
    
    // 获取用户任务
    const tasks = await getTasks(env);
    const userTasks = tasks.filter(t => t.user_id === userId);
    
    // 安全返回用户信息
    const safeUser = {
      id: user.id,
      username: user.username,
      email: user.email,
      user_type: user.user_type,
      is_active: user.is_active,
      created_at: user.created_at,
      last_login: user.last_login,
      last_activity: user.last_activity,
      license_count: userLicenses.length,
      license_valid: !!activeLicense,
      license_info: activeLicense || null,
      task_count: userTasks.length,
      completed_tasks: userTasks.filter(t => t.status === 'completed').length,
      pending_tasks: userTasks.filter(t => t.status === 'pending').length
    };
    
    return jsonResponse(safeUser);
  } catch (error) {
    console.error('获取用户信息失败:', error);
    return jsonResponse({ error: '获取用户信息失败' }, 500);
  }
}

async function handleUserActivity(userId, env) {
  try {
    const users = await getUsers(env);
    const userIndex = users.findIndex(u => u.id === userId);
    
    if (userIndex === -1) {
      return jsonResponse({ error: '用户不存在' }, 404);
    }
    
    // 更新最后活动时间
    users[userIndex].last_activity = new Date().toISOString();
    
    // 保存用户
    await saveUsers(env, users);
    
    return jsonResponse({ success: true, message: '活动时间已更新' });
  } catch (error) {
    console.error('更新用户活动时间失败:', error);
    return jsonResponse({ error: '更新失败' }, 500);
  }
}

async function handleGetUserTasks(userId, env) {
  try {
    const tasks = await getTasks(env);
    const userTasks = tasks.filter(t => t.user_id === userId);
    
    // 按创建时间排序
    userTasks.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    
    return jsonResponse(userTasks);
  } catch (error) {
    console.error('获取用户任务失败:', error);
    return jsonResponse({ error: '获取任务失败' }, 500);
  }
}

// ========== 任务管理 ==========
async function handleGetTasks(env) {
  try {
    const tasks = await getTasks(env);
    
    // 按创建时间排序
    tasks.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    
    return jsonResponse(tasks);
  } catch (error) {
    console.error('获取任务列表失败:', error);
    return jsonResponse({ error: '获取任务列表失败' }, 500);
  }
}

async function handleCreateTask(request, env) {
  try {
    const data = await request.json();
    const { user_id, urls, email, submitted_by, notes = '' } = data;
    
    // 验证输入
    if (!user_id || !urls || !Array.isArray(urls) || urls.length === 0 || !email) {
      return jsonResponse({ success: false, error: '缺少必要字段或格式错误' }, 400);
    }
    
    // 验证用户是否存在
    const users = await getUsers(env);
    const user = users.find(u => u.id === user_id);
    
    if (!user) {
      return jsonResponse({ success: false, error: '用户不存在' }, 404);
    }
    
    // 创建任务ID
    const taskId = generateId('task');
    
    // 创建新任务
    const newTask = {
      task_id: taskId,
      user_id,
      username: user.username,
      urls,
      email,
      notes,
      status: 'pending',
      progress: 0,
      submitted_by: submitted_by || 'system',
      created_at: new Date().toISOString(),
      started_at: null,
      completed_at: null,
      downloaded_files: [],
      direct_links: [],
      error_message: null
    };
    
    // 获取现有任务
    const tasks = await getTasks(env);
    
    // 添加到列表
    tasks.push(newTask);
    
    // 保存任务
    await saveTasks(env, tasks);
    
    // 记录事件
    await logEvent(env, 'task_created', {
      task_id: taskId,
      user_id,
      username: user.username,
      url_count: urls.length,
      submitted_by
    });
    
    // 发送通知（可选）
    await sendNotification(env, 'task_created', {
      task_id: taskId,
      username: user.username,
      email,
      url_count: urls.length
    });
    
    return jsonResponse({
      success: true,
      message: '任务创建成功',
      task: newTask
    });
    
  } catch (error) {
    console.error('创建任务失败:', error);
    return jsonResponse({ success: false, error: '创建任务失败' }, 500);
  }
}

async function handleGetTask(taskId, env) {
  try {
    const tasks = await getTasks(env);
    const task = tasks.find(t => t.task_id === taskId);
    
    if (!task) {
      return jsonResponse({ error: '任务不存在' }, 404);
    }
    
    return jsonResponse(task);
  } catch (error) {
    console.error('获取任务信息失败:', error);
    return jsonResponse({ error: '获取任务信息失败' }, 500);
  }
}

async function handleProcessTask(taskId, env) {
  try {
    const tasks = await getTasks(env);
    const taskIndex = tasks.findIndex(t => t.task_id === taskId);
    
    if (taskIndex === -1) {
      return jsonResponse({ success: false, error: '任务不存在' }, 404);
    }
    
    const task = tasks[taskIndex];
    
    // 检查任务状态
    if (task.status !== 'pending') {
      return jsonResponse({ 
        success: false, 
        error: `任务当前状态为 ${task.status}，无法开始处理` 
      }, 400);
    }
    
    // 更新任务状态
    task.status = 'processing';
    task.started_at = new Date().toISOString();
    task.progress = 10;
    
    // 保存任务
    await saveTasks(env, tasks);
    
    // 记录事件
    await logEvent(env, 'task_processing', {
      task_id: taskId,
      user_id: task.user_id
    });
    
    // 异步处理任务
    processTaskAsync(task, env);
    
    return jsonResponse({
      success: true,
      message: '任务开始处理',
      task: task
    });
    
  } catch (error) {
    console.error('开始处理任务失败:', error);
    return jsonResponse({ success: false, error: '开始处理任务失败' }, 500);
  }
}

async function processTaskAsync(task, env) {
  try {
    const tasks = await getTasks(env);
    const taskIndex = tasks.findIndex(t => t.task_id === task.task_id);
    
    if (taskIndex === -1) return;
    
    const currentTask = tasks[taskIndex];
    
    // 模拟处理过程
    const steps = [20, 40, 60, 80, 100];
    for (const progress of steps) {
      await new Promise(resolve => setTimeout(resolve, 2000)); // 模拟延迟
      
      // 更新进度
      currentTask.progress = progress;
      await saveTasks(env, tasks);
      
      // 记录进度
      await logEvent(env, 'task_progress', {
        task_id: task.task_id,
        progress
      });
    }
    
    // 完成处理
    currentTask.status = 'completed';
    currentTask.progress = 100;
    currentTask.completed_at = new Date().toISOString();
    
    // 生成模拟文件
    const files = [];
    const links = [];
    
    for (let i = 0; i < Math.min(currentTask.urls.length, 5); i++) {
      const fileName = `xueke_doc_${currentTask.task_id}_${i + 1}.pdf`;
      files.push(fileName);
      links.push(`https://xuke.ambition.qzz.io/download/${currentTask.task_id}/${fileName}`);
    }
    
    currentTask.downloaded_files = files;
    currentTask.direct_links = links;
    
    // 保存任务
    await saveTasks(env, tasks);
    
    // 记录完成事件
    await logEvent(env, 'task_completed', {
      task_id: task.task_id,
      user_id: task.user_id,
      file_count: files.length
    });
    
    // 发送完成通知
    await sendNotification(env, 'task_completed', {
      task_id: task.task_id,
      username: task.username,
      email: task.email,
      file_count: files.length,
      download_links: links.slice(0, 3) // 只发送前3个链接
    });
    
  } catch (error) {
    console.error('异步处理任务失败:', error);
    
    // 更新任务状态为失败
    try {
      const tasks = await getTasks(env);
      const taskIndex = tasks.findIndex(t => t.task_id === task.task_id);
      
      if (taskIndex !== -1) {
        tasks[taskIndex].status = 'failed';
        tasks[taskIndex].error_message = error.message;
        await saveTasks(env, tasks);
        
        await logEvent(env, 'task_failed', {
          task_id: task.task_id,
          error: error.message
        });
      }
    } catch (e) {
      console.error('更新失败状态失败:', e);
    }
  }
}

async function handleDownloadTask(taskId, env) {
  try {
    const tasks = await getTasks(env);
    const task = tasks.find(t => t.task_id === taskId);
    
    if (!task) {
      return jsonResponse({ error: '任务不存在' }, 404);
    }
    
    if (task.status !== 'completed') {
      return jsonResponse({ error: '任务未完成' }, 400);
    }
    
    return jsonResponse({
      task_id: taskId,
      direct_links: task.direct_links || [],
      files: task.downloaded_files || [],
      download_all: `https://xuke.ambition.qzz.io/download/${taskId}/all.zip`
    });
  } catch (error) {
    console.error('获取下载链接失败:', error);
    return jsonResponse({ error: '获取下载链接失败' }, 500);
  }
}

async function handleGetTaskStatus(taskId, env) {
  try {
    const tasks = await getTasks(env);
    const task = tasks.find(t => t.task_id === taskId);
    
    if (!task) {
      return jsonResponse({ error: '任务不存在' }, 404);
    }
    
    return jsonResponse({
      task_id: taskId,
      status: task.status,
      progress: task.progress,
      started_at: task.started_at,
      completed_at: task.completed_at,
      downloaded_count: task.downloaded_files ? task.downloaded_files.length : 0
    });
  } catch (error) {
    console.error('获取任务状态失败:', error);
    return jsonResponse({ error: '获取任务状态失败' }, 500);
  }
}

// ========== 统计信息 ==========
async function handleGetStats(env) {
  try {
    const [users, tasks, licenses] = await Promise.all([
      getUsers(env),
      getTasks(env),
      getLicenses(env)
    ]);
    
    // 计算统计
    const stats = {
      total_users: users.length,
      active_users: users.filter(u => u.is_active).length,
      total_tasks: tasks.length,
      pending_tasks: tasks.filter(t => t.status === 'pending').length,
      processing_tasks: tasks.filter(t => t.status === 'processing').length,
      completed_tasks: tasks.filter(t => t.status === 'completed').length,
      failed_tasks: tasks.filter(t => t.status === 'failed').length,
      total_licenses: licenses.length,
      active_licenses: licenses.filter(l => l.is_active && new Date(l.expires_at) > new Date()).length,
      expired_licenses: licenses.filter(l => new Date(l.expires_at) < new Date()).length,
      server_time: new Date().toISOString(),
      uptime: process.uptime ? Math.floor(process.uptime()) : 0
    };
    
    // 24小时任务趋势
    const now = new Date();
    const last24h = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    
    stats.tasks_last_24h = tasks.filter(t => 
      new Date(t.created_at) > last24h
    ).length;
    
    return jsonResponse(stats);
  } catch (error) {
    console.error('获取统计信息失败:', error);
    return jsonResponse({ error: '获取统计信息失败' }, 500);
  }
}

// ========== 系统设置 ==========
async function handleSaveSettings(request, env) {
  try {
    const data = await request.json();
    
    // 获取现有设置
    let settings = {};
    try {
      const settingsData = await env.KV_NAMESPACE.get('settings');
      if (settingsData) {
        settings = JSON.parse(settingsData);
      }
    } catch (e) {
      // 忽略解析错误
    }
    
    // 更新设置
    const newSettings = {
      ...settings,
      ...data,
      updated_at: new Date().toISOString(),
      updated_by: 'system'
    };
    
    // 保存设置
    await env.KV_NAMESPACE.put('settings', JSON.stringify(newSettings));
    
    // 记录事件
    await logEvent(env, 'settings_updated', {
      settings: Object.keys(data)
    });
    
    return jsonResponse({
      success: true,
      message: '设置保存成功',
      settings: newSettings
    });
  } catch (error) {
    console.error('保存设置失败:', error);
    return jsonResponse({ success: false, error: '保存设置失败' }, 500);
  }
}

async function handleBackup(env) {
  try {
    const [users, tasks, licenses, settings, logs] = await Promise.all([
      getUsers(env),
      getTasks(env),
      getLicenses(env),
      env.KV_NAMESPACE.get('settings'),
      getLogs(env, 1000) // 获取最近1000条日志
    ]);
    
    const backup = {
      timestamp: new Date().toISOString(),
      version: '2.0.0',
      users: users,
      tasks: tasks,
      licenses: licenses,
      settings: settings ? JSON.parse(settings) : {},
      logs: logs,
      summary: {
        user_count: users.length,
        task_count: tasks.length,
        license_count: licenses.length,
        log_count: logs.length
      }
    };
    
    // 记录备份事件
    await logEvent(env, 'backup_created', {
      backup_size: JSON.stringify(backup).length
    });
    
    return jsonResponse(backup);
  } catch (error) {
    console.error('创建备份失败:', error);
    return jsonResponse({ error: '创建备份失败' }, 500);
  }
}

async function handleCleanup(env) {
  try {
    const tasks = await getTasks(env);
    const now = new Date();
    const days30 = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    
    // 过滤任务：保留30天内或未完成的任务
    const filteredTasks = tasks.filter(task => {
      const createdDate = new Date(task.created_at);
      
      // 保留未完成的任务
      if (task.status !== 'completed') {
        return true;
      }
      
      // 保留30天内的任务
      return createdDate > days30;
    });
    
    // 计算清理数量
    const cleanedCount = tasks.length - filteredTasks.length;
    
    // 保存清理后的任务
    await saveTasks(env, filteredTasks);
    
    // 清理日志（保留最近1000条）
    const logs = await getLogs(env, 2000); // 获取2000条
    if (logs.length > 1000) {
      logs.splice(0, logs.length - 1000);
      await saveLogs(env, logs);
    }
    
    // 记录清理事件
    await logEvent(env, 'system_cleanup', {
      cleaned_tasks: cleanedCount,
      remaining_tasks: filteredTasks.length,
      remaining_logs: Math.min(logs.length, 1000)
    });
    
    return jsonResponse({
      success: true,
      message: `系统清理完成，移除了 ${cleanedCount} 个旧任务`,
      cleaned_tasks: cleanedCount,
      remaining_tasks: filteredTasks.length
    });
  } catch (error) {
    console.error('系统清理失败:', error);
    return jsonResponse({ success: false, error: '系统清理失败' }, 500);
  }
}

// ========== 文件下载 ==========
async function handleDownload(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;
  
  // 解析下载路径：/download/:taskId/:filename
  const parts = path.split('/').filter(p => p);
  
  if (parts.length < 3) {
    return new Response('Invalid download path', { status: 400 });
  }
  
  const taskId = parts[1];
  const filename = parts[2];
  
  try {
    // 获取任务信息
    const tasks = await getTasks(env);
    const task = tasks.find(t => t.task_id === taskId);
    
    if (!task) {
      return new Response('Task not found', { status: 404 });
    }
    
    // 检查文件是否存在于任务中
    if (task.downloaded_files && !task.downloaded_files.includes(filename)) {
      return new Response('File not found', { status: 404 });
    }
    
    // 生成模拟文件内容
    let fileContent;
    
    if (filename === 'all.zip') {
      // 生成包含所有文件的ZIP文件（模拟）
      fileContent = `This is a simulated ZIP file containing all downloaded files for task ${taskId}.
      
Task Information:
- Task ID: ${taskId}
- User: ${task.username}
- Email: ${task.email}
- Files: ${task.downloaded_files ? task.downloaded_files.join(', ') : 'None'}
- Created: ${task.created_at}

This is a placeholder file. In a real system, this would contain the actual downloaded files.`;
      
      return new Response(fileContent, {
        headers: {
          'Content-Type': 'application/zip',
          'Content-Disposition': `attachment; filename="xueke_${taskId}.zip"`,
          'Cache-Control': 'no-cache'
        }
      });
    } else {
      // 生成单个文件
      fileContent = `学科网下载文件 - ${filename}

任务信息：
- 任务ID: ${taskId}
- 用户: ${task.username}
- 邮箱: ${task.email}
- 下载时间: ${new Date().toISOString()}

文件内容：
这是学科网文档的模拟下载文件。
在实际系统中，这里应该是从学科网下载的实际文档内容。

文档ID: ${filename.replace('.pdf', '').split('_').pop()}
生成时间: ${new Date().toISOString()}`;
      
      return new Response(fileContent, {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `attachment; filename="${filename}"`,
          'Cache-Control': 'no-cache'
        }
      });
    }
    
  } catch (error) {
    console.error('处理下载请求失败:', error);
    return new Response('Download failed', { status: 500 });
  }
}

// ========== 数据访问辅助函数 ==========
async function getUsers(env) {
  try {
    const usersData = await env.KV_NAMESPACE.get('users');
    return usersData ? JSON.parse(usersData) : getDefaultUsers();
  } catch (error) {
    console.error('获取用户数据失败:', error);
    return getDefaultUsers();
  }
}

async function saveUsers(env, users) {
  try {
    await env.KV_NAMESPACE.put('users', JSON.stringify(users));
  } catch (error) {
    console.error('保存用户数据失败:', error);
  }
}

async function getTasks(env) {
  try {
    const tasksData = await env.KV_NAMESPACE.get('tasks');
    return tasksData ? JSON.parse(tasksData) : [];
  } catch (error) {
    console.error('获取任务数据失败:', error);
    return [];
  }
}

async function saveTasks(env, tasks) {
  try {
    await env.KV_NAMESPACE.put('tasks', JSON.stringify(tasks));
  } catch (error) {
    console.error('保存任务数据失败:', error);
  }
}

async function getLicenses(env) {
  try {
    const licensesData = await env.KV_NAMESPACE.get('licenses');
    return licensesData ? JSON.parse(licensesData) : getDefaultLicenses();
  } catch (error) {
    console.error('获取许可证数据失败:', error);
    return getDefaultLicenses();
  }
}

async function saveLicenses(env, licenses) {
  try {
    await env.KV_NAMESPACE.put('licenses', JSON.stringify(licenses));
  } catch (error) {
    console.error('保存许可证数据失败:', error);
  }
}

async function getLogs(env, limit = 1000) {
  try {
    const logsData = await env.KV_NAMESPACE.get('logs');
    const logs = logsData ? JSON.parse(logsData) : [];
    
    // 按时间排序，最新的在前面
    logs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    // 限制数量
    return logs.slice(0, limit);
  } catch (error) {
    console.error('获取日志失败:', error);
    return [];
  }
}

async function saveLogs(env, logs) {
  try {
    await env.KV_NAMESPACE.put('logs', JSON.stringify(logs));
  } catch (error) {
    console.error('保存日志失败:', error);
  }
}

async function logEvent(env, type, data) {
  try {
    const logs = await getLogs(env, 2000); // 获取现有日志
    
    const logEntry = {
      id: generateId('log'),
      type,
      data,
      timestamp: new Date().toISOString(),
      ip: 'system'
    };
    
    logs.push(logEntry);
    
    // 限制日志数量
    if (logs.length > 2000) {
      logs.splice(0, logs.length - 2000);
    }
    
    await saveLogs(env, logs);
  } catch (error) {
    console.error('记录日志失败:', error);
  }
}

async function sendNotification(env, type, data) {
  // 这里可以集成邮件、Webhook等通知方式
  // 目前仅记录日志
  await logEvent(env, `notification_${type}`, data);
}

// ========== 默认数据 ==========
function getDefaultUsers() {
  return [
    {
      id: 'user_admin_001',
      username: 'admin',
      email: 'admin@example.com',
      password_hash: 'admin123', // 注意：实际应该使用加密哈希
      user_type: 'admin',
      is_active: true,
      created_at: new Date().toISOString(),
      last_login: new Date().toISOString(),
      last_activity: new Date().toISOString(),
      device_id: null
    },
    {
      id: 'user_test_001',
      username: 'testuser',
      email: 'test@example.com',
      password_hash: 'test123',
      user_type: 'user',
      is_active: true,
      created_at: new Date().toISOString(),
      last_login: null,
      last_activity: null,
      device_id: null
    }
  ];
}

function getDefaultLicenses() {
  const now = new Date();
  const futureDate = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000); // 30天后
  
  return [
    {
      id: 'license_001',
      license_key: 'XUKE-2024-ABCD-EFGH',
      user_id: 'user_admin_001',
      username: 'admin',
      days: 30,
      max_uses: 10,
      used_count: 3,
      created_at: now.toISOString(),
      expires_at: futureDate.toISOString(),
      is_active: true,
      activated_at: now.toISOString(),
      device_id: 'device_001',
      last_use: now.toISOString()
    },
    {
      id: 'license_002',
      license_key: 'XUKE-2024-IJKL-MNOP',
      user_id: 'user_test_001',
      username: 'testuser',
      days: 7,
      max_uses: 3,
      used_count: 1,
      created_at: now.toISOString(),
      expires_at: new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      is_active: true,
      activated_at: now.toISOString(),
      device_id: 'device_002',
      last_use: now.toISOString()
    }
  ];
}

// ========== 工具函数 ==========
function generateId(prefix = 'id') {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substr(2, 9);
  return `${prefix}_${timestamp}_${random}`;
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'no-cache'
    }
  });
}