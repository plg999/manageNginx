from django.db import models
from django.contrib.auth import get_user_model

from client_app.models import ClientInfo

User = get_user_model()

class NginxConfigFile(models.Model):
    client = models.ForeignKey(ClientInfo, on_delete=models.CASCADE, related_name='config_files')
    file_path = models.CharField(max_length=500)  # 改为CharField并指定长度
    file_content = models.CharField(max_length=500)
    file_md5 = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'nginx_config_file'
        # unique_together = ['client', 'file_path']

    def __str__(self):
        return self.file_path


class BackendServerInfo(models.Model):
    STATUS_CHOICES = [
        ('up', '正常'),
        ('down', '下线'),
        ('backup', '备用'),
    ]

    client = models.ForeignKey(ClientInfo, on_delete=models.CASCADE, related_name='backend_servers')
    backend_server_addr = models.GenericIPAddressField()
    file_path = models.CharField(max_length=500)  # 改为CharField并指定长度
    upstream = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='up')
    weight = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'backend_server_info'
        unique_together = ['client', 'backend_server_addr']

    def __str__(self):
        return f"{self.backend_server_addr} ({self.status})"