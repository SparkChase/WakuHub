# 读取环境变量
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "waku-agent"
    APP_ENV: str = "dev"
    APP_DEBUG: bool = True

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "waku"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # 验证码
    CAPTCHA_LENGTH: int = 4          # 验证码位数
    CAPTCHA_TTL: int = 120           # 有效期（秒）
    CAPTCHA_KEY_PREFIX: str = "captcha:"  # Redis key 前缀

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "knowledge-docs"
    MINIO_SECURE: bool = False

    # Milvus
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "medical123"

    # 模型
    DASHSCOPE_API_KEY: str = ""
       # 聊天模型
    BASE_URL_CHAT: str = ""
    DEEPSEEK_API_KEY: str = ""
    CHAT_MODEL: str = "deepseek-chat"
    EMBEDDING_MODEL: str = "text-embedding-v3"
    VL_MODEL: str = "qwen-vl"

    LOG_LEVEL: str = "DEBUG"
    LOG_DIR: str = "logs"

    # JWT（JWT_SECRET_KEY 为敏感配置，生产必须放 .env 覆盖）
    JWT_SECRET_KEY: str = "dev-secret-change-in-prod-please-use-32-bytes-min"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 默认 1 天

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # 指定环境变量文件
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

# 保存到内存缓存中。以后直接获取。
@lru_cache  # lru 把对象实例保存到内存中。这是一种单例的实现
def get_settings() -> Settings:
    return Settings()
