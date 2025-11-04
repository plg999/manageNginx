from rest_framework import serializers
from .models import ClientInfo
from rest_framework.decorators import api_view
from rest_framework.response import Response
class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientInfo
        fields = ['id', 'ip', 'port', 'created_at']


@api_view(['POST'])
def register_client(request):
    """客户端注册"""
    ip = request.data.get('client_uvicorn_ip')
    port = request.data.get('client_uvicorn_port')

    client, created = ClientInfo.objects.get_or_create(
        ip=ip,
        defaults={'port': port}
    )

    if not created:
        client.port = port
        client.save()

    return Response({
        'msg': f'客户端 {ip}:{port} 注册成功',
        'status': 200
    })

@api_view(['GET'])
def get_clients(request):
    """获取客户端列表"""
    clients = ClientInfo.objects.all()
    serializer = ClientSerializer(clients, many=True)
    return Response(serializer.data)