"""MinIO 对象存储客户端，供知识库文档等文件上传/下载使用。

模块级单例：连接信息来自 Settings，客户端无状态可安全复用，无需每请求新建。
"""
import io

from minio import Minio
from loguru import logger

from src.core.config import get_settings

settings = get_settings()

# 模块级 MinIO 客户端单例
_minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)


def get_minio_client() -> Minio:
    """FastAPI 依赖注入用：返回模块级客户端单例"""
    return _minio_client


def ensure_bucket_exists() -> None:
    """确保业务桶存在，不存在则创建。应用启动时调用一次。"""
    exists = _minio_client.bucket_exists(settings.MINIO_BUCKET)
    logger.info(f"检查桶 {settings.MINIO_BUCKET} 是否存在：{exists}")
    if not exists:
        _minio_client.make_bucket(bucket_name=settings.MINIO_BUCKET)


def upload_file(
    object_name: str, data: bytes, content_type: str = "application/octet-stream"
) -> str:
    """上传字节流到业务桶，返回对象名（即存储路径）"""
    _minio_client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_name,
        data=io.BytesIO(data),
        content_type=content_type,
        length=len(data),
    )
    return object_name


def download_file(object_name: str) -> bytes:
    """从业务桶下载对象，返回字节流"""
    resp = _minio_client.get_object(
        bucket_name=settings.MINIO_BUCKET, object_name=object_name
    )
    try:
        return resp.read()
    finally:
        # get_object 返回的是流对象，读完必须关闭并归还连接，否则连接池会泄漏
        resp.close()
        resp.release_conn()


def delete_object(object_name: str) -> None:
    """从业务桶删除对象"""
    _minio_client.remove_object(
        bucket_name=settings.MINIO_BUCKET, object_name=object_name
    )
    logger.info(f"删除文件 {object_name} 成功")
