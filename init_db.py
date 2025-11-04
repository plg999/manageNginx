#!/usr/bin/env python
import os
import django
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djnginx.settings')
django.setup()

def create_superuser():
    User = get_user_model()
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        print("超级用户创建成功: admin/admin123")

if __name__ == '__main__':
    create_superuser()