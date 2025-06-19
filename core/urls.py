# core/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeliveryOrderViewSet, RobotViewSet, UserViewSet, DispatchOrderViewSet, MessageViewSet, QRCodeVerifyView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register('orders', DeliveryOrderViewSet, basename='orders')
router.register('robots', RobotViewSet, basename='robots')
router.register('users', UserViewSet, basename='users')

router.register(r'dispatch/orders', DispatchOrderViewSet, basename='dispatch-orders')

router.register('messages', MessageViewSet, basename='messages')



# www.luanqibazao.com/login
urlpatterns = [
    path('api/', include(router.urls)),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/verify_qr/', QRCodeVerifyView.as_view(), name='verify-qr'),

]
