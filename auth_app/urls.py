from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),

    # 用户管理路由
    path('', views.get_user_list, name='user-list'),
    path('current/', views.get_current_user, name='current-user'),
    path('<int:user_id>/', views.get_user_detail, name='user-detail'),


]