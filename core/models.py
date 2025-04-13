from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)

    def __str__(self):
        return self.username


class DeliveryOrder(models.Model):
    STATUS_CHOICES = [
        ('PENDING', '待分配'),
        ('ASSIGNED', '已装入机器人'),
        ('DELIVERING', '配送中'),
        ('DELIVERED', '已送达'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    teacher = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    pickup_location = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    def __str__(self):
        return f"Order #{self.id} - {self.status}"


class Robot(models.Model):
    name = models.CharField(max_length=50)
    is_available = models.BooleanField(default=True)
    next_available_time = models.DateTimeField(null=True, blank=True)

    current_order = models.OneToOneField(DeliveryOrder, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.name} - {'空闲' if self.is_available else '忙碌'}"

