import tempfile

import paramiko
from io import StringIO
import json
import os
import logging
import crossplane
logger = logging.getLogger(__name__)

class NginxAnalyzer:
    def __init__(self, nginx_main_conf_path="/etc/nginx/nginx.conf", nginx_obj_dict=None):
        self.nginx_obj_dict = nginx_obj_dict or {"status": "ok", "errors": [], "config": []}
        self.nginx_conf = self.nginx_obj_dict["config"]
        self.nginx_main_conf_path = nginx_main_conf_path
       # 新增：添加local_config_dir属性
        self.local_config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_nginx_configs')
        os.makedirs(self.local_config_dir, exist_ok=True)
    def get_pid_file_path(self):
        for file in self.nginx_conf:
            file_path = file['file']
            if file_path == self.nginx_main_conf_path:
                file_all_directives_list = file['parsed']
                for file_per_directive_dict in file_all_directives_list:
                    if file_per_directive_dict['directive'] == 'pid':
                        return file_per_directive_dict['args'][0]
        return None

    def get_file_path_list(self):
        file_path_list = []
        for file in self.nginx_conf:
            file_path = file['file']
            file_path_list.append(file_path)
        return file_path_list

    def check_file_path_is_under_main_file_dir(self):
        file_path_list = self.get_file_path_list()
        nginx_main_conf_path_dir = os.path.dirname(self.nginx_main_conf_path)
        for per_file_path in file_path_list:
            if not nginx_main_conf_path_dir in per_file_path:
                raise Exception(f"配置文件不在主配置目录下: {per_file_path}")

    def check_main_conf_file(self):
        '''检测主配置文件是否有server和upstream指令'''
        for file in self.nginx_conf:
            file_path = file['file']
            if file_path == self.nginx_main_conf_path:
                nginx_main_conf_all_directives_dict = file['parsed']  # 取到本文件所有directive配置
                for file_per_directive_dict in nginx_main_conf_all_directives_dict:
                    if file_per_directive_dict["directive"] == "http":
                        for http_per_directive_dict in file_per_directive_dict['block']:
                            if http_per_directive_dict['directive'] == 'server' or \
                                    http_per_directive_dict['directive'] == 'upstream':
                                raise Exception("请把http块下的server块和upstream块的配置移出主配置文件")
                    if file_per_directive_dict["directive"] == "stream":
                        for http_per_directive_dict in file_per_directive_dict['block']:
                            print(http_per_directive_dict)
                            if http_per_directive_dict['directive'] == 'server' or http_per_directive_dict[
                                'directive'] == 'upstream':
                                raise Exception("请把stream块下的server块和upstream块的配置移出主配置文件")

    def get_backend_server_info_dict(self):
        backend_server_info_dict = {}
        for file in self.nginx_conf:
            file_path = file['file']
            if file_path == self.nginx_main_conf_path or 'mime.types' in file_path:
                continue
            file_all_directives_list = file['parsed']
            for file_per_directive_dict in file_all_directives_list:
                if file_per_directive_dict['directive'] == 'upstream':
                    upstream_name = "".join(file_per_directive_dict['args'])
                    upstream_all_directives_list = file_per_directive_dict['block']
                    for upstream_per_directive_dict in upstream_all_directives_list:
                        if upstream_per_directive_dict['directive'] == 'server':
                            backend_server_args_list = upstream_per_directive_dict['args']
                            backend_server_addr = backend_server_args_list[0]
                            backend_server_info_dict[backend_server_addr] = {
                                'file_path': file_path,
                                'upstream': upstream_name,
                                'status': 'down' if 'down' in backend_server_args_list else
                                         'backup' if 'backup' in backend_server_args_list else ''
                            }
        return backend_server_info_dict
    def _manual_parse_nginx_config(self, file_content, file_path):
        """手动解析Nginx配置文件，提取关键配置"""
        import re
        parsed_directives = []

        try:
            # 提取server块
            server_pattern = r'server\s*\{([^}]+)\}'
            server_matches = re.findall(server_pattern, file_content, re.DOTALL)

            for i, server_content in enumerate(server_matches):
                # 创建server指令
                server_directive = {
                    'directive': 'server',
                    'args': [f'server_{i}'],
                    'line': 1,  # 简化处理，使用默认行号
                    'block': []
                }

                # 提取server_name
                server_name_pattern = r'server_name\s+([^;]+);'
                server_name_match = re.search(server_name_pattern, server_content)
                if server_name_match:
                    server_names = server_name_match.group(1).strip().split()
                    server_directive['block'].append({
                        'directive': 'server_name',
                        'args': server_names,
                        'line': 1
                    })

                # 提取listen
                listen_pattern = r'listen\s+([^;]+);'
                listen_match = re.search(listen_pattern, server_content)
                if listen_match:
                    listen_args = listen_match.group(1).strip().split()
                    server_directive['block'].append({
                        'directive': 'listen',
                        'args': listen_args,
                        'line': 1
                    })

                # 提取location块
                location_pattern = r'location\s+([^{]+)\{([^}]+)\}'
                location_matches = re.findall(location_pattern, server_content, re.DOTALL)

                for location_match in location_matches:
                    location_path = location_match[0].strip()
                    location_content = location_match[1]

                    location_directive = {
                        'directive': 'location',
                        'args': [location_path],
                        'line': 1,
                        'block': []
                    }

                    # 提取proxy_pass
                    proxy_pass_pattern = r'proxy_pass\s+([^;]+);'
                    proxy_pass_match = re.search(proxy_pass_pattern, location_content)
                    if proxy_pass_match:
                        proxy_pass_args = [proxy_pass_match.group(1).strip()]
                        location_directive['block'].append({
                            'directive': 'proxy_pass',
                            'args': proxy_pass_args,
                            'line': 1
                        })

                    server_directive['block'].append(location_directive)

                parsed_directives.append(server_directive)

            # 提取upstream块
            upstream_pattern = r'upstream\s+([^{]+)\{([^}]+)\}'
            upstream_matches = re.findall(upstream_pattern, file_content, re.DOTALL)

            for upstream_match in upstream_matches:
                upstream_name = upstream_match[0].strip()
                upstream_content = upstream_match[1]

                upstream_directive = {
                    'directive': 'upstream',
                    'args': [upstream_name],
                    'line': 1,
                    'block': []
                }

                # 提取server指令
                server_pattern = r'server\s+([^;]+);'
                server_matches = re.findall(server_pattern, upstream_content)

                for server_match in server_matches:
                    server_args = server_match.strip().split()
                    upstream_directive['block'].append({
                        'directive': 'server',
                        'args': server_args,
                        'line': 1
                    })

                parsed_directives.append(upstream_directive)

            print(f"手动解析成功，找到 {len(parsed_directives)} 个关键配置块")
            return parsed_directives

        except Exception as e:
            print(f"手动解析失败: {e}")
            return []

    def analysis_nginx_all_conf(self):
        virtual_server_name_list = []
        virtual_servers_info_dict = {}
        upstream_name_list = []
        upstreams_info_dict = {}
        backend_server_ip_port_list = []
        backend_servers_info_dict = {}

        print(f"开始执行analysis_nginx_all_conf，配置文件数量: {len(self.nginx_conf)}")
        print(f"配置文件列表: {[file['file'] for file in self.nginx_conf]}")

        try:
            self.check_main_conf_file()
        except Exception as e:
            # 如果验证失败，记录警告信息但继续执行分析
            print(f"警告: {e}")
            print("配置分析将继续进行，但结果可能不准确")

        processed_files = 0
        valid_files = 0  # 有效配置文件计数

        # 新增：递归处理配置块的辅助函数
        def process_directives(directives, file_path, depth=0):
            """递归处理指令列表，包括嵌套块中的指令"""
            for directive_dict in directives:
                directive = directive_dict.get('directive', '')
                args = directive_dict.get('args', [])
                block = directive_dict.get('block', [])

                # 根据深度缩进显示
                indent = "  " * depth
                print(f"{indent}处理指令: {directive}, 深度: {depth}")

                if directive == 'upstream':
                    upstream_name = "".join(args)
                    print(f"{indent}找到upstream: {upstream_name}")
                    if upstream_name not in upstream_name_list:
                        upstream_name_list.append(upstream_name)
                    else:
                        print(f"{indent}警告: upstream命名重复: {upstream_name}，跳过重复项")
                        continue

                    upstreams_info_dict[upstream_name] = {
                        'file_path': file_path,
                        'backend_servers': []
                    }

                    # 处理upstream块中的server指令
                    for upstream_per_directive_dict in block:
                        if upstream_per_directive_dict['directive'] == 'server':
                            backend_server_args_list = upstream_per_directive_dict['args']
                            upstreams_info_dict[upstream_name]['backend_servers'].append(backend_server_args_list)
                            backend_server_ip_port = backend_server_args_list[0]
                            backend_server_ip_port_list.append(backend_server_ip_port)
                            backend_servers_info_dict[backend_server_ip_port] = {
                                'file_path': file_path,
                                'upstream': upstream_name,
                                'args': backend_server_args_list[1:]
                            }
                            print(f"{indent}找到后端服务器: {backend_server_ip_port}")

                elif directive == 'server':
                    server_name = ""
                    # 先查找server_name指令
                    for server_per_directive_dict in block:
                        if server_per_directive_dict['directive'] == "server_name":
                            server_name_args = server_per_directive_dict['args']
                            server_name = ",".join(server_name_args)
                            if server_name not in virtual_server_name_list:
                                virtual_server_name_list.append(server_name)
                                virtual_servers_info_dict[server_name] = {
                                    'filepath': file_path,
                                    'location_proxy': {},
                                    'proxy_pass': []
                                }
                            print(f"{indent}找到虚拟主机: {server_name}")
                            break

                    # 如果没有找到server_name，使用默认名称
                    if not server_name:
                        server_name = f"server_{len(virtual_server_name_list)}"
                        if server_name not in virtual_server_name_list:
                            virtual_server_name_list.append(server_name)
                            virtual_servers_info_dict[server_name] = {
                                'filepath': file_path,
                                'location_proxy': {},
                                'proxy_pass': []
                            }
                        print(f"{indent}找到未命名虚拟主机，使用默认名称: {server_name}")

                    # 处理server块中的location指令
                    for server_per_directive_dict in block:
                        if server_per_directive_dict['directive'] == "location":
                            location_arg = "".join(server_per_directive_dict['args'])
                            location_block = server_per_directive_dict.get('block', [])
                            for location_per_directive_dict in location_block:
                                if location_per_directive_dict["directive"] == "proxy_pass":
                                    proxy_pass_args = location_per_directive_dict["args"]
                                    if proxy_pass_args:
                                        proxy_pass = "".join(proxy_pass_args)
                                        # 处理proxy_pass格式
                                        if '//' in proxy_pass:
                                            proxy_pass = proxy_pass.split('//')[1]
                                        virtual_servers_info_dict[server_name]['proxy_pass'].append(proxy_pass)
                                        virtual_servers_info_dict[server_name]['location_proxy'][
                                            location_arg] = proxy_pass
                                        print(f"{indent}找到proxy_pass: {proxy_pass}")

                # 递归处理嵌套块中的指令（如http块中的server块）
                if block:
                    print(f"{indent}发现嵌套块，指令: {directive}, 深度: {depth}")
                    process_directives(block, file_path, depth + 1)

        for file in self.nginx_conf:
            file_path = file['file']
            file_status = file.get('status', 'unknown')

            # 关键修改：不再跳过主配置文件，只跳过mime.types文件
            if 'mime.types' in file_path:
                print(f"跳过mime.types文件: {file_path}")
                continue

            # 关键修改：改进错误处理逻辑
            has_valid_directives = False
            parsed_directives = file.get('parsed', [])

            # 修复：简化解析逻辑，避免重复解析
            if file_status in ['error', 'exception', 'manual', 'failed']:
                print(f"文件 {file_path} 状态为 {file_status}，尝试检查是否包含有效内容")

                # 检查本地文件是否存在且包含有效内容
                local_file_path = os.path.join(self.local_config_dir, os.path.basename(file_path))
                if os.path.exists(local_file_path):
                    try:
                        with open(local_file_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()

                        # 检查文件内容是否包含server或upstream配置
                        if 'server {' in file_content or 'upstream ' in file_content:
                            print(f"文件 {file_path} 包含有效配置，尝试重新解析")
                            try:
                                # 尝试重新解析
                                parsed_config = crossplane.parse(local_file_path, catch_errors=True, combine=True)
                                if parsed_config.get('status') == 'ok' and parsed_config.get('config'):
                                    # 更新解析结果
                                    file['parsed'] = parsed_config['config'][0].get('parsed', [])
                                    file['status'] = 'ok'
                                    print(f"文件 {file_path} 重新解析成功")
                                else:
                                    # 如果crossplane解析失败，尝试手动解析关键配置
                                    print(f"crossplane解析失败，尝试手动解析关键配置")
                                    manual_parsed = self._manual_parse_nginx_config(file_content, file_path)
                                    if manual_parsed:
                                        file['parsed'] = manual_parsed
                                        file['status'] = 'manual_ok'
                                        print(f"文件 {file_path} 手动解析成功")
                            except Exception as e:
                                print(f"文件 {file_path} 重新解析失败: {e}")
                    except Exception as e:
                        print(f"读取本地文件 {local_file_path} 失败: {e}")
                else:
                    print(f"本地文件不存在: {local_file_path}，无法进行手动解析")

            # 修复：简化测试逻辑，避免重复解析
            # 只在文件状态仍然是failed且没有进行过手动解析时才进行测试
            if file_path == '/etc/nginx/conf.d/test.conf' and file_status == 'failed':
                print(f"测试手动解析功能，强制对文件 {file_path} 进行手动解析")
                local_file_path = os.path.join(self.local_config_dir, os.path.basename(file_path))
                if os.path.exists(local_file_path):
                    try:
                        with open(local_file_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()

                        # 调用手动解析方法
                        manual_parsed = self._manual_parse_nginx_config(file_content, file_path)
                        if manual_parsed:
                            print(
                                f"手动解析成功，原指令数量: {len(parsed_directives)}，手动解析后指令数量: {len(manual_parsed)}")
                            # 比较两种解析方式的结果差异
                            original_directives = [d.get('directive', '') for d in parsed_directives]
                            manual_directives = [d.get('directive', '') for d in manual_parsed]
                            print(f"原解析指令: {original_directives}")
                            print(f"手动解析指令: {manual_directives}")

                            # 更新文件解析结果
                            file['parsed'] = manual_parsed
                            file['status'] = 'manual_ok'
                            print(f"文件 {file_path} 已更新为手动解析结果")
                    except Exception as e:
                        print(f"测试手动解析失败: {e}")
                else:
                    print(f"本地文件不存在: {local_file_path}，无法进行手动解析")

            # 更新解析后的指令列表和状态
            parsed_directives = file.get('parsed', [])
            file_status = file.get('status', 'unknown')

            # 检查是否包含server或upstream等有效指令
            has_valid_directives = False
            for directive in parsed_directives:
                directive_name = directive.get('directive', '')
                if directive_name in ['server', 'upstream', 'location', 'proxy_pass', 'http', 'events']:
                    has_valid_directives = True
                    break

            # 修复：改进跳过逻辑，正确处理手动解析后的文件
            if file_status in ['error', 'exception', 'empty', 'skipped', 'failed'] and not has_valid_directives:
                print(f"跳过状态为 {file_status} 且不包含有效指令的文件: {file_path}")
                continue

            processed_files += 1
            if has_valid_directives or file_status not in ['error', 'exception', 'empty', 'skipped', 'failed']:
                valid_files += 1

            print(f"处理第{processed_files}个配置文件: {file_path}, 状态: {file_status}")
            file_all_directives_dict = file['parsed']
            print(f'配置文件解析结果包含指令数量: {len(file_all_directives_dict)}')

            # 详细记录文件内容，便于调试
            print(f"文件 {file_path} 的详细指令:")
            for i, directive in enumerate(file_all_directives_dict):
                directive_name = directive.get('directive', '未知')
                args = directive.get('args', [])
                line = directive.get('line', '未知')
                print(f"  指令 {i}: {directive_name}, 行号: {line}, 参数: {args}")

            # 使用新的递归处理函数处理所有指令
            process_directives(file_all_directives_dict, file_path)

        print(f"分析完成，处理了{processed_files}个配置文件，其中{valid_files}个有效")
        print(
            f"找到虚拟主机: {len(virtual_server_name_list)}, upstream: {len(upstream_name_list)}, 后端服务器: {len(backend_server_ip_port_list)}")

        # 如果没有找到任何配置，记录详细日志
        if len(virtual_server_name_list) == 0 and len(upstream_name_list) == 0:
            print("警告: 未找到任何虚拟主机或upstream配置")
            print("详细配置文件状态:")
            for file in self.nginx_conf:
                file_path = file['file']
                file_status = file.get('status', 'unknown')
                parsed_count = len(file.get('parsed', []))
                print(f"  文件: {file_path}, 状态: {file_status}, 指令数量: {parsed_count}")

                # 显示每个文件的详细指令
                parsed_directives = file.get('parsed', [])
                for i, directive in enumerate(parsed_directives):
                    directive_name = directive.get('directive', '未知')
                    args = directive.get('args', [])
                    line = directive.get('line', '未知')
                    print(f"    指令 {i}: {directive_name}, 行号: {line}, 参数: {args}")

        return (virtual_server_name_list, virtual_servers_info_dict,
                upstream_name_list, upstreams_info_dict,
                backend_server_ip_port_list, backend_servers_info_dict)
class NginxParamikoClient:
    def __init__(self, host, port=22, username=None, password=None, key_file=None, key_content=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_file = key_file
        self.key_content = key_content  # 新增：支持直接传入密钥内容
        self.ssh_client = None
        self.local_config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_nginx_configs')
        os.makedirs(self.local_config_dir, exist_ok=True)

    def connect(self):
        """建立SSH连接 - 支持多种认证方式"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # 优先级：密钥内容 > 密钥文件 > 密码认证
            if self.key_content:
                # 使用密钥内容认证
                key = paramiko.RSAKey.from_private_key(StringIO(self.key_content))
                self.ssh_client.connect(
                    self.host, self.port, self.username, pkey=key
                )
            elif self.key_file:
                # 使用密钥文件认证
                key = paramiko.RSAKey.from_private_key_file(self.key_file)
                self.ssh_client.connect(
                    self.host, self.port, self.username, pkey=key
                )
            else:
                # 使用密码认证
                self.ssh_client.connect(
                    self.host, self.port, self.username, self.password
                )
            return True
        except Exception as e:
            logger.error(f"SSH连接失败: {e}")
            return False

    def execute_command(self, command):
        """执行远程命令"""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode()
            error = stderr.read().decode()
            return_code = stdout.channel.recv_exit_status()

            return {
                'success': return_code == 0,
                'output': output,
                'error': error,
                'return_code': return_code
            }
        except Exception as e:
            logger.error(f"命令执行失败: {e}")
            return {'success': False, 'error': str(e)}

    def check_nginx_config(self, nginx_path='/etc/nginx/nginx.conf'):
        """检查Nginx配置语法"""
        command = f"nginx -t -c {nginx_path}"
        return self.execute_command(command)

    def save_remote_file_to_local(self, remote_file_path):
        """将远程文件保存到本地目录"""
        try:
            # 读取远程文件内容
            read_result = self.read_config_file(remote_file_path)
            if not read_result['success']:
                return {'success': False, 'error': f'读取远程文件失败: {read_result.get("error", "未知错误")}'}

            file_content = read_result['output']

            # 生成本地文件路径
            # 使用远程路径的basename作为本地文件名，避免路径冲突
            import posixpath
            remote_basename = posixpath.basename(remote_file_path)
            local_file_path = os.path.join(self.local_config_dir, remote_basename)

            # 保存文件到本地
            with open(local_file_path, 'w', encoding='utf-8') as f:
                f.write(file_content)

            print(f"远程文件 {remote_file_path} 已保存到本地: {local_file_path}")
            return {
                'success': True,
                'local_path': local_file_path,
                'remote_path': remote_file_path,
                'content': file_content
            }
        except Exception as e:
            logger.error(f"保存远程文件到本地失败: {e}")
            return {'success': False, 'error': str(e)}
    def reload_nginx(self):
        """重载Nginx配置"""
        command = "nginx -s reload"
        return self.execute_command(command)

    def get_nginx_status(self):
        """获取Nginx状态"""
        command = "systemctl status nginx || ps aux | grep nginx"
        return self.execute_command(command)

    def read_config_file(self, file_path):
        """读取配置文件内容"""
        command = f"cat {file_path}"
        return self.execute_command(command)

    def write_config_file(self, file_path, content):
        """写入配置文件"""
        # 使用echo命令写入内容
        escaped_content = content.replace('"', '\\"').replace('$', '\\$')
        command = f'echo "{escaped_content}" > {file_path}'
        return self.execute_command(command)

    def upload_config_file(self, local_file_path, remote_file_path):
        """使用SCP上传本地文件到远程服务器"""
        try:
            # 创建SFTP客户端
            sftp = self.ssh_client.open_sftp()

            # 上传文件
            sftp.put(local_file_path, remote_file_path)

            # 关闭SFTP连接
            sftp.close()

            return {
                'success': True,
                'message': f'文件上传成功: {local_file_path} -> {remote_file_path}'
            }
        except Exception as e:
            logger.error(f"SCP上传失败: {e}")
            return {
                'success': False,
                'error': f'SCP上传失败: {str(e)}'
            }

    def upload_config_content(self, content, remote_file_path):
        """将配置内容写入临时文件并上传到远程服务器"""
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.conf') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            # 上传临时文件
            result = self.upload_config_file(temp_file_path, remote_file_path)

            # 删除临时文件
            os.unlink(temp_file_path)

            return result
        except Exception as e:
            logger.error(f"配置内容上传失败: {e}")
            return {
                'success': False,
                'error': f'配置内容上传失败: {str(e)}'
            }
    def get_nginx_config_files(self, config_dir='/etc/nginx/'):
        """获取Nginx配置目录下的所有文件"""
        command = f"find {config_dir} -name '*.conf' -type f"
        result = self.execute_command(command)
        print('文件查找结果',result)
        if result['success']:
            files = [f.strip() for f in result['output'].split('\n') if f.strip()]
            return files
        return []

    def _parse_nginx_config_recursive(self, file_path, parsed_files=None):
        """简化版：专门解析nginx.conf中的http块include指令，保存所有.conf文件到本地"""
        if parsed_files is None:
            parsed_files = set()

        # 检查文件是否已经解析过
        if file_path in parsed_files:
            print(f"文件 {file_path} 已经解析过，跳过")
            return []
        parsed_files.add(file_path)

        print(f"开始解析配置文件: {file_path}")

        # 1. 保存远程文件到本地
        save_result = self.save_remote_file_to_local(file_path)
        if not save_result['success']:
            print(f"保存远程文件到本地失败: {save_result.get('error', '未知错误')}")
            return [{
                'file': file_path,
                'status': 'error',
                'parsed': [{'directive': 'error_log', 'args': [f'保存到本地失败: {save_result.get("error", "未知错误")}'], 'line': 1}]
            }]

        local_file_path = save_result['local_path']
        file_content = save_result['content']
        print(f"配置文件 {file_path} 已保存到本地: {local_file_path}")

        # 跳过mime.types文件
        if 'mime.types' in file_path:
            print(f"跳过mime.types文件: {file_path}")
            try:
                os.unlink(local_file_path)
            except:
                pass
            return [{
                'file': file_path,
                'status': 'skipped',
                'parsed': [{'directive': 'types', 'args': ['MIME类型定义文件，跳过解析'], 'line': 1}]
            }]

        # 2. 解析主配置文件
        print(f"解析主配置文件 {file_path}")
        try:
            parsed_config = crossplane.parse(local_file_path, catch_errors=True, combine=True)
            print(f"主配置文件 {file_path} 解析完成")
        except Exception as e:
            print(f"主配置文件 {file_path} 解析失败: {e}")
            parsed_config = {
                'status': 'error',
                'errors': [str(e)],
                'config': [{
                    'file': file_path,
                    'status': 'error',
                    'parsed': [{'directive': 'error_log', 'args': [f'解析失败: {str(e)}'], 'line': 1}]
                }]
            }

        configs = parsed_config.get('config', [])
        all_configs = []

        # 处理当前文件的配置
        for config in configs:
            config['file'] = file_path  # 确保文件路径正确
            all_configs.append(config)

        # 3. 提取http块中的include目录，通过远程命令获取所有.conf文件
        print(f"提取http块中的include目录")
        include_dirs = self._extract_http_include_directories(file_content)
        print(f"找到http块中的include目录: {include_dirs}")

        for include_dir in include_dirs:
            print(f"处理include目录: {include_dir}")
            # 通过远程命令获取目录下所有.conf文件
            conf_files = self._get_conf_files_from_remote_dir(include_dir)
            print(f"在目录 {include_dir} 中找到 {len(conf_files)} 个.conf文件")

            for conf_file in conf_files:
                if conf_file not in parsed_files:
                    print(f"开始处理include文件: {conf_file}")
                    # 递归处理include文件
                    include_configs = self._parse_nginx_config_recursive(conf_file, parsed_files)
                    all_configs.extend(include_configs)
                else:
                    print(f"文件 {conf_file} 已经处理过，跳过")

        print(f"文件 {file_path} 处理完成，总共得到 {len(all_configs)} 个配置块")
        return all_configs

    def _extract_http_include_directories(self, file_content):
        """提取http块中的include指令指定的目录路径"""
        import re
        include_dirs = set()

        # 首先检查是否包含http块
        if 'http {' not in file_content:
            print("文件中不包含http块，跳过http块include指令提取")
            return []

        print("检测到http块，开始提取其中的include指令")

        # 匹配http块中的include指令
        include_pattern = r'include\s+([^;#\n]+)[;#\n]'
        matches = re.findall(include_pattern, file_content)

        for match in matches:
            include_pattern = match.strip().strip('"').strip("'")

            # 清理路径，移除可能的注释
            if '#' in include_pattern:
                include_pattern = include_pattern.split('#')[0].strip()

            # 跳过mime.types文件
            if 'mime.types' in include_pattern:
                print(f"跳过mime.types文件: {include_pattern}")
                continue

            # 提取目录路径（移除通配符部分）
            if '*.conf' in include_pattern:
                # 提取目录路径，例如：/etc/nginx/conf.d/*.conf -> /etc/nginx/conf.d
                dir_path = include_pattern.replace('*.conf', '').rstrip('/')
                if dir_path and dir_path.startswith('/'):
                    include_dirs.add(dir_path)
                    print(f"添加include目录: {dir_path}")

        return list(include_dirs)

    def _get_conf_files_from_remote_dir(self, dir_path):
        """通过远程命令获取指定目录下所有.conf文件并保存到本地"""
        try:
            # 使用find命令查找目录下所有.conf文件
            command = f"find {dir_path} -name '*.conf' -type f"
            result = self.execute_command(command)

            if result['success']:
                files = [f.strip() for f in result['output'].split('\n') if f.strip()]
                print(f"在目录 {dir_path} 中找到.conf文件: {files}")

                # 保存每个文件到本地
                saved_files = []
                for file_path in files:
                    save_result = self.save_remote_file_to_local(file_path)
                    if save_result['success']:
                        saved_files.append(file_path)
                        print(f"文件 {file_path} 已保存到本地: {save_result['local_path']}")
                    else:
                        print(f"保存文件 {file_path} 到本地失败: {save_result.get('error', '未知错误')}")

                return saved_files
            else:
                print(f"查找目录 {dir_path} 中的.conf文件失败: {result.get('error', '未知错误')}")
                return []
        except Exception as e:
            print(f"获取目录 {dir_path} 中的.conf文件时发生异常: {e}")
            return []

    def get_nginx_config_analysis(self, nginx_main_conf_path='/etc/nginx/nginx.conf'):
        """获取Nginx配置的完整分析结果"""
        try:
            print(f"开始获取Nginx配置分析，主配置文件路径: {nginx_main_conf_path}")

            # 1. 递归解析所有配置文件（包括include引入的文件）
            print("开始递归解析Nginx配置文件...")
            all_configs = self._parse_nginx_config_recursive(nginx_main_conf_path)
            print(f"递归解析完成，总共解析了 {len(all_configs)} 个配置文件")

            # 构建crossplane兼容的配置结构
            parsed_config = {
                'status': 'ok',
                'errors': [],
                'config': all_configs
            }

            print(f"最终配置结构包含 {len(all_configs)} 个配置文件")
            for config in all_configs:
                print(f"配置文件: {config.get('file', '未知')}")

            # 2. 创建Nginx分析实例
            nginx_analyzer = NginxAnalyzer(
                nginx_main_conf_path=nginx_main_conf_path,
                nginx_obj_dict=parsed_config
            )
            print("NginxAnalyzer实例创建成功")

            # 3. 执行完整的配置分析
            print("开始执行analysis_nginx_all_conf方法...")
            analysis_result = nginx_analyzer.analysis_nginx_all_conf()
            print("analysis_nginx_all_conf方法执行完成")

            # 直接返回分析结果，不包含success和error字段
            return {
                'virtual_servers': analysis_result[0],  # 虚拟主机列表
                'virtual_servers_info': analysis_result[1],  # 虚拟主机详细信息
                'upstreams': analysis_result[2],  # upstream列表
                'upstreams_info': analysis_result[3],  # upstream详细信息
                'backend_servers': analysis_result[4],  # 后端服务器列表
                'backend_servers_info': analysis_result[5],  # 后端服务器详细信息
                'config_files': nginx_analyzer.get_file_path_list(),
                'pid_file_path': nginx_analyzer.get_pid_file_path()
            }

        except Exception as e:
            logger.error(f"配置分析失败: {e}")
            print(f"配置分析过程中发生异常: {e}")
            # 发生异常时直接抛出，让调用方处理
            raise e

    def get_backend_server_info_dict(self):
        backend_server_info_dict = {}
        for file in self.nginx_conf:
            file_path = file['file']
            # 关键修改：不再跳过主配置文件，只跳过mime.types文件
            if 'mime.types' in file_path:
                continue

            file_all_directives_list = file['parsed']
            for file_per_directive_dict in file_all_directives_list:
                if file_per_directive_dict['directive'] == 'upstream':
                    upstream_name = "".join(file_per_directive_dict['args'])
                    upstream_all_directives_list = file_per_directive_dict['block']
                    for upstream_per_directive_dict in upstream_all_directives_list:
                        if upstream_per_directive_dict['directive'] == 'server':
                            backend_server_args_list = upstream_per_directive_dict['args']
                            backend_server_addr = backend_server_args_list[0]
                            backend_server_info_dict[backend_server_addr] = {
                                'file_path': file_path,
                                'upstream': upstream_name,
                                'status': 'down' if 'down' in backend_server_args_list else
                                'backup' if 'backup' in backend_server_args_list else ''
                            }
        return backend_server_info_dict

    def validate_nginx_config_structure(self, nginx_main_conf_path='/etc/nginx/nginx.conf'):
        """验证Nginx配置结构"""
        try:
            # 读取配置文件内容
            main_conf_result = self.read_config_file(nginx_main_conf_path)
            if not main_conf_result['success']:
                raise Exception(f"无法读取主配置文件: {main_conf_result.get('error', '未知错误')}")

            main_conf_content = main_conf_result['output']

            # 使用crossplane.parse解析内容
            parsed_config = crossplane.parse(main_conf_content)

            nginx_analyzer = NginxAnalyzer(
                nginx_main_conf_path=nginx_main_conf_path,
                nginx_obj_dict=parsed_config
            )

            # 执行配置验证
            nginx_analyzer.check_main_conf_file()  # 检查主配置文件
            nginx_analyzer.check_file_path_is_under_main_file_dir()  # 检查文件路径

            # 直接返回成功消息
            return '配置结构验证通过'
        except Exception as e:
            # 发生异常时直接抛出
            raise e
    def get_virtual_hosts(self, nginx_main_conf_path='/etc/nginx/nginx.conf'):
        """获取所有虚拟主机信息"""
        analysis_result = self.get_nginx_config_analysis(nginx_main_conf_path)
        # 直接返回虚拟主机相关信息
        return {
            'virtual_hosts': analysis_result['virtual_servers'],
            'virtual_hosts_info': analysis_result['virtual_servers_info']
        }
    def get_upstreams(self, nginx_main_conf_path='/etc/nginx/nginx.conf'):
        """获取所有upstream信息"""
        analysis_result = self.get_nginx_config_analysis(nginx_main_conf_path)
        # 直接返回upstream相关信息
        return {
            'upstreams': analysis_result['upstreams'],
            'upstreams_info': analysis_result['upstreams_info']
        }
    def close(self):
        """关闭连接"""
        if self.ssh_client:
            self.ssh_client.close()


