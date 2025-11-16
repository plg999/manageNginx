from django.db import models

class ClientInfo(models.Model):
    name = models.CharField(max_length=100,null=True,blank=True)
    host = models.GenericIPAddressField(default='127.0.0.1',null=True,blank=True)
    port = models.IntegerField(default=22)
    username = models.CharField(max_length=50,null=True,blank=True)
    password = models.CharField(max_length=100,null=True,blank=True)
    client_ip = models.GenericIPAddressField(unique=True,null=True,blank=True)
    client_port = models.IntegerField()
    nginx_config_path = models.CharField(max_length=200,null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'client_info'

    def __str__(self):
        return f"{self.client_ip}:{self.client_port}"