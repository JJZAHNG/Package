from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, permissions, status
from .models import DeliveryOrder, Robot, Message
from .serializers import DeliveryOrderSerializer, RobotSerializer, UserSerializer, MessageSerializer
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from .utils import generate_signed_payload, generate_qr_code
from rest_framework.permissions import IsAdminUser


User = get_user_model()


# ✅ 管理员权限控制类
class IsAdminUserOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


# ✅ 新增：分发人员权限控制类
class IsDispatcher(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_dispatcher


# ✅ 用户视图（含 /me）
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'], url_path='me')
    def get_current_user(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def set_dispatcher(self, request, pk=None):
        """
        设置/取消配送员身份（超级管理员专用）
        POST /api/users/<id>/set_dispatcher/
        {
          "is_dispatcher": true
        }
        """
        user = self.get_object()
        is_dispatcher = request.data.get("is_dispatcher")

        if not isinstance(is_dispatcher, bool):
            return Response({"detail": "请提供 is_dispatcher: true/false"}, status=400)

        user.is_dispatcher = is_dispatcher
        user.save()
        return Response({"id": user.id, "username": user.username, "is_dispatcher": user.is_dispatcher})


# ✅ 学生 / 老师订单接口
class DeliveryOrderViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_teacher:
            return DeliveryOrder.objects.all()
        return DeliveryOrder.objects.filter(student=user)

    def perform_create(self, serializer):
        order = serializer.save(student=self.request.user)
        signed_data = generate_signed_payload(order.id, order.student.id)
        qr_base64 = generate_qr_code(signed_data)
        order.qr_code_url = qr_base64
        order.save()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if not request.user.is_teacher:
            return Response({'detail': '只有教师可以分配机器人'}, status=status.HTTP_403_FORBIDDEN)

        if instance.status != "PENDING":
            return Response({'detail': '订单已分配或正在配送中'}, status=status.HTTP_400_BAD_REQUEST)

        robot = Robot.objects.filter(is_available=True).first()
        if not robot:
            return Response({'detail': '当前无可用机器人'}, status=status.HTTP_400_BAD_REQUEST)

        instance.status = "ASSIGNED"
        instance.teacher = request.user
        instance.save()

        robot.is_available = False
        robot.current_order = instance
        robot.save()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# ✅ 配送人员专属订单操作接口
class DispatchOrderViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryOrderSerializer
    permission_classes = [IsDispatcher]

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        if status_filter:
            return DeliveryOrder.objects.filter(status=status_filter)
        return DeliveryOrder.objects.all()

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_status = request.data.get('status')

        if new_status not in ['ASSIGNED', 'DELIVERING', 'DELIVERED']:
            return Response({"detail": "不允许设置该状态"}, status=status.HTTP_400_BAD_REQUEST)

        instance.status = new_status
        instance.save()
        return Response(self.get_serializer(instance).data)


# ✅ 机器人接口
class RobotViewSet(viewsets.ModelViewSet):
    queryset = Robot.objects.all()
    serializer_class = RobotSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUserOnly()]
        return [permissions.IsAuthenticated()]


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all().order_by('-created_at')
    serializer_class = MessageSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]
