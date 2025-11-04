import configparser
import os

def get_client_port(client_ip):
    """获取客户端端口号"""
    config = configparser.ConfigParser()
    config.read('conf/conf_server.ini')
    return config.get('client', client_ip)

def check_nginx_config(client_ip):
    """检查Nginx配置语法"""
    client_port = get_client_port(client_ip)
    import requests
    url = f'http://{client_ip}:{client_port}/nginx_conf/check'
    response = requests.post(url)
    return response.json()

def reload_nginx_config(client_ip):
    """重载Nginx配置"""
    client_port = get_client_port(client_ip)
    import requests
    url = f'http://{client_ip}:{client_port}/nginx_conf/reload'
    response = requests.post(url)
    return response.json()