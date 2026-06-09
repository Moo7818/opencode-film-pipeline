# API 接口说明

## 接口概览

所有模型统一使用 `POST /v1/api/generate`（replyType=async），通过 `GET /v1/api/result?id=xxx` 轮询结果。

| 接口 | 方法 | 说明 |
|---|---|---|
| `/v1/api/generate` | POST | 图像生成（replyType=async） |
| `/v1/api/result` | GET | 结果查询（`?id=xxx`） |

## 图像生成

**POST /v1/api/generate**

请求头：
- `Authorization: Bearer {api_key}`
- `Content-Type: application/json`
- `oss-id`（可选，云存储 ID）
- `oss-path`（可选，云存储路径）

请求体：
```json
{
  "model": "gpt-image-2-vip",
  "prompt": "生成提示词",
  "replyType": "async",
  "aspectRatio": "1024x1024",
  "images": ["https://example.com/ref.png"]
}
```

响应：
```json
{
  "id": "task_xxx",
  "status": "running"
}
```

## 结果查询

**GET /v1/api/result?id=xxx**

请求头：
- `Authorization: Bearer {api_key}`

响应状态值：
| 状态 | 说明 |
|------|------|
| `running` | 进行中 |
| `succeeded` | 生成成功 |
| `failed` | 任务失败 |
| `violation` | 违规 |

成功响应：
```json
{
  "status": "succeeded",
  "results": [{"url": "https://...", "oss_url": "https://..."}]
}
```

## 验证运行时配置

不确定当前生效的默认模型？运行：

```bash
python -c "from script.config import get_model; print(get_model())"
```

配置文件位于 `~/.trae-cn/media_gen_config.json`，格式示例：

```json
{
  "GRSAI_MODEL": "gpt-image-2",
  "GRSAI_API_KEY": "sk-xxx..."
}
```

## 凭证加载

优先级：环境变量 > `~/.trae-cn/media_gen_config.json`

| 变量 | 默认值 | 说明 |
|---|---|---|
| `GRSAI_API_KEY` | （必填） | API 密钥 |
| `GRSAI_API_HOST` | `https://grsai.dakka.com.cn` | API 服务地址 |
| `GRSAI_MODEL` | `gpt-image-2` | 默认模型 |
| `GRSAI_OSS_ID` | （空） | 云存储 ID |
| `GRSAI_OSS_PATH` | （空） | 云存储路径 |
| `TENCENT_COS_SECRET_ID` | （空） | 腾讯云 COS（本地参考图上传） |
| `TENCENT_COS_SECRET_KEY` | （空） | |
| `TENCENT_COS_BUCKET` | （空） | |
| `TENCENT_COS_REGION` | （空） | |