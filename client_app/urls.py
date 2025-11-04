from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('register/',views.register_client,name='register_client'),
    path('getclient/',views.get_clients, name='get_client')
]