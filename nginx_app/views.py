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
from client_app.models import ClientInfo
from client_app.client import NginxParamikoClient
from .models import ClientInfo, NginxConfigFile, BackendServerInfo
from .serializers import (
    NginxConfigFileSerializer, BackendServerInfoSerializer,
    NginxConfigCreateSerializer, NginxConfigUpdateSerializer, BackendServerStatusSerializer
)
from .utils import get_client_port


def connect_to_client(client_ip):
    """
    连接函数 - 封装客户端连接逻辑

    参数:
        client_ip: 客户端IP地址

    返回:
        tuple: (client对象, server对象, error_response)
               如果连接成功返回 (client, server, None)
               如果连接失败返回 (None, None, error_response)
    """
    try:
        if not client_ip:
            return None, None, Response({'msg': 'client_ip为必填参数', 'status': 400}, status=400)

        # 从数据库获取服务器信息
        try:
            server = ClientInfo.objects.get(host=client_ip)
        except ClientInfo.DoesNotExist:
            return None, None, Response({'msg': f'未找到IP为{client_ip}的服务器配置', 'status': 404}, status=404)

        # 创建Paramiko客户端
        client = NginxParamikoClient(
            host=server.host,
            port=server.port,
            username=server.username,
            password=server.password
        )
        print('获取到客户端ip', client.host)

        # 尝试建立SSH连接
        if client.connect():
            print(f'成功连接到客户端 {client_ip}')
            return client, server, None  # 成功时返回client, server, None
        else:
            print(f'连接客户端 {client_ip} 失败')
            return None, None, Response({'msg': f'无法建立SSH连接到客户端 {client_ip}', 'status': 400}, status=400)

    except Exception as e:
        print(f'连接客户端 {client_ip} 时发生异常: {str(e)}')
        return None, None, Response({'msg': f'连接失败: {str(e)}', 'status': 400}, status=400)

@api_view(['POST'])
def test_connect(request):
    """
    网络连接测试API端点
    """
    # print('request',request.data)
    try:
        host = request.data.get('serverip')
        username = request.data.get('username')
        password = request.data.get('password')
        port = request.data.get('port', 22)  # 默认端口22
        key_file = request.data.get('key_file')  # 密钥文件路径
        key_content = request.data.get('key_content')  # 密钥内容
        # 验证必填参数
        if not host:
            return Response({
                'msg': 'serverIp为必填参数',
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
        # 测试连接
        if client.connect():
            # 使用正确的execute_command方法，而不是exec_command
            result = client.execute_command('echo "连接测试成功"')

            if result['success']:
                output = result['output'].strip()
                print('执行结果:', result)
                client.close()

                response = Response({
                    'msg': f'连接成功: {host} - {output}',
                    'status': 200,
                    'auth_type': 'key' if key_file or key_content else 'password'
                }, status=200)
            else:
                response = Response({
                    'msg': f'命令执行失败: {result["error"]}',
                    'status': 400
                }, status=400)
        else:
            response = Response({
                'msg': f'连接失败: 无法建立SSH连接',
                'status': 400
            }, status=400)
        return response

    except Exception as e:
        response = Response({
            'msg': f'连接失败: {str(e)}',
            'status': 400
        }, status=400)
        return response


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
    # 获取请求数据
    client_ip = request.data.get('client_ip')
    file_path = request.data.get('file_path')
    print('file_path',file_path)
    file_content = request.data.get('file_content', f'#{file_path}')  # 默认内容

    if not client_ip or not file_path:
        return Response({'msg': 'client_ip和file_path为必填参数', 'status': 400}, status=400)

    # 正确接收connect_to_client的返回值
    client, server = connect_to_client(client_ip)
    # 建立ssh连接
    if not client.connect():
        return Response({'msg': f'无法连接到服务器{client_ip}', 'status': 400}, status=400)

    try:
        # 检查文件是否存在
        check_result = client.execute_command(f'test -f {file_path}')
        if check_result['success'] and 'exists' in check_result['output']:
            return Response({'msg': f'{file_path}此文件已存在', 'status': 201}, status=201)

        # 检查目录存在，不存在则创建
        dir_path = '/'.join(file_path.split('/')[:-1])
        if dir_path:
            mkdir_result = client.execute_command(f'mkdir -p {dir_path}')
            if not mkdir_result['success']:
                return Response({'msg': f'创建目录失败: {mkdir_result["error"]}', 'status': 201}, status=201)

        # 写入配置文件
        write_result = client.write_config_file(file_path, file_content)
        if write_result['success']:
            # 检查Nginx配置语法
            check_config_result = client.check_nginx_config()
            if check_config_result['success']:
                # 重载Nginx配置
                reload_result = client.reload_nginx()
                if reload_result['success']:
                    return Response({
                        'msg': f'{file_path},此文件创建成功，nginx重载成功',
                        'status': 200
                    })
                else:
                    return Response({
                        'msg': f'文件创建成功但Nginx重载失败: {reload_result["error"]}',
                        'status': 201
                    })
            else:
                # 配置检查失败，删除创建的文件
                client.execute_command(f'rm -f {file_path}')
                return Response({
                    'msg': f'Nginx配置检查失败: {check_config_result["error"]}，已删除创建的文件',
                    'status': 201
                })
        else:
            return Response({
                'msg': f'文件创建失败: {write_result["error"]}',
                'status': 201
            })

    except Exception as e:
        return Response({'msg': str(e), 'status': 400}, status=400)
    finally:
        client.close()
@api_view(['GET'])
def read_nginx_config(request):
    """
    读取Nginx配置文件内容
    API端点: GET /api/nginx/config/read/

    功能: 读取指定客户端的Nginx配置文件内容

    参数:
        request: 包含读取配置信息的GET请求
        - client_ip: 客户端IP地址
        - file_path: 配置文件路径（必填）

    返回:
        Response: 配置文件内容
    """

    try:
        # 获取请求
        client_ip = request.GET.get('client_ip')
        file_path = request.GET.get('file_path')

        if not client_ip:
            return Response({'msg': 'client_ip为必填参数', 'status': 400}, status=400)
        if not file_path:
            return Response({'msg': 'file_path为必填参数', 'status': 400}, status=400)

        client, server, error_response = connect_to_client(client_ip)

        if error_response:
            return error_response

        # 建立连接
        if not client.connect():
            return Response({'msg': f'无法连接到服务器{client_ip}', 'status': 400}, status=400)

        try:
            # 读取配置文件
            read_result = client.read_config_file(file_path)

            if read_result['success']:
                # 成功读取文件
                config_content = read_result['output']
                file_size = len(config_content.encode('utf-8')) if config_content else 0

                return Response({
                    'msg': '配置文件读取成功',
                    'status': 200,
                    'result': {
                        'file_path': file_path,
                        'content': config_content,
                        'file_size': file_size,
                        'lines_count': len(config_content.split('\n')) if config_content else 0,
                        'success': True,
                        'output': read_result.get('output', ''),
                        'error': read_result.get('error', ''),
                        'return_code': read_result.get('return_code', -1)
                    }
                })
            else:
                # 读取文件失败
                error_details = {
                    'output': read_result.get('output', ''),
                    'error': read_result.get('error', ''),
                    'return_code': read_result.get('return_code', -1)
                }

                # 分析错误类型
                error_text = read_result.get('error', '') + read_result.get('output', '')
                if 'No such file or directory' in error_text:
                    error_type = '文件不存在'
                elif 'Permission denied' in error_text:
                    error_type = '权限不足'
                elif 'Is a directory' in error_text:
                    error_type = '路径是目录'
                else:
                    error_type = '读取失败'

                return Response({
                    'msg': f'配置文件读取失败 - {error_type}',
                    'status': 201,
                    'result': {
                        'file_path': file_path,
                        'content': '',
                        'file_size': 0,
                        'lines_count': 0,
                        'success': False,
                        'error_type': error_type,
                        **error_details
                    }
                })

        finally:
            client.close()
    except Exception as e:
        return Response({'msg': str(e), 'status': 400}, status=400)


@api_view(['GET'])
def read_all_nginx_configs(request):
    """
    列出Nginx配置目录下的所有配置文件
    API端点: GET /api/nginx/config/list/

    功能: 列出指定客户端Nginx配置目录下的所有.conf文件

    参数:
        request: 包含列表查询信息的GET请求
        - client_ip: 客户端IP地址
        - config_dir: 配置目录路径（可选，默认为/etc/nginx/conf.d/）

    返回:
        Response: 配置文件列表
    """

    try:
        # 获取请求
        client_ip = request.GET.get('client_ip')
        config_dir = request.GET.get('config_dir', '/etc/nginx/')

        if not client_ip:
            return Response({'msg': 'client_ip为必填参数', 'code': 400}, status=400)

        client, server, error_response = connect_to_client(client_ip)

        if error_response:
            return error_response

        # 建立连接
        if not client.connect():
            return Response({'msg': f'无法连接到服务器{client_ip}', 'code': 400}, status=400)

        try:
            # 获取配置文件列表
            files_result = client.get_nginx_config_files(config_dir)

            return Response({
                'msg': '配置文件列表获取成功',
                'status': 200,
                'result': {
                    'config_dir': config_dir,
                    'files': files_result,
                    'files_count': len(files_result),
                    'success': True
                }
            })

        except Exception as e:
            return Response({
                'msg': f'获取配置文件列表失败: {str(e)}',
                'status': 201,
                'result': {
                    'config_dir': config_dir,
                    'files': [],
                    'files_count': 0,
                    'success': False,
                    'error': str(e)
                }
            })
        finally:
            client.close()
    except Exception as e:
        return Response({'msg': str(e), 'status': 400}, status=400)
@api_view(['POST'])
def check_nginx_config(request):
    """
    检查Nginx配置语法
    API端点: POST /api/nginx/check-config/

    功能: 在指定客户端检查Nginx配置语法

    参数:
        request: 包含检查配置信息的POST请求
        - client_ip: 客户端IP地址
        - nginx_path: Nginx配置文件路径（可选，默认为/etc/nginx/nginx.conf）

    返回:
        Response: 配置检查结果
    """

    try:
        #获取请求
        client_ip = request.GET.get('client_ip')
        nginx_path = request.GET.get('nginx_path', '/etc/nginx/nginx.conf')
        if not client_ip:
            return Response({'msg': 'client_ip为必填参数', 'status': 400}, status=400)

        client = connect_to_client(client_ip)
        #建立连接
        if not client.connect():
            return Response({'msg': f'无法连接到服务器{client_ip}', 'status': 400}, status=400)
        try:
            #检查配置
            check_result = client.check_nginx_config(nginx_path)
            if check_result['success']:
                #是否包含成功信息
                output_text = check_result['output']
                if 'syntax is ok' in output_text and 'test is successful' in output_text:
                    status_msg = '配置语法正确'
                    status_code = 200
                else:
                    status_msg = '配置检查完成但结果异常'
                    status_code = 201
                return Response({
                    'msg': status_msg,
                    'status': status_code,
                    'result': {
                        'output': output_text,
                        'success':True,
                        'syntax_ok': 'syntax is ok' in output_text,
                        'test_successful': 'test is successful' in output_text
                    }
                })
            else:
                # 配置检查失败
                error_details = {
                    'output': check_result.get('output', ''),
                    'error': check_result.get('error', ''),
                    'return_code': check_result.get('return_code', -1)
                }
                #分析错误
                error_output = check_result.get('output', '') + check_result.get('error', '')
                if '[emerg]' in error_output:
                    error_type ='紧急错误'
                elif '[warn]' in error_output:
                    error_type = '警告'
                else:
                    error_type = '语法错误'
                return Response({
                    'msg': f'Nginx配置检查失败 - {error_type}',
                    'status': 201,
                    'result': {
                        **error_details,
                        'error_type': error_type,
                        'success': False
                    }
                })
        finally:
            client.close()
    except Exception as e:
        return Response({'msg': str(e), 'status': 400}, status=400)


@api_view(['POST'])
def check_and_reload_nginx(request):
    """
    检查并重启Nginx配置
    API端点: POST /api/nginx/check-and-reload/

    功能: 先检查Nginx配置语法，如果检查通过则重启Nginx服务

    参数:
        request: 包含检查配置信息的POST请求
        - client_ip: 客户端IP地址
        - nginx_path: Nginx配置文件路径（可选，默认为/etc/nginx/nginx.conf）

    返回:
        Response: 检查并重启操作结果
    """

    try:
        # 获取请求
        client_ip = request.data.get('client_ip')
        nginx_path = request.data.get('nginx_path', '/etc/nginx/nginx.conf')
        if not client_ip:
            return Response({'msg': 'client_ip为必填参数', 'status': 400}, status=400)

        client, error_response = connect_to_client(client_ip)
        if error_response:
            return error_response

        # 建立连接
        if not client.connect():
            return Response({'msg': f'无法连接到服务器{client_ip}', 'status': 400}, status=400)

        try:
            # 第一步：检查配置
            check_result = client.check_nginx_config(nginx_path)

            if not check_result['success']:
                # 配置检查失败，直接返回错误
                error_details = {
                    'output': check_result.get('output', ''),
                    'error': check_result.get('error', ''),
                    'return_code': check_result.get('return_code', -1)
                }
                # 分析错误
                error_output = check_result.get('output', '') + check_result.get('error', '')
                if '[emerg]' in error_output:
                    error_type = '紧急错误'
                elif '[warn]' in error_output:
                    error_type = '警告'
                else:
                    error_type = '语法错误'

                return Response({
                    'msg': f'Nginx配置检查失败，无法重启 - {error_type}',
                    'status': 201,
                    'result': {
                        'check_result': {
                            **error_details,
                            'error_type': error_type,
                            'success': False
                        },
                        'reload_result': None,
                        'overall_success': False
                    }
                })

            # 第二步：重启Nginx
            reload_result = client.reload_nginx()

            # 构建返回结果
            check_output_text = check_result['output']
            check_success = check_result['success']
            check_syntax_ok = 'syntax is ok' in check_output_text
            check_test_successful = 'test is successful' in check_output_text

            if reload_result['success']:
                return Response({
                    'msg': 'Nginx配置检查通过并重启成功',
                    'status': 200,
                    'result': {
                        'check_result': {
                            'output': check_output_text,
                            'success': check_success,
                            'syntax_ok': check_syntax_ok,
                            'test_successful': check_test_successful
                        },
                        'reload_result': {
                            'output': reload_result.get('output', ''),
                            'error': reload_result.get('error', ''),
                            'return_code': reload_result.get('return_code', -1),
                            'success': reload_result['success']
                        },
                        'overall_success': True
                    }
                })
            else:
                return Response({
                    'msg': 'Nginx配置检查通过但重启失败',
                    'status': 201,
                    'result': {
                        'check_result': {
                            'output': check_output_text,
                            'success': check_success,
                            'syntax_ok': check_syntax_ok,
                            'test_successful': check_test_successful
                        },
                        'reload_result': {
                            'output': reload_result.get('output', ''),
                            'error': reload_result.get('error', ''),
                            'return_code': reload_result.get('return_code', -1),
                            'success': reload_result['success']
                        },
                        'overall_success': False
                    }
                })

        finally:
            client.close()
    except Exception as e:
        return Response({'msg': str(e), 'status': 400}, status=400)

@api_view(['POST'])
def update_nginx_config(request):
    """
    更新Nginx配置文件内容
    API端点: POST /api/configs/update/

    功能: 更新指定客户端的配置文件内容，使用SCP方式替换服务端文件

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

        # 连接客户端
        client, server, error_response = connect_to_client(client_ip)


        # 建立SSH连接
        if not client.connect():
            return Response({'msg': f'无法连接到服务器{client_ip}', 'status': 400}, status=400)

        try:
            # 检查文件是否存在
            check_result = client.execute_command(f'test -f {file_path}')
            if not check_result['success'] or 'not exists' in check_result['output']:
                return Response({'msg': f'文件不存在: {file_path}', 'status': 404}, status=404)

            # 备份原文件
            backup_path = f"{file_path}.backup"
            backup_result = client.execute_command(f'cp {file_path} {backup_path}')
            if not backup_result['success']:
                return Response({'msg': f'文件备份失败: {backup_result["error"]}', 'status': 400}, status=400)

            # 使用SCP方式上传配置内容
            upload_result = client.upload_config_content(file_content, file_path)
            if not upload_result['success']:
                # 上传失败，恢复备份
                client.execute_command(f'cp {backup_path} {file_path}')
                return Response({'msg': upload_result['error'], 'status': 400}, status=400)

            # 检查Nginx配置语法
            check_config_result = client.check_nginx_config()
            if check_config_result['success']:
                # 重载Nginx配置
                reload_result = client.reload_nginx()
                if reload_result['success']:
                    # 删除备份文件
                    client.execute_command(f'rm -f {backup_path}')
                    return Response({
                        'msg': f'配置文件更新成功，Nginx重载成功',
                        'status': 200
                    })
                else:
                    # 重载失败，恢复备份
                    client.execute_command(f'cp {backup_path} {file_path}')
                    return Response({
                        'msg': f'配置文件更新成功但Nginx重载失败: {reload_result["error"]}，已恢复原文件',
                        'status': 201
                    })
            else:
                # 配置检查失败，恢复备份
                client.execute_command(f'cp {backup_path} {file_path}')
                return Response({
                    'msg': f'Nginx配置检查失败: {check_config_result["error"]}，已恢复原文件',
                    'status': 400
                })

        except Exception as e:
            return Response({'msg': str(e), 'status': 400}, status=400)
        finally:
            client.close()

    return Response(serializer.errors, status=400)

@api_view(['GET'])
def get_nginx_status(request):
    """
    获取Nginx状态
    API端点: GET /api/nginx/status/

    功能: 获取指定客户端的Nginx服务状态

    参数:
        request: 包含状态查询信息的GET请求
        - client_ip: 客户端IP地址

    返回:
        Response: Nginx状态信息
    """

    try:
        # 获取请求
        client_ip = request.GET.get('client_ip')
        if not client_ip:
            return Response({'msg': 'client_ip为必填参数', 'status': 400}, status=400)

        client, server, error_response = connect_to_client(client_ip)
        if error_response:
            return error_response

        # 建立连接
        if not client.connect():
            return Response({'msg': f'无法连接到服务器{client_ip}', 'status': 400}, status=400)

        try:
            # 获取Nginx状态
            status_result = client.get_nginx_status()

            # 分析状态结果
            output_text = status_result.get('output', '')
            error_text = status_result.get('error', '')
            return_code = status_result.get('return_code', -1)

            # 判断Nginx状态
            is_running = False
            status_type = 'unknown'

            if return_code == 0:
                # systemctl status nginx 成功
                if 'active (running)' in output_text.lower():
                    is_running = True
                    status_type = 'systemd_running'
                elif 'active (exited)' in output_text.lower():
                    is_running = False
                    status_type = 'systemd_exited'
                else:
                    # 检查进程信息
                    if 'nginx' in output_text.lower():
                        is_running = True
                        status_type = 'process_running'
            else:
                # systemctl失败，检查进程
                if 'nginx' in output_text.lower() or 'nginx' in error_text.lower():
                    is_running = True
                    status_type = 'process_detected'

            if is_running:
                return Response({
                    'msg': 'Nginx服务正在运行',
                    'status': 200,
                    'result': {
                        'output': output_text,
                        'error': error_text,
                        'return_code': return_code,
                        'is_running': True,
                        'status_type': status_type,
                        'success': status_result['success']
                    }
                })
            else:
                return Response({
                    'msg': 'Nginx服务未运行',
                    'status': 201,
                    'result': {
                        'output': output_text,
                        'error': error_text,
                        'return_code': return_code,
                        'is_running': False,
                        'status_type': status_type,
                        'success': status_result['success']
                    }
                })

        finally:
            client.close()
    except Exception as e:
        return Response({'msg': str(e), 'status': 400}, status=400)


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

    # 验证必需参数
    if not client_ip:
        return Response({'msg': 'client_ip参数不能为空', 'status': 400}, status=400)

    try:
        # 首先尝试从数据库查询后端服务器信息
        servers = BackendServerInfo.objects.filter(client__client_ip=client_ip)

        # 如果数据库中有数据，直接返回
        if servers.exists():
            serializer = BackendServerInfoSerializer(servers, many=True)
            return Response({
                'msg': '从数据库获取后端服务器信息成功',
                'data': serializer.data,
                'source': 'database',
                'status': 200
            })

        # 如果数据库中没有数据，尝试从客户端服务器获取配置
        # 连接到客户端
        client, server, error_response = connect_to_client(client_ip)

        if error_response:
            return Response({
                'msg': f'连接客户端失败: {error_response.data.get("msg", "未知错误")}',
                'data': [],
                'source': 'none',
                'status': 400
            })

        # 检查client对象是否为None
        if not client or not server:
            return Response({
                'msg': '连接客户端失败: 无法获取客户端连接对象',
                'data': [],
                'source': 'none',
                'status': 400
            })

        # 建立SSH连接
        if not client.connect():
            return Response({
                'msg': f'无法连接到服务器{client_ip}',
                'data': [],
                'source': 'none',
                'status': 400
            })

        try:
            # 获取Nginx配置分析结果
            config_analysis_result = client.get_nginx_config_analysis()
            print('配置文件返回值',config_analysis_result)

            # 从配置分析结果中提取upstream信息
            upstreams_info = config_analysis_result.get('upstreams_info', {})
            backend_servers_list = []

            # 遍历所有upstream配置
            for upstream_name, upstream_info in upstreams_info.items():
                file_path = upstream_info.get('file_path', '')
                backend_servers = upstream_info.get('backend_servers', [])

                # 处理每个后端服务器
                for server_args in backend_servers:
                    # 解析服务器地址和参数
                    backend_server_addr = server_args[0] if server_args else ''

                    # 解析状态参数
                    status = 'up'  # 默认状态
                    weight = 1  # 默认权重

                    for arg in server_args[1:]:
                        if arg in ['up', 'down', 'backup']:
                            status = arg
                        elif arg.startswith('weight='):
                            try:
                                weight = int(arg.split('=')[1])
                            except (ValueError, IndexError):
                                pass

                    # 创建后端服务器信息对象
                    backend_server_info = {
                        'client': server.id,  # 使用ClientInfo对象的ID
                        'backend_server_addr': backend_server_addr,
                        'file_path': file_path,
                        'upstream': upstream_name,
                        'status': status,
                        'weight': weight
                    }

                    backend_servers_list.append(backend_server_info)

            # 如果没有找到后端服务器信息
            if not backend_servers_list:
                return Response({
                    'msg': '未在Nginx配置中找到后端服务器信息',
                    'data': [],
                    'source': 'nginx_config',
                    'status': 200
                })

            # 将获取到的后端服务器信息保存到数据库
            saved_servers = []
            for server_info in backend_servers_list:
                # 检查是否已存在相同记录
                existing_server = BackendServerInfo.objects.filter(
                    client=server_info['client'],
                    backend_server_addr=server_info['backend_server_addr']
                ).first()

                if not existing_server:
                    # 创建新的后端服务器记录
                    backend_server = BackendServerInfo.objects.create(
                        client_id=server_info['client'],
                        backend_server_addr=server_info['backend_server_addr'],
                        file_path=server_info['file_path'],
                        upstream=server_info['upstream'],
                        status=server_info['status'],
                        weight=server_info['weight']
                    )
                    saved_servers.append(backend_server)
                else:
                    saved_servers.append(existing_server)

            # 序列化并返回结果
            serializer = BackendServerInfoSerializer(saved_servers, many=True)
            return Response({
                'msg': '从Nginx配置获取后端服务器信息成功，并已保存到数据库',
                'data': serializer.data,
                'source': 'nginx_config_and_saved',
                'status': 200
            })

        except Exception as e:
            return Response({
                'msg': f'从客户端获取配置时发生错误: {str(e)}',
                'data': [],
                'source': 'none',
                'status': 500
            })

        finally:
            if client:
                client.close()

    except Exception as e:
        return Response({
            'msg': f'获取后端服务器信息时发生错误: {str(e)}',
            'data': [],
            'source': 'none',
            'status': 500
        })

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


@api_view(['GET'])
def read_upstream_info(request):
    """
    读取给定upstream信息，支持模糊查找
    API端点: GET /api/servers/upstream/

    功能: 根据客户端IP和upstream名称模糊查询后端服务器信息

    参数:
        request: GET请求，包含查询参数
        - client_ip: 客户端IP地址（必需）
        - upstream: upstream名称，支持模糊匹配（必需）

    返回:
        Response: 匹配的后端服务器信息列表
    """
    # 从查询参数中获取客户端IP和upstream名称
    client_ip = request.GET.get('client_ip')
    upstream = request.GET.get('upstream')

    # 验证必需参数
    if not client_ip:
        return Response({'msg': 'client_ip参数不能为空', 'status': 400}, status=400)

    if not upstream:
        return Response({'msg': 'upstream参数不能为空', 'status': 400}, status=400)

    try:
        # 查询指定客户端的所有后端服务器
        servers = BackendServerInfo.objects.filter(
            client__client_ip=client_ip,
            upstream__icontains=upstream  # 使用icontains进行不区分大小写的模糊匹配
        )

        # 构建返回数据
        upstream_info_list = []
        for server in servers:
            server_info = {
                'backend_server_addr': server.backend_server_addr,
                'file_path': server.file_path,
                'upstream': server.upstream,
                'status': server.status
            }
            upstream_info_list.append(server_info)

        return Response({
            'msg': '查询成功',
            'data': upstream_info_list,
            'status': 200
        })

    except Exception as e:
        return Response({'msg': f'查询失败: {str(e)}', 'status': 500}, status=500)


@api_view(['GET'])
def search_backend_servers(request):
    """
    高级搜索后端服务器信息
    API端点: GET /api/servers/search/

    功能: 支持多条件组合搜索后端服务器

    参数:
        request: GET请求，包含查询参数
        - client_ip: 客户端IP地址（可选）
        - upstream: upstream名称，支持模糊匹配（可选）
        - status: 服务器状态（可选）
        - backend_server_addr: 服务器地址，支持模糊匹配（可选）

    返回:
        Response: 匹配的后端服务器信息列表
    """
    try:
        # 获取查询参数
        client_ip = request.GET.get('client_ip')
        upstream = request.GET.get('upstream')
        status = request.GET.get('status')
        backend_server_addr = request.GET.get('backend_server_addr')

        # 构建查询条件
        query_filters = {}

        if client_ip:
            query_filters['client__client_ip'] = client_ip

        if upstream:
            query_filters['upstream__icontains'] = upstream

        if status:
            query_filters['status'] = status

        if backend_server_addr:
            query_filters['backend_server_addr__icontains'] = backend_server_addr

        # 执行查询
        servers = BackendServerInfo.objects.filter(**query_filters)

        # 序列化结果
        serializer = BackendServerInfoSerializer(servers, many=True)

        return Response({
            'msg': '搜索成功',
            'data': serializer.data,
            'count': servers.count(),
            'status': 200
        })

    except Exception as e:
        return Response({'msg': f'搜索失败: {str(e)}', 'status': 500}, status=500)
