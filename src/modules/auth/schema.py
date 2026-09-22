from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    captcha_key: str   # GET /captcha 返回的 key
    captcha_code: str  # 用户输入的验证码


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
