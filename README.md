# 校园快递系统 · 后端 API 接口文档

版本：v1.0  
更新日期：2025-05-22  
作者：Alan & 开发团队  

---

## 认证说明（JWT）

- 登录获取 Access Token / Refresh Token

- 除特殊接口（如扫码识别）外，所有接口均需认证

- 请求头中添加：

  ```
  Authorization: Bearer <access_token>
  ```

---

## 通用返回格式

```json
{
  "detail": "操作成功/错误信息",
  ...其他数据字段
}
```

---

## 接口目录总览

| 模块     | 接口路径示例            | 方法  | 描述                   |
| -------- | ----------------------- | ----- | ---------------------- |
| 用户     | `/api/users/`           | GET   | 获取当前用户信息       |
| 登录     | `/api/token/`           | POST  | 获取 JWT Token         |
| 订单     | `/api/orders/`          | POST  | 创建订单（学生）       |
| 分发员   | `/api/dispatch/orders/` | PATCH | 更改订单状态（配送员） |
| 机器人   | `/api/robots/`          | GET   | 获取机器人列表         |
| 留言     | `/api/messages/`        | POST  | 提交留言               |
| 签收扫码 | `/api/verify_qr/`       | POST  | 上传二维码识别并签收   |

---

## 用户模块

### 🔹 获取当前登录用户信息

- **URL**：`/api/users/me/`
- **方法**：GET
- **权限**：🔒 登录后

**返回示例**：

```json
{
  "id": 3,
  "username": "jjzhang",
  "email": "jj@example.com",
  "is_student": true,
  "is_teacher": false
}
```

---

## 登录模块

### 🔹 获取 Token（登录）

- **URL**：`/api/token/`
- **方法**：POST
- **权限**：🔓 无需认证

**请求参数**：

```json
{
  "username": "jjzhang",
  "password": "123456"
}
```

**返回示例**：

```json
{
  "access": "eyJ0eXAiOiJKV1Qi...",
  "refresh": "eyJ0eXAiOiJKV1Qi..."
}
```

---

## 订单模块

### 🔹 创建订单（学生）

- **URL**：`/api/orders/`
- **方法**：POST
- **权限**：🔒 登录后（学生）

**请求参数字段说明**：

| 字段名              | 类型    | 是否必填 | 示例值       | 描述             |
| ------------------- | ------- | -------- | ------------ | ---------------- |
| package_type        | string  | ✅        | "box"        | 包裹类型         |
| weight              | string  | ✅        | "medium"     | 重量等级         |
| fragile             | boolean | ✅        | true         | 是否易碎         |
| description         | string  | ❌        | "文件资料"   | 包裹描述         |
| pickup_building     | string  | ✅        | "图书馆"     | 取件楼栋         |
| pickup_instructions | string  | ❌        | "门口柜子里" | 取件备注         |
| delivery_building   | string  | ✅        | "宿舍1栋"    | 投递楼栋         |
| delivery_speed      | string  | ✅        | "express"    | 配送速度         |
| scheduled_date      | string  | ❌        | "2025-05-22" | 预约日期（可选） |
| scheduled_time      | string  | ❌        | "14:00"      | 预约时间（可选） |

**成功响应示例**：

```json
{
  "id": 12,
  "status": "PENDING",
  "qr_code_url": "data:image/png;base64,iVBORw0KG..."
}
```

---

## 分发员模块（快递员）

### 🔹 获取订单列表（按状态筛选）

- **URL**：`/api/dispatch/orders/?status=PENDING`
- **方法**：GET
- **权限**：🔒 登录 & 配送员权限

---

### 🔹 修改订单状态

- **URL**：`/api/dispatch/orders/<id>/`
- **方法**：PATCH

**请求体示例**：

```json
{
  "status": "DELIVERING"
}
```

**返回**：

```json
{
  "id": 12,
  "status": "DELIVERING"
}
```

---

## 机器人模块（管理员）

### 🔹 获取机器人列表

- **URL**：`/api/robots/`
- **方法**：GET

---

### 🔹 添加机器人

- **URL**：`/api/robots/`
- **方法**：POST

**请求参数**：

```json
{
  "name": "Robo-001",
  "is_available": true
}
```

---

## 留言模块

### 🔹 用户提交留言

- **URL**：`/api/messages/`
- **方法**：POST
- **权限**：🔒 登录后

```json
{
  "title": "投递晚点",
  "content": "快递延误了半小时，请改进"
}
```

---

## 扫码签收接口

### 🔹 上传二维码图像并自动签收

- **URL**：`/api/verify_qr/`
- **方法**：POST
- **权限**：🔓 不需要登录
- **请求格式**：multipart/form-data

**字段**：

| 字段名 | 类型 | 说明                      |
| ------ | ---- | ------------------------- |
| file   | 文件 | 二维码图片文件（PNG/JPG） |

**成功响应**：

```json
{
  "detail": "✅ 验证成功，状态已更新为已送达",
  "order_id": 17,
  "new_status": "DELIVERED"
}
```

**失败响应示例**：

```json
{
  "detail": "签名无效"
}
```

---

## ❗ 错误码说明

| 状态码 | 含义                     |
| ------ | ------------------------ |
| 400    | 请求参数无效             |
| 401    | 未登录                   |
| 403    | 权限不足 / 签名失败      |
| 404    | 资源不存在（如订单无效） |
| 500    | 服务器内部错误           |

---

