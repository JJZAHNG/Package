import qrcode
import base64
import json
import hashlib
from io import BytesIO
from django.conf import settings

SECRET_KEY = settings.SECRET_KEY  # 🔐 用于签名

def generate_signed_payload(order_id, student_id):
    """
    构建签名数据结构：原始 JSON payload + SHA256 签名（基于 SECRET_KEY）
    返回值中 payload 是 base64 编码的字符串
    """
    payload = {
        "order_id": order_id,
        "student_id": student_id
    }

    # ✅ 为了签名稳定性，保证 JSON key 顺序一致
    payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))

    # 🔐 使用 SECRET_KEY 生成签名
    signature = hashlib.sha256((payload_str + SECRET_KEY).encode()).hexdigest()

    return {
        "payload": base64.b64encode(payload_str.encode()).decode(),  # ✅ QR code 中用 base64 编码
        "signature": signature
    }

def generate_qr_code(data: dict) -> str:
    """
    生成二维码并返回 base64 编码 PNG 字符串
    :param data: dict，通常包含 payload(base64字符串) + signature
    :return: base64格式的 PNG 图像字符串（可直接用 <img src=...> 显示）
    """
    qr = qrcode.make(json.dumps(data, ensure_ascii=False))
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"
