#!/usr/bin/env python
import os
import django
import sys
from django.contrib.auth import get_user_model
# 添加Django项目路径到Python路径
django_project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, django_project_path)
# 设置Django设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djnginx.settings')

# 配置Django设置
try:
    django.setup()
except Exception as e:
    print(f"Django设置失败: {e}")
    sys.exit(1)

from client_app.models import ClientInfo

def create_superuser():
    User = get_user_model()
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        print("超级用户创建成功: admin/admin123")

def create_sample_client_data():
    '''创建客户端数据'''
    sample_clients = [
        {'client_ip': '192.168.1.100', 'client_port': 80},
        {'client_ip': '192.168.1.101', 'client_port': 8080},
        {'client_ip': '192.168.1.102', 'client_port': 443},
        {'client_ip': '10.0.0.10', 'client_port': 80},
        {'client_ip': '10.0.0.11', 'client_port': 8080},
    ]
    created_count = 0
    for client_data in sample_clients:
        try:
            client,created = ClientInfo.objects.get_or_create(

                client_ip= client_data['client_ip'],
                defaults={'client_port':client_data['client_port']}
            )
            if created:
                created_count += 1
                print(f"创建客户端: {client}")
            else:
                print(f"客户端已存在")

        except Exception as e:
            print(f"创建客户端 {client_data['client_ip']} 时出错: {e}")
    print(f"成功创建/更新了 {created_count} 个客户端记录")
if __name__ == '__main__':
    create_superuser()
    create_sample_client_data()