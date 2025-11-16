



from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ClientInfo
from .serializers import ClientInfoSerializer
from .client import NginxParamikoClient
@api_view(['POST'])
def health_check(request):
    """
    健康检查API端点 - 根据前端提供的IP和密码检查Nginx端口状态
    """
    try:
        # 从请求数据中获取连接参数
        host = request.data.get('host')
        username = request.data.get('username')
        password = request.data.get('password')
        port = request.data.get('port', 22)  # 默认SSH端口22
        key_file = request.data.get('key_file')  # 可选：密钥文件路径
        key_content = request.data.get('key_content')  # 可选：密钥内容

        # 验证必填参数
        if not host:
            return Response({
                'msg': 'host为必填参数',
                'status': 400
            }, status=400)

        if not username:
            return Response({
                'msg': 'username为必填参数',
                'status': 400
            }, status=400)

        # 至少需要密码或密钥认证
        if not password and not key_file and not key_content:
            return Response({
                'msg': '需要提供密码或密钥认证',
                'status': 400
            }, status=400)

        # 创建Paramiko客户端
        client = NginxParamikoClient(
            host=host,
            port=port,
            username=username,
            password=password,
            key_file=key_file,
            key_content=key_content
        )

        # 建立SSH连接
        if client.connect():
            # 检查Nginx进程是否存在
            nginx_process_result = client.execute_command('ps aux | grep nginx | grep -v grep')

            # 检查Nginx端口（默认80和443）
            port_80_result = client.execute_command('ss -tlnp | grep :80')
            port_443_result = client.execute_command('ss -tlnp | grep :443')

            # 检查Nginx服务状态
            service_result = client.execute_command(
                'systemctl status nginx 2>/dev/null || service nginx status 2>/dev/null || echo "无法获取服务状态"')
            print('systemct ',service_result)
            client.close()

            # 分析结果
            nginx_running = nginx_process_result['success'] and 'nginx' in nginx_process_result['output']
            port_80_open = port_80_result['success'] and ':80' in port_80_result['output']
            port_443_open = port_443_result['success'] and ':443' in port_443_result['output']
            service_active = 'active (running)' in service_result['output'] if service_result['success'] else False

            # 构建响应
            response_data = {
                'code':200,
                'status': 'healthy' if nginx_running else 'unhealthy',
                'message': 'Nginx健康检查完成',
                'nginx_running': nginx_running,
                'port_80_open': port_80_open,
                'port_443_open': port_443_open,
                'service_status': 'active' if service_active else 'inactive',
                'auth_type': 'key' if key_file or key_content else 'password',
                'server_info': {
                    'host': host,
                    'port': port,
                    'username': username
                }
            }

            return Response(response_data)
        else:
            return Response({
                'status': 'error',
                'message': '无法建立SSH连接',
                'server_info': {
                    'host': host,
                    'port': port,
                    'username': username
                }
            }, status=400)

    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'健康检查失败: {str(e)}',
            'server_info': {
                'host': host if 'host' in locals() else 'unknown',
                'port': port if 'port' in locals() else 22,
                'username': username if 'username' in locals() else 'unknown'
            }
        }, status=400)

@api_view(['POST'])
def register_client(request):
    """客户端注册"""
    client_ip = request.data.get('client_ip')  # 修改：使用正确的字段名
    client_port = request.data.get('client_port')  # 修改：使用正确的字段名
    host = request.data.get('host', '127.0.0.1')  # 新增：SSH服务器IP
    port = request.data.get('port', 22)  # 新增：SSH端口
    username = request.data.get('username')  # 新增：SSH用户名
    password = request.data.get('password')  # 新增：SSH密码
    name = request.data.get('name')  # 新增：客户端名称
    nginx_config_path = request.data.get('nginx_config_path')  # 新增：Nginx配置路径

    # 验证必填参数
    if not client_ip:
        return Response({
            'msg': 'client_ip为必填参数',
            'status': 400
        }, status=400)

    if not client_port:
        return Response({
            'msg': 'client_port为必填参数',
            'status': 400
        }, status=400)

    # 创建或更新客户端信息
    client, created = ClientInfo.objects.get_or_create(
        client_ip=client_ip,  # 修改：使用正确的字段名
        defaults={
            'client_port': client_port,
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'name': name,
            'nginx_config_path': nginx_config_path
        }
    )

    if not created:
        # 更新现有记录
        client.client_port = client_port
        client.host = host
        client.port = port
        client.username = username
        client.password = password
        client.name = name
        client.nginx_config_path = nginx_config_path
        client.save()

    return Response({
        'msg': f'客户端 {client_ip}:{client_port} 注册成功',
        'status': 200,
        'created': created,
        'client_info': {
            'id': client.id,
            'name': client.name,
            'client_ip': client.client_ip,
            'client_port': client.client_port,
            'host': client.host,
            'port': client.port,
            'username': client.username,
            'nginx_config_path': client.nginx_config_path
        }
    })


@api_view(['GET'])
def get_clients(request):
    """获取客户端列表"""
    clients = ClientInfo.objects.all()
    serializer = ClientInfoSerializer(clients, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def get_client_ip_list(request):
    """
    获取所有客户端IP列表
    API端点: GET /api/clients/

    功能: 查询系统中所有已注册的客户端信息

    参数:
        request: Django请求对象，包含查询参数

    返回:
        Response: 包含客户端列表的JSON响应
    """
    # 查询所有客户端信息
    clients = ClientInfo.objects.all()
    # 使用序列化器将模型对象转换为JSON格式
    serializer = ClientInfoSerializer(clients, many=True)
    response_data = {
        'clients': serializer.data,
        'total_count': clients.count(),
        'status': 200
    }
    return Response(response_data)


@api_view(['POST'])
def receive_client_info(request):
    """
    接收并更新客户端信息
    API端点: POST /api/clients/

    功能: 客户端启动时注册或更新其IP和端口信息

    参数:
        request: 包含客户端信息的POST请求
        - client_uvicorn_ip: 客户端IP地址
        - client_uvicorn_port: 客户端端口号

    返回:
        Response: 操作结果消息和状态码
    """
    # 从请求数据中获取客户端IP和端口
    client_ip = request.data.get('client_uvicorn_ip')
    client_port = request.data.get('client_uvicorn_port')

    # 更新或创建客户端记录
    # 如果客户端IP已存在则更新端口，不存在则创建新记录
    client, created = ClientInfo.objects.update_or_create(
        client_ip=client_ip,
        defaults={'client_port': client_port}
    )

    return Response({
        'msg': f'客户端信息已更新: {client_ip}:{client_port}',
        'status': 200
    })

