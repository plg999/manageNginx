# -*- coding: utf-8 -*-
"""
Nginx配置管理系统的视图模块
提供客户端管理、配置文件管理、后端服务器管理等API接口
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
import hashlib
import requests

from .models import ClientInfo, NginxConfigFile, BackendServerInfo
from .serializers import (
    ClientInfoSerializer, NginxConfigFileSerializer, BackendServerInfoSerializer,
    NginxConfigCreateSerializer, NginxConfigUpdateSerializer, BackendServerStatusSerializer
)
from .utils import get_client_port


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
    return Response(serializer.data)


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


@api_view(['POST'])
def receive_nginx_file_path_and_content(request):
    """
    接收并同步Nginx配置文件内容
    API端点: POST /api/configs/sync/

    功能: 同步客户端的配置文件到中央数据库，支持增量更新

    参数:
        request: 包含文件路径和内容的POST请求
        - client_ip: 客户端IP地址
        - file_path_and_content_dict: 文件路径和内容的字典

    返回:
        Response: 同步结果消息和状态码
    """
    try:
        data = request.data
        client_ip = data.get('client_ip')
        # 复制数据字典并移除client_ip字段，剩下的就是文件路径和内容
        file_content_dict = data.copy()
        file_content_dict.pop('client_ip')

        # 根据客户端IP获取客户端对象，如果不存在返回404
        client = get_object_or_404(ClientInfo, client_ip=client_ip)

        # 使用数据库事务保证数据一致性
        with transaction.atomic():
            # 遍历所有文件路径和内容，进行同步更新
            for file_path, file_content in file_content_dict.items():
                # 计算文件内容的MD5哈希值，用于检测内容变化
                file_content_md5 = hashlib.md5(file_content.encode('utf-8')).hexdigest()

                # 更新或创建配置文件记录
                config_file, created = NginxConfigFile.objects.update_or_create(
                    client=client,
                    file_path=file_path,
                    defaults={
                        'file_content': file_content,
                        'file_md5': file_content_md5
                    }
                )

            # 清理数据库中已不存在的文件记录
            existing_files = NginxConfigFile.objects.filter(client=client)
            for config_file in existing_files:
                if config_file.file_path not in file_content_dict:
                    config_file.delete()

        return Response({'msg': '配置文件同步成功', 'status': 200})

    except Exception as e:
        # 捕获所有异常并返回错误信息
        return Response({'msg': str(e), 'status': 400}, status=400)


@api_view(['POST'])
def receive_backend_server_info(request):
    """
    接收并同步后端服务器信息
    API端点: POST /api/servers/sync/

    功能: 全量同步客户端的后端服务器信息到数据库

    参数:
        request: 包含后端服务器信息的POST请求
        - client_ip: 客户端IP地址
        - backend_server_info_dict: 后端服务器信息字典

    返回:
        Response: 同步结果消息和状态码
    """
    try:
        data = request.data
        client_ip = data.get('client_ip')
        backend_server_info_dict = data.get('backend_server_info_dict')

        # 获取客户端对象
        client = get_object_or_404(ClientInfo, client_ip=client_ip)

        # 使用事务保证数据一致性
        with transaction.atomic():
            # 删除该客户端的所有旧服务器信息（全量同步）
            BackendServerInfo.objects.filter(client=client).delete()

            # 创建新的服务器信息记录
            for backend_server_addr, info in backend_server_info_dict.items():
                BackendServerInfo.objects.create(
                    client=client,
                    backend_server_addr=backend_server_addr,
                    file_path=info.get('file_path', ''),
                    upstream=info.get('upstream', ''),
                    status=info.get('status', 'up')  # 默认状态为运行中
                )

        return Response({'msg': 'Backend server信息同步成功', 'status': 200})

    except Exception as e:
        return Response({'msg': str(e), 'status': 400}, status=400)


@api_view(['POST'])
def create_nginx_config(request):
    """
    创建新的Nginx配置文件
    API端点: POST /api/configs/create/

    功能: 在指定客户端创建新的配置文件

    参数:
        request: 包含创建配置信息的POST请求
        - client_ip: 客户端IP地址
        - file_path: 文件路径

    返回:
        Response: 创建操作的结果
    """
    # 使用序列化器验证请求数据
    serializer = NginxConfigCreateSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        client_ip = data['client_ip']
        file_path = data['file_path']

        # 获取客户端端口号
        client_port = get_client_port(client_ip)
        # 构建目标客户端的API URL
        url = f'http://{client_ip}:{client_port}/nginx_conf/create'

        try:
            # 转发创建请求到具体客户端
            response = requests.post(url, json={'file_path': file_path})
            return Response(response.json())
        except Exception as e:
            return Response({'msg': str(e), 'status': 400}, status=400)

    # 如果数据验证失败，返回错误信息
    return Response(serializer.errors, status=400)


@api_view(['POST'])
def update_nginx_config(request):
    """
    更新Nginx配置文件内容
    API端点: POST /api/configs/update/

    功能: 更新指定客户端的配置文件内容

    参数:
        request: 包含更新配置信息的POST请求
        - client_ip: 客户端IP地址
        - file_path: 文件路径
        - file_content: 文件内容

    返回:
        Response: 更新操作的结果
    """
    # 验证请求数据
    serializer = NginxConfigUpdateSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        client_ip = data['client_ip']
        file_path = data['file_path']
        file_content = data['file_content']

        # 获取客户端端口并构建目标URL
        client_port = get_client_port(client_ip)
        url = f'http://{client_ip}:{client_port}/nginx_conf/update'

        try:
            # 转发更新请求到客户端
            response = requests.post(url, json={
                'file_path': file_path,
                'file_content': file_content
            })
            return Response(response.json())
        except Exception as e:
            return Response({'msg': str(e), 'status': 400}, status=400)

    return Response(serializer.errors, status=400)


@api_view(['GET'])
def read_nginx_config(request):
    """
    读取单个Nginx配置文件内容
    API端点: GET /api/configs/read/

    功能: 从数据库读取指定配置文件的详细内容

    参数:
        request: GET请求，包含查询参数
        - client_ip: 客户端IP地址（查询参数）
        - file_path: 文件路径（查询参数）

    返回:
        Response: 文件内容或错误信息
    """
    # 从URL查询参数中获取客户端IP和文件路径
    client_ip = request.GET.get('client_ip')
    file_path = request.GET.get('file_path')

    try:
        # 查询指定的配置文件
        config_file = NginxConfigFile.objects.get(
            client__client_ip=client_ip,  # 通过外键关系查询
            file_path=file_path
        )
        return Response({
            'msg': config_file.file_content,
            'status': 200
        })
    except NginxConfigFile.DoesNotExist:
        # 文件不存在时返回404错误
        return Response({'msg': '配置文件不存在', 'status': 404}, status=404)


@api_view(['GET'])
def read_all_nginx_configs(request):
    """
    读取客户端所有Nginx配置文件列表
    API端点: GET /api/configs/readAll/

    功能: 获取指定客户端的所有配置文件信息（不包含文件内容）

    参数:
        request: GET请求，包含查询参数
        - client_ip: 客户端IP地址（查询参数）

    返回:
        Response: 配置文件列表的序列化数据
    """
    # 获取客户端IP查询参数
    client_ip = request.GET.get('client_ip')
    # 过滤该客户端的所有配置文件
    configs = NginxConfigFile.objects.filter(client__client_ip=client_ip)
    # 序列化配置列表
    serializer = NginxConfigFileSerializer(configs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def read_all_backend_servers(request):
    """
    读取客户端所有后端服务器信息
    API端点: GET /api/servers/

    功能: 获取指定客户端的所有后端服务器详细信息

    参数:
        request: GET请求，包含查询参数
        - client_ip: 客户端IP地址（查询参数）

    返回:
        Response: 后端服务器列表的序列化数据
    """
    client_ip = request.GET.get('client_ip')
    # 过滤该客户端的后端服务器
    servers = BackendServerInfo.objects.filter(client__client_ip=client_ip)
    serializer = BackendServerInfoSerializer(servers, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def update_backend_server_status(request):
    """
    更新后端服务器状态
    API端点: POST /api/servers/status/

    功能: 修改指定后端服务器的运行状态（如up/down）

    参数:
        request: POST请求，包含更新信息
        - client_ip: 客户端IP地址
        - file_path: 配置文件路径
        - backend_server_addr: 后端服务器地址
        - status: 目标状态

    返回:
        Response: 状态更新操作的结果
    """
    # 验证请求数据
    serializer = BackendServerStatusSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        client_ip = data['client_ip']
        file_path = data['file_path']
        backend_server_addr = data['backend_server_addr']
        status = data['status']

        # 获取客户端端口并构建目标URL
        client_port = get_client_port(client_ip)
        url = f'http://{client_ip}:{client_port}/backend_server/status/update'

        try:
            # 转发状态更新请求到客户端
            response = requests.post(url, json={
                'file_path': file_path,
                'backend_server_addr': backend_server_addr,
                'status': status
            })
            return Response(response.json())
        except Exception as e:
            return Response({'msg': str(e), 'status': 400}, status=400)

    return Response(serializer.errors, status=400)