from django.urls import path
from . import views

urlpatterns = [
    # 客户端管理
    path('client/list/', views.get_client_ip_list, name='client-list'),
    path('client/info/', views.receive_client_info, name='client-info'),

    # 配置同步
    path('sync/', views.receive_nginx_file_path_and_content, name='sync-configs'),

    # 配置操作
    path('create/', views.create_nginx_config, name='create-config'),
    path('update/', views.update_nginx_config, name='update-config'),
    path('read/', views.read_nginx_config, name='read-config'),
    path('read-all/', views.read_all_nginx_configs, name='read-all-configs'),
]