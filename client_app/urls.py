from django.urls import path
from . import views

urlpatterns = [

    # 客户端管理
    path('list/', views.get_client_ip_list, name='client-list'),
    path('info/', views.receive_client_info, name='client-info'),

    path('health/', views.health_check, name='health_check'),
    path('register/',views.register_client,name='register_client'),
]