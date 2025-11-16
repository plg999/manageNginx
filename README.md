Nginx管理系统 (Nginx Management System)
一个基于Django + Vue.js的现代化Nginx服务器管理系统，提供可视化的Nginx配置管理和服务器状态监控。

🚀 功能特性
后端功能 (Django REST API)
用户管理: 完整的用户认证和权限管理系统
Nginx配置管理: 支持远程Nginx配置文件的读取、编辑和上传
服务器状态监控: 实时监控Nginx服务器状态和负载均衡配置
SSH远程连接: 安全的SSH连接管理远程服务器
配置解析: 自动解析Nginx配置文件，提取upstream、server等配置信息
数据库支持: MySQL数据库存储配置和服务器信息
前端功能 (Vue.js界面)
响应式界面: 现代化的Vue.js前端界面
实时状态展示: 动态显示服务器状态和配置信息
配置可视化: 直观的Nginx配置编辑和管理界面
用户友好: 简洁易用的操作界面
🛠️ 技术栈
后端技术
框架: Django 5.2.7 + Django REST Framework
数据库: MySQL
认证: JWT (JSON Web Tokens)
SSH连接: Paramiko
CORS支持: django-cors-headers
前端技术
框架: Vue.js 3
构建工具: Vue CLI
UI组件: Element Plus (可选)
路由: Vue Router
📦 项目结构

plainText
djnginx/
├── auth_app/          # 用户认证模块
├── client_app/        # 客户端管理模块
├── nginx_app/         # Nginx配置管理模块
├── djnginx/           # Django项目配置
├── NginxUI/           # 前端Vue.js项目
│   └── nginxvue/
│       ├── src/
│       │   ├── components/    # Vue组件
│       │   ├── router/        # 路由配置
│       │   └── assets/       # 静态资源
│       └── package.json
└── manage.py          # Django管理脚本
🚀 快速开始
环境要求
Python 3.8+
Node.js 14+
MySQL 5.7+
Git
后端部署
克隆项目

bash
git clone <repository-url>
cd djnginx
创建虚拟环境

bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
安装依赖

bash
pip install -r requirements.txt
数据库配置

sql
Apply
CREATE DATABASE nginx_manager_db;
修改数据库配置 编辑 djnginx/settings.py 中的数据库配置：

python
Apply
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'nginx_manager_db',
        'USER': 'your_username',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
数据库迁移

bash
python manage.py makemigrations
python manage.py migrate
创建超级用户

bash
python manage.py createsuperuser
启动后端服务

bash
python manage.py runserver
前端部署
进入前端目录

bash
cd NginxUI/nginxvue
安装依赖

bash
npm install
启动开发服务器

bash
npm run serve
构建生产版本

bash
npm run build
🔧 配置说明
后端配置
数据库: 支持MySQL数据库
认证: JWT token认证
CORS: 支持跨域请求
日志: 自动创建日志目录
前端配置
API地址: 配置后端API地址
端口: 默认运行在8888端口
📖 API文档
主要API端点
用户管理
POST /api/users/login/ - 用户登录
POST /api/users/register/ - 用户注册
GET /api/users/profile/ - 获取用户信息
Nginx配置管理
GET /api/configs/read/ - 读取Nginx配置
POST /api/configs/upload/ - 上传Nginx配置
POST /api/configs/create/ - 创建Nginx配置
服务器管理
GET /api/servers/backend_server/readAll/ - 获取所有后端服务器
GET /api/servers/upstream/ - 获取upstream配置
POST /api/servers/backend_server/status/update/ - 更新服务器状态
🐛 故障排除
常见问题
数据库连接失败

检查MySQL服务是否启动
验证数据库配置信息
SSH连接失败

检查远程服务器SSH服务状态
验证SSH密钥和权限
前端无法连接后端

检查后端服务是否运行
验证CORS配置
🤝 贡献指南
欢迎提交Issue和Pull Request来改进这个项目！

Fork本项目
创建特性分支 (git checkout -b feature/AmazingFeature)
提交更改 (git commit -m 'Add some AmazingFeature')
推送到分支 (git push origin feature/AmazingFeature)
开启Pull Request

注意: 这是一个开发中的项目，生产环境使用前请进行充分测试。

这个README文档包含了项目的完整介绍、安装指南、使用说明和故障排除信息。您可以根据需要进一步调整和完善。
