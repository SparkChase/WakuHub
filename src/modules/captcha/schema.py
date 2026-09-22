from pydantic import BaseModel, Field


class CaptchaResponse(BaseModel):
    """生成验证码的返回：前端拿 key 保存，img 直接塞进 <img src>。"""
    key: str = Field(description="验证码标识，校验时回传")
    img: str = Field(description="图片 base64，格式 data:image/png;base64,...")


class CaptchaVerify(BaseModel):
    """校验验证码的请求。"""
    key: str = Field(description="生成时拿到的 key")
    code: str = Field(description="用户输入的验证码")
