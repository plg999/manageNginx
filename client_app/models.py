from django.db import models

class ClientInfo(models.Model):
    client_ip = models.GenericIPAddressField(unique=True)
    client_port = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'client_info'

    def __str__(self):
        return f"{self.client_ip}:{self.client_port}"