from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, permissions, status
from .models import DeliveryOrder, Robot, Message
from .serializers import DeliveryOrderSerializer, RobotSerializer, UserSerializer, MessageSerializer
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from .utils import generate_signed_payload, generate_qr_code
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from pyzbar.pyzbar import decode
from PIL import Image
import json, hashlib, base64
from django.conf import settings




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


class QRCodeVerifyView(APIView):
    permission_classes = [AllowAny]  # ✅ 不需要登录认证
    parser_classes = [MultiPartParser]  # ✅ 支持文件上传

    def post(self, request):
        image = request.FILES.get('file')

        if not image:
            return Response({"detail": "未上传二维码图片"}, status=400)

        try:
            img = Image.open(image)
            qr_data_list = decode(img)

            if not qr_data_list:
                return Response({"detail": "无法识别二维码"}, status=400)

            # ✅ 第一个二维码内容（字符串格式）
            data = qr_data_list[0].data.decode("utf-8")
            qr_json = json.loads(data)

            # ✅ 从二维码中获取 base64 编码的 payload 和签名
            payload_b64 = qr_json.get("payload")
            signature = qr_json.get("signature")

            if not payload_b64 or not signature:
                return Response({"detail": "二维码数据格式无效"}, status=400)

            # ✅ 解码 payload
            try:
                payload_str = base64.b64decode(payload_b64).decode()
            except Exception:
                return Response({"detail": "无法解码 payload"}, status=400)

            # ✅ 签名校验
            expected_signature = hashlib.sha256((payload_str + settings.SECRET_KEY).encode()).hexdigest()
            if signature != expected_signature:
                return Response({"detail": "签名无效"}, status=403)

            # ✅ 提取 payload 内容
            payload = json.loads(payload_str)
            order_id = payload.get("order_id")
            student_id = payload.get("student_id")

            if not order_id or not student_id:
                return Response({"detail": "payload 数据不完整"}, status=400)

            # ✅ 查找订单并确认身份
            try:
                order = DeliveryOrder.objects.get(id=order_id, student_id=student_id)
            except DeliveryOrder.DoesNotExist:
                return Response({"detail": "订单不存在或身份不符"}, status=404)

            # ✅ 修改订单状态
            order.status = "DELIVERED"
            order.save()

            return Response({
                "detail": "✅ 验证成功，状态已更新为已送达",
                "order_id": order.id,
                "new_status": order.status,
            })

        except Exception as e:
            return Response({"detail": f"处理失败: {str(e)}"}, status=500)