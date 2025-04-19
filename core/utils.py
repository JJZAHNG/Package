# core/utils.py

import qrcode
import base64
import json
import hashlib
from io import BytesIO
from django.conf import settings

SECRET_KEY = settings.SECRET_KEY  # 可用于签名生成

def generate_signed_payload(order_id, student_id):
    payload = {
        "order_id": order_id,
        "student_id": student_id
    }
    payload_str = json.dumps(payload, separators=(',', ':'))

    # 🔒 生成签名（可用于机器人验证）
    signature = hashlib.sha256((payload_str + SECRET_KEY).encode()).hexdigest()

    return {
        "payload": base64.b64encode(payload_str.encode()).decode(),
        "signature": signature
    }

def generate_qr_code(data: dict) -> str:
    """
    生成二维码并返回 base64 编码字符串
    """
    qr = qrcode.make(json.dumps(data, ensure_ascii=False))
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"
