from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from nginx_app import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # API根目录
    # path('api/', views.api_root, name='api-root'),
    # 用户管理路由
    path('api/users/', include('auth_app.urls')),
    # 客户端相关路由
    path('api/clients/', include('client_app.urls')),  # 客户端管理
    path('api/configs/', include('nginx_app.urls')),  # 配置管理
    path('api/servers/', include('nginx_app.urls_servers')),  # 服务
    # REST Framework认证
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)