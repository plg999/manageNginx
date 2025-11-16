from django.urls import path
from . import views

urlpatterns = [
    # 服务器同步
    # path('sync/', views.receive_backend_server_info, name='sync-servers'),


    path('connection/network/', views.test_connect, name='test_connection'),
    path('conf/create/', views.create_nginx_config, name='create-config'),
    path('conf/update/', views.update_nginx_config, name='update-config'),
    path('conf/read/', views.read_nginx_config, name='read-config'),
    path('conf/readAll/', views.read_all_nginx_configs, name='read-all-configs'),
    path('backend_server/readAll/', views.read_all_backend_servers, name='read_all_backend_servers'),
    path('/backend_serve_status/update/', views.read_all_backend_servers, name='read_all_backend_servers'),

    path('backend_server/readUpstream/', views.read_upstream_info, name='read_upstream_info'),
    # 服务器状态管理
    path('status/', views.update_backend_server_status, name='update-server-status'),
]