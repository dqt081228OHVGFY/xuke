#!/bin/bash

# ==============================================
# 学科网下载系统 - Cloudflare Worker 部署脚本
# ==============================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函数：打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 函数：检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装，请先安装"
        exit 1
    fi
}

# 函数：创建目录结构
create_directories() {
    print_info "创建目录结构..."
    
    mkdir -p public
    mkdir -p uploads
    mkdir -p logs
    mkdir -p config
    mkdir -p backups
    
    # 创建前端HTML文件
    cat > public/index.html << 'EOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>学科网下载系统</title>
    <style>
        /* 这里可以放你的CSS样式 */
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        
        .status-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #4CAF50;
        }
        
        .btn {
            display: inline-block;
            padding: 10px 20px;
            background: #4CAF50;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px 5px;
        }
        
        .btn:hover {
            background: #45a049;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 学科网下载系统</h1>
        
        <div class="status-card">
            <h2>系统状态</h2>
            <p id="status">正在检测系统状态...</p>
        </div>
        
        <div>
            <a href="/api/ping" class="btn" target="_blank">测试API</a>
            <a href="/api/stats" class="btn" target="_blank">查看统计</a>
            <button onclick="checkHealth()" class="btn">检查健康状态</button>
        </div>
        
        <div style="margin-top: 30px;">
            <h3>管理员入口</h3>
            <p>请使用管理员账号登录客户端进行管理。</p>
            <p>默认管理员账号: admin / admin123</p>
        </div>
    </div>
    
    <script>
        async function checkHealth() {
            try {
                const response = await fetch('/api/ping');
                const data = await response.json();
                document.getElementById('status').innerHTML = `
                    ✅ 系统运行正常<br>
                    版本: ${data.version || '未知'}<br>
                    时间: ${data.timestamp || '未知'}
                `;
            } catch (error) {
                document.getElementById('status').innerHTML = '❌ 系统连接失败';
            }
        }
        
        // 页面加载时检查状态
        window.onload = checkHealth;
    </script>
</body>
</html>
EOF
    
    print_success "目录结构创建完成"
}

# 函数：检查并安装依赖
check_dependencies() {
    print_info "检查依赖..."
    
    # 检查 Node.js
    if ! node --version &> /dev/null; then
        print_warning "Node.js 未安装，请先安装 Node.js"
        print_info "推荐安装方式:"
        echo "1. 使用 nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
        echo "2. 然后: nvm install 18"
        exit 1
    fi
    
    # 检查 wrangler
    if ! npm list -g wrangler &> /dev/null; then
        print_info "安装 Wrangler CLI..."
        npm install -g wrangler
    fi
    
    print_success "依赖检查完成"
}

# 函数：登录 Cloudflare
login_cloudflare() {
    print_info "登录 Cloudflare..."
    
    if ! wrangler whoami &> /dev/null; then
        print_warning "未检测到 Cloudflare 登录，请登录..."
        wrangler login
        
        if [ $? -ne 0 ]; then
            print_error "Cloudflare 登录失败"
            exit 1
        fi
    fi
    
    print_success "Cloudflare 登录成功"
}

# 函数：创建 KV 命名空间
create_kv_namespace() {
    local namespace_name="XUKE_KV"
    local binding_name="KV_NAMESPACE"
    
    print_info "创建 KV 命名空间: $namespace_name"
    
    # 检查是否已存在
    if wrangler kv:namespace list | grep -q "$namespace_name"; then
        print_warning "KV 命名空间已存在，跳过创建"
        local kv_id=$(wrangler kv:namespace list | grep "$namespace_name" | head -1 | awk '{print $2}')
        echo "命名空间ID: $kv_id"
        
        # 更新配置文件
        sed -i.bak "s/REPLACE_WITH_YOUR_KV_ID/$kv_id/g" wrangler.toml
        return
    fi
    
    # 创建生产环境命名空间
    print_info "创建生产环境 KV 命名空间..."
    local kv_output=$(wrangler kv:namespace create "$namespace_name" 2>&1)
    
    if [ $? -eq 0 ]; then
        local kv_id=$(echo "$kv_output" | grep -o "id=\"[^\"]*\"" | sed 's/id="//;s/"//')
        print_success "KV 命名空间创建成功: $kv_id"
        
        # 更新配置文件
        sed -i.bak "s/REPLACE_WITH_YOUR_KV_ID/$kv_id/g" wrangler.toml
    else
        print_error "创建 KV 命名空间失败"
        echo "错误信息: $kv_output"
        exit 1
    fi
}

# 函数：创建预览环境 KV 命名空间
create_preview_kv() {
    print_info "创建预览环境 KV 命名空间..."
    
    local kv_output=$(wrangler kv:namespace create "XUKE_KV_PREVIEW" --preview 2>&1)
    
    if [ $? -eq 0 ]; then
        local kv_id=$(echo "$kv_output" | grep -o "id=\"[^\"]*\"" | sed 's/id="//;s/"//')
        print_success "预览 KV 命名空间创建成功: $kv_id"
        
        # 添加到配置文件
        if ! grep -q "preview_id" wrangler.toml; then
            sed -i "/\[\[kv_namespaces\]\]/a\preview_id = \"$kv_id\"" wrangler.toml
        fi
    else
        print_warning "创建预览 KV 命名空间失败（可能已存在）"
    fi
}

# 函数：初始化数据库
initialize_database() {
    print_info "初始化数据库..."
    
    # 等待 Worker 部署完成
    sleep 10
    
    # 测试 API
    local worker_url=$(wrangler whoami | grep -o "workers.dev/.*" | head -1)
    if [ -z "$worker_url" ]; then
        worker_url="xueke-download-system.workers.dev"
    fi
    
    print_info "测试 Worker URL: https://$worker_url"
    
    # 创建初始化数据
    cat > config/init_data.json << 'EOF'
{
    "users": [
        {
            "username": "admin",
            "email": "admin@example.com",
            "password": "admin123",
            "user_type": "admin"
        },
        {
            "username": "demo",
            "email": "demo@example.com",
            "password": "demo123",
            "user_type": "user"
        }
    ],
    "licenses": [
        {
            "license_key": "XUKE-2024-ADMIN-0001",
            "username": "admin",
            "days": 365,
            "max_uses": 999
        },
        {
            "license_key": "XUKE-2024-DEMO-0001",
            "username": "demo",
            "days": 30,
            "max_uses": 10
        }
    ]
}
EOF
    
    print_success "初始化数据已创建"
}

# 函数：部署 Worker
deploy_worker() {
    print_info "部署 Worker 到 Cloudflare..."
    
    # 先进行预发布测试
    print_info "进行预发布测试..."
    if wrangler deploy --dry-run; then
        print_success "预发布测试通过"
    else
        print_error "预发布测试失败，请检查代码"
        exit 1
    fi
    
    # 实际部署
    print_info "开始部署..."
    local deploy_output=$(wrangler deploy 2>&1)
    
    if [ $? -eq 0 ]; then
        print_success "Worker 部署成功!"
        
        # 提取部署信息
        echo "$deploy_output" | grep -E "(https://|deployed to)" | head -5
        
        # 保存部署信息
        echo "$deploy_output" > logs/deploy_$(date +%Y%m%d_%H%M%S).log
    else
        print_error "Worker 部署失败"
        echo "错误信息: $deploy_output"
        exit 1
    fi
}

# 函数：配置自定义域名
setup_custom_domain() {
    local domain="xuke.ambition.qzz.io"
    
    print_info "设置自定义域名: $domain"
    
    echo ""
    echo "📋 请手动在 Cloudflare Dashboard 中配置自定义域名:"
    echo ""
    echo "1. 访问 https://dash.cloudflare.com/"
    echo "2. 进入 Workers & Pages"
    echo "3. 找到 'xueke-download-system'"
    echo "4. 点击 '自定义域'"
    echo "5. 添加: $domain"
    echo ""
    echo "或者使用以下命令（如果域名在 Cloudflare 上托管）:"
    echo "wrangler route add '$domain/*' --zone ambition.qzz.io"
    echo ""
    
    read -p "是否要尝试自动配置域名？ (y/n): " choice
    if [ "$choice" = "y" ] || [ "$choice" = "Y" ]; then
        print_info "尝试配置路由..."
        wrangler route add "$domain/*" --zone ambition.qzz.io 2>&1 | tee logs/route_setup.log
    fi
}

# 函数：运行测试
run_tests() {
    print_info "运行系统测试..."
    
    local worker_url=$(wrangler whoami | grep -o "workers.dev/.*" | head -1)
    if [ -z "$worker_url" ]; then
        worker_url="xueke-download-system.workers.dev"
    fi
    
    local test_url="https://$worker_url"
    
    print_info "测试 URL: $test_url"
    
    # 测试 ping 接口
    print_info "测试 ping 接口..."
    curl -s "$test_url/api/ping" | jq . 2>/dev/null || curl -s "$test_url/api/ping"
    echo ""
    
    # 测试 stats 接口
    print_info "测试 stats 接口..."
    curl -s "$test_url/api/stats" | jq . 2>/dev/null || curl -s "$test_url/api/stats"
    echo ""
    
    print_success "基本功能测试完成"
}

# 函数：创建环境配置文件
create_env_config() {
    print_info "创建环境配置文件..."
    
    cat > .env << EOF
# 学科网下载系统环境配置
# 生成时间: $(date)

# Cloudflare 配置
CF_ACCOUNT_ID=$(wrangler whoami | grep "Account ID" | awk '{print $3}')
CF_WORKER_NAME=xueke-download-system
CF_KV_NAMESPACE=$(grep "id =" wrangler.toml | head -1 | cut -d'"' -f2)

# 系统配置
SYSTEM_URL=https://xuke.ambition.qzz.io
API_BASE_URL=https://xuke.ambition.qzz.io/api
CLIENT_VERSION=2.0.0

# 默认账号（首次部署后请修改）
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123
DEFAULT_ADMIN_LICENSE=XUKE-2024-ADMIN-0001

# 部署信息
DEPLOY_DATE=$(date "+%Y-%m-%d %H:%M:%S")
DEPLOY_VERSION=2.0.0
EOF
    
    cat > config/client_config.json << 'EOF'
{
    "server": {
        "url": "https://xuke.ambition.qzz.io",
        "timeout": 30
    },
    "user": {
        "username": "admin",
        "email": "admin@example.com",
        "license_key": "XUKE-2024-ADMIN-0001",
        "auto_login": false
    },
    "connection": {
        "heartbeat_interval": 60,
        "status_check_interval": 10,
        "auto_reconnect": true
    }
}
EOF
    
    print_success "环境配置文件创建完成"
}

# 函数：显示部署摘要
show_deployment_summary() {
    local worker_url=$(wrangler whoami | grep -o "workers.dev/.*" | head -1)
    if [ -z "$worker_url" ]; then
        worker_url="xueke-download-system.workers.dev"
    fi
    
    echo ""
    echo "=============================================="
    echo "            🎉 部署完成！"
    echo "=============================================="
    echo ""
    echo "🌐 系统访问地址:"
    echo "   主界面: https://$worker_url"
    echo "   自定义域名: https://xuke.ambition.qzz.io"
    echo ""
    echo "🔧 管理信息:"
    echo "   管理员账号: admin"
    echo "   管理员密码: admin123"
    echo "   管理员激活码: XUKE-2024-ADMIN-0001"
    echo ""
    echo "📱 客户端配置:"
    echo "   服务器地址: https://xuke.ambition.qzz.io"
    echo "   或使用: https://$worker_url"
    echo ""
    echo "🔍 测试链接:"
    echo "   API状态: https://$worker_url/api/ping"
    echo "   系统统计: https://$worker_url/api/stats"
    echo ""
    echo "📝 重要提示:"
    echo "   1. 首次使用请修改默认密码"
    echo "   2. 在 Cloudflare Dashboard 中配置自定义域名"
    echo "   3. 查看 logs/ 目录下的日志文件"
    echo "   4. 配置文件保存在 config/ 目录"
    echo ""
    echo "🚀 下一步操作:"
    echo "   1. 运行客户端测试连接"
    echo "   2. 在网站上添加用户"
    echo "   3. 为用户生成激活码"
    echo "   4. 开始使用系统"
    echo "=============================================="
}

# 主函数
main() {
    clear
    echo "=============================================="
    echo "    学科网下载系统 - Cloudflare 部署工具"
    echo "=============================================="
    echo ""
    
    # 检查参数
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        echo "使用说明:"
        echo "  ./deploy.sh           # 完整部署"
        echo "  ./deploy.sh --test    # 仅测试"
        echo "  ./deploy.sh --update  # 更新部署"
        echo "  ./deploy.sh --clean   # 清理环境"
        exit 0
    fi
    
    # 模式选择
    local mode="full"
    if [ "$1" = "--test" ]; then
        mode="test"
    elif [ "$1" = "--update" ]; then
        mode="update"
    elif [ "$1" = "--clean" ]; then
        mode="clean"
    fi
    
    case $mode in
        "full")
            # 完整部署流程
            check_dependencies
            login_cloudflare
            create_directories
            create_kv_namespace
            create_preview_kv
            deploy_worker
            setup_custom_domain
            initialize_database
            create_env_config
            run_tests
            show_deployment_summary
            ;;
        "test")
            # 测试模式
            check_dependencies
            login_cloudflare
            run_tests
            ;;
        "update")
            # 更新模式
            print_info "更新部署..."
            deploy_worker
            run_tests
            print_success "更新完成"
            ;;
        "clean")
            # 清理模式
            print_info "清理部署环境..."
            rm -rf public uploads logs config backups
            print_success "清理完成"
            ;;
    esac
    
    # 保存部署历史
    echo "$(date): 部署完成，模式=$mode" >> logs/deploy_history.log
}

# 错误处理
set -e
trap 'print_error "部署过程出现错误，退出码: $?"' ERR

# 运行主函数
main "$@"