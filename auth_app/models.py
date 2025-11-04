
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # 修复表名冲突
    class Meta:
        db_table = 'custom_user'  # 修改为不同的表名
        verbose_name = '自定义用户'
        verbose_name_plural = '自定义用户'

    def __str__(self):
        return self.username