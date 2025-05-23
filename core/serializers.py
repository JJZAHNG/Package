# core/serializers.py

from rest_framework import serializers
from .models import User, DeliveryOrder, Robot, Message
from django.contrib.auth import get_user_model
from datetime import date, datetime
from django.utils import timezone
from django.contrib.auth.hashers import make_password



User = get_user_model()

# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['id', 'username', 'password', 'is_student', 'is_teacher']
#         extra_kwargs = {'password': {'write_only': True}}



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'password', 'is_student', 'is_teacher', 'is_dispatcher']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    def update(self, instance, validated_data):
        # 如果包含密码字段，做加密处理
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.password = make_password(password)

        instance.save()
        return instance


class DeliveryOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryOrder
        fields = '__all__'
        read_only_fields = ['student', 'teacher', 'status', 'created_at']

    def validate(self, data):
        """
        校验预约时间不能是过去
        """
        scheduled_date = data.get('scheduled_date')
        scheduled_time = data.get('scheduled_time')

        if scheduled_date:
            today = date.today()
            if scheduled_date < today:
                raise serializers.ValidationError("预约日期不能早于今天")

            if scheduled_date == today and scheduled_time:
                now_time = timezone.localtime().time()
                if scheduled_time < now_time:
                    raise serializers.ValidationError("预约时间不能早于当前时间")

        return data

    def to_representation(self, instance):
        """
        自定义输出格式：fragile 显示为 是/否
        """
        rep = super().to_representation(instance)
        rep['fragile'] = "是" if instance.fragile else "否"
        return rep


class RobotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Robot
        fields = '__all__'


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'name', 'email', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']


