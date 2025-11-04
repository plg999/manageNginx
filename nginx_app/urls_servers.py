from django.urls import path
from . import views

urlpatterns = [
    # 服务器同步
    path('sync/', views.receive_backend_server_info, name='sync-servers'),

    # 服务器查询
    path('', views.read_all_backend_servers, name='get-servers'),

    # 服务器状态管理
    path('status/', views.update_backend_server_status, name='update-server-status'),
]