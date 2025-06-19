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
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def post(self, request):
        image = request.FILES.get('file')
        print("🖼️ 收到上传文件：", image.name if image else "无文件")

        if not image:
            return Response({"error_code": 1001, "detail": "未上传二维码图片"}, status=400)

        try:
            img = Image.open(image)
            qr_data_list = decode(img)
            print("🔍 二维码识别结果：", qr_data_list)

            if not qr_data_list:
                return Response({"error_code": 1002, "detail": "无法识别二维码"}, status=400)

            try:
                data = qr_data_list[0].data.decode("utf-8")
                print("📦 原始二维码内容：", data)
                qr_json = json.loads(data)
            except Exception as e:
                print("❌ 二维码数据解析失败：", e)
                return Response({"error_code": 1003, "detail": f"二维码数据解析失败: {str(e)}"}, status=400)

            payload_b64 = qr_json.get("payload")
            signature = qr_json.get("signature")
            print("📦 payload（base64）: ", payload_b64)
            print("🔏 signature: ", signature)

            if not payload_b64 or not signature:
                return Response({"error_code": 1004, "detail": "二维码数据格式不完整"}, status=400)

            try:
                payload_str = base64.b64decode(payload_b64).decode()
                print("📄 解码后的 payload：", payload_str)
            except Exception as e:
                print("❌ payload 解码失败：", e)
                return Response({"error_code": 1005, "detail": "payload 解码失败"}, status=400)

            expected_signature = hashlib.sha256((payload_str + settings.SECRET_KEY).encode()).hexdigest()
            print("🧮 校验签名：", expected_signature == signature)

            if signature != expected_signature:
                return Response({"error_code": 1006, "detail": "签名校验失败"}, status=403)

            try:
                payload = json.loads(payload_str)
                order_id = payload.get("order_id")
                student_id = payload.get("student_id")
                print("📋 提取 payload 字段：order_id =", order_id, "student_id =", student_id)
            except Exception as e:
                print("❌ payload 内容解析失败：", e)
                return Response({"error_code": 1007, "detail": "payload 内容解析失败"}, status=400)

            if not order_id or not student_id:
                return Response({"error_code": 1008, "detail": "payload 缺少必要字段"}, status=400)

            try:
                order = DeliveryOrder.objects.get(id=order_id, student_id=student_id)
                print("✅ 找到订单：", order.id)
            except DeliveryOrder.DoesNotExist:
                print("❌ 订单不存在或 student_id 不匹配")
                return Response({"error_code": 1009, "detail": "订单不存在或 student_id 不匹配"}, status=404)

            order.status = "DELIVERED"
            order.save()
            print("🚚 状态已更新为已送达")

            return Response({
                "detail": "✅ 验证成功，状态已更新为已送达",
                "order_id": order.id,
                "new_status": order.status,
            })

        except Exception as e:
            print("🔥 未知异常：", type(e).__name__, str(e))
            return Response({
                "error_code": 1999,
                "detail": f"服务器内部错误: {type(e).__name__}: {str(e)}"
            }, status=500)
