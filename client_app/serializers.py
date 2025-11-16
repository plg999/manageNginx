from rest_framework import serializers
from .models import ClientInfo
from rest_framework.decorators import api_view
from rest_framework.response import Response
class ClientInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientInfo
        fields = ['id', 'client_ip', 'client_port','created_at','updated_at']

