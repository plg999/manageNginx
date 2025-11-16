from rest_framework import serializers
from .models import ClientInfo, NginxConfigFile, BackendServerInfo


class NginxConfigFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = NginxConfigFile
        fields = '__all__'

class BackendServerInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackendServerInfo
        fields = '__all__'

class NginxConfigCreateSerializer(serializers.Serializer):
    client_ip = serializers.IPAddressField()
    file_path = serializers.CharField()

class NginxConfigUpdateSerializer(serializers.Serializer):
    client_ip = serializers.IPAddressField()
    file_path = serializers.CharField()
    file_content = serializers.CharField()

class BackendServerStatusSerializer(serializers.Serializer):
    client_ip = serializers.IPAddressField()
    file_path = serializers.CharField()
    backend_server_addr = serializers.IPAddressField()
    status = serializers.ChoiceField(choices=['up', 'down', 'backup'])