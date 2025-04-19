from django.shortcuts import render

# Create your views here.
# core/views.py

from rest_framework import viewsets, permissions
from .models import DeliveryOrder, Robot
from .serializers import DeliveryOrderSerializer, RobotSerializer, UserSerializer
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from .utils import generate_signed_payload, generate_qr_code


User = get_user_model()

class IsAdminUserOnly(permissions.BasePermission):
    """
    仅允许管理员用户（is_staff=True）增删改机器人
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'], url_path='me')
    def get_current_user(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class DeliveryOrderViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_teacher:
            return DeliveryOrder.objects.all()
        return DeliveryOrder.objects.filter(student=user)

    def perform_create(self, serializer):
        # 保存订单（此时还没有 ID，需保存后获取）
        order = serializer.save(student=self.request.user)

        # 生成签名数据和二维码图像
        signed_data = generate_signed_payload(order.id, order.student.id)
        qr_base64 = generate_qr_code(signed_data)

        # print("🔥 二维码链接长度：", len(order.qr_code_url))
        # print("🔗 链接内容：", order.qr_code_url)

        # 更新订单对象，写入二维码字段
        order.qr_code_url = qr_base64
        order.save()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        # 🔒 仅允许老师更新订单（学生不能执行分配）
        if not request.user.is_teacher:
            return Response({'detail': '只有教师可以分配机器人'}, status=status.HTTP_403_FORBIDDEN)

        # ⚠️ 状态必须是待分配才能分配机器人
        if instance.status != "PENDING":
            return Response({'detail': '订单已分配或正在配送中'}, status=status.HTTP_400_BAD_REQUEST)

        # 🚚 找一个空闲机器人
        robot = Robot.objects.filter(is_available=True).first()
        if not robot:
            return Response({'detail': '当前无可用机器人'}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ 更新订单状态 & 教师 & 绑定机器人
        instance.status = "ASSIGNED"
        instance.teacher = request.user
        instance.save()

        robot.is_available = False
        robot.current_order = instance
        robot.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

# class RobotViewSet(viewsets.ReadOnlyModelViewSet):
#     queryset = Robot.objects.all()
#     serializer_class = RobotSerializer
#     permission_classes = [permissions.IsAuthenticated]

class RobotViewSet(viewsets.ModelViewSet):
    queryset = Robot.objects.all()
    serializer_class = RobotSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUserOnly()]
        return [permissions.IsAuthenticated()]


