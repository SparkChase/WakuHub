from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.database import get_db
from src.core.base_schema import ResponseSchema
from src.modules.auth.schema import LoginRequest, TokenResponse
from src.modules.auth.service import AuthService
from src.modules.user.schema import UserCreate, UserRead
from src.modules.user.service import UserService
from src.modules.captcha.api import get_captcha_service
from src.modules.captcha.service import CaptchaService
from src.utils.jwt import JWTHelper

router = APIRouter(prefix="/auth", tags=["Auth"])

# 从 Authorization: Bearer <token> 头里取 token；tokenUrl 指向登录接口，供 Swagger 授权用
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


# 鉴权依赖：从 token 解析出当前登录用户，供受保护接口用 Depends(get_current_user)
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    svc: UserService = Depends(get_user_service),
) -> UserRead:
    payload = JWTHelper.decode_token(token)
    user = await svc.get_user(int(payload["sub"]))
    return UserRead.model_validate(user)


# POST /auth/register  注册
@router.post("/register", response_model=ResponseSchema[UserRead])
async def register(
    data: UserCreate,
    svc: UserService = Depends(get_user_service),
):
    user = await svc.create_user(data)
    return ResponseSchema[UserRead](data=UserRead.model_validate(user))


# POST /auth/login  登录：先校验验证码，再校验密码，返回 JWT
@router.post("/login", response_model=ResponseSchema[TokenResponse])
async def login(
    data: LoginRequest,
    svc: AuthService = Depends(get_auth_service),
    captcha_svc: CaptchaService = Depends(get_captcha_service),
):
    # 先验验证码：错误直接拒，避免拿登录接口暴力刷密码
    await captcha_svc.verify(data.captcha_key, data.captcha_code)
    token = await svc.login(data)
    return ResponseSchema[TokenResponse](data=token)


# GET /auth/me  当前登录用户信息（受保护，需 Bearer token）
@router.get("/me", response_model=ResponseSchema[UserRead])
async def read_me(
    current_user: UserRead = Depends(get_current_user),
):
    return ResponseSchema[UserRead](data=current_user)
