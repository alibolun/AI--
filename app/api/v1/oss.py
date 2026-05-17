import alibabacloud_oss_v2 as oss
from fastapi import APIRouter, HTTPException
from datetime import timedelta
import os
# 加载环境变量
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()

# OSS 域名配置
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "oss-cn-beijing.aliyuncs.com")
OSS_BUCKET = os.getenv("OSS_BUCKET")

# 延迟初始化 OSS 客户端
_client = None

def get_oss_client():
    global _client
    if _client is None:
        try:
            # 从环境变量中加载凭证信息，用于身份验证
            credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
            
            # 加载SDK的默认配置，并设置凭证提供者
            cfg = oss.config.load_default()
            cfg.credentials_provider = credentials_provider
            
            # 方式一：只填写Region（推荐）
            # 必须指定Region ID，SDK会根据Region自动构造HTTPS访问域名
            cfg.region = 'cn-beijing'
            
            # 使用配置好的信息创建OSS客户端
            _client = oss.Client(cfg)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"OSS 初始化失败: {str(e)}")
    return _client


@router.get("/oss/presign")
def chat_endpoint(filename: str):
    # 根据文件扩展名判断 Content-Type
    content_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
    content_type = content_type_map.get(ext, "application/octet-stream")

    client = get_oss_client()
    
    if not OSS_BUCKET:
        raise HTTPException(status_code=500, detail="OSS_BUCKET 环境变量未设置")
    
    pre_result = client.presign(oss.PutObjectRequest(
        bucket=OSS_BUCKET,
        key=filename,
        content_type=content_type,
    ), expires=timedelta(seconds=3600))

    # 返回上传 URL 和可访问的图片路径
    return {
        "uploadUrl": pre_result.url.strip('"'),
        "contentType": content_type,
        "accessUrl": f"https://{OSS_BUCKET}.{OSS_ENDPOINT}/{filename}"
    }
