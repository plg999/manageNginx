from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .serializers import LoginSerializer, UserSerializer

User = get_user_model()


@api_view(['GET'])
def get_user_list(request):
    """
    获取用户列表
    需要认证才能访问
    """
    try:
        # 获取所有用户
        users = User.objects.all()

        # 使用分页（可选）
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))

        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        paginated_users = users[start_index:end_index]

        # 序列化用户数据
        serializer = UserSerializer(paginated_users, many=True)

        response_data = {
            'users': serializer.data,
            'total_count': users.count(),
            'page': page,
            'page_size': page_size,
            'total_pages': (users.count() + page_size - 1) // page_size,
            'status': 200
        }

        return Response(response_data)

    except Exception as e:
        return Response({
            'msg': f'获取用户列表失败: {str(e)}',
            'status': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_user_detail(request, user_id):
    """获取单个用户详情"""
    try:
        user = User.objects.get(id=user_id)
        serializer = UserSerializer(user)

        return Response({
            'user': serializer.data,
            'status': 200
        })

    except User.DoesNotExist:
        return Response({
            'msg': '用户不存在',
            'status': 404
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({
            'msg': f'获取用户详情失败: {str(e)}',
            'status': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(['GET'])
def get_current_user(request):
    """
    获取当前登录用户信息
    """
    try:
        user = request.user
        serializer = UserSerializer(user)

        return Response({
            'user': serializer.data,
            'status': 200
        })

    except Exception as e:
        return Response({
            'msg': f'获取当前用户信息失败: {str(e)}',
            'status': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def login(request):
    """用户登录"""
    # 如果是GET请求，返回错误信息或重定向
    if request.method == 'GET':
        return Response({
            'msg': '请使用POST方法进行登录',
            'status': 405
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    serializer = LoginSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        response_data = {
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'status': 200,
            'user': UserSerializer(user).data
        }

        return Response(response_data)

    return Response({
        'msg': serializer.errors,
        'status': 401
    }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
def logout(request):
    """用户登出"""
    try:
        refresh_token = request.data.get('refresh_token')
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'msg': '登出成功', 'status': 200})
    except Exception as e:
        return Response({'msg': str(e), 'status': 400}, status=400)
@api_view(['POST'])
def token_refresh(request):
    """刷新JWT令牌"""
    try:
        refresh_token = request.data.get('refresh_token')
        token = RefreshToken(refresh_token)
        new_access_token = str(token.access_token)

        return Response({
            'access_token': new_access_token,
            'status': 200
        })
    except Exception as e:
        return Response({
            'msg': f'令牌刷新失败: {str(e)}',
            'status': 400
        }, status=400)