"""用户权限缓存（Cache-Aside 模式）。

背景：每次受保护请求都要 解析 JWT → 查 users → selectin 加载 roles → selectin 加载
permissions，至少 3 次 DB 查询。用户量大 / 多机部署时开销显著。

方案：把「用户的权限 code 集合 + 是否超管」缓存到 Redis，多机共享同一份缓存。
读路径走 Cache-Aside：先查缓存，命中直接用；未命中回源 DB 并回填缓存。

缓存内容按 user_id 存一个 JSON：{"is_superuser": bool, "perms": [code, ...]}。
写路径（分配角色 / 改角色权限）负责失效对应缓存，配合 TTL 兜底。
"""
import json

from redis.asyncio import Redis

from src.core.config import get_settings
from src.modules.user.model import User

settings = get_settings()


class PermissionCache:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _key(self, user_id: int) -> str:
        return f"{settings.RBAC_CACHE_PREFIX}{user_id}"

    # 从 ORM User 抽取要缓存的最小数据：超管标记 + 扁平化的权限 code 集合
    @staticmethod
    def _extract(user: User) -> dict:
        perms = {p.code for role in user.roles for p in role.permissions}
        return {"is_superuser": user.is_superuser, "perms": sorted(perms)}

    # 读缓存：命中返回 dict，未命中返回 None（区别于"命中但空权限"）
    async def get(self, user_id: int) -> dict | None:
        raw = await self.redis.get(self._key(user_id))
        if raw is None:
            return None
        return json.loads(raw)

    # 写缓存：从 ORM User 抽取数据，序列化后带 TTL 存入
    async def set(self, user: User) -> dict:
        data = self._extract(user)
        await self.redis.set(
            self._key(user.id), json.dumps(data), ex=settings.RBAC_CACHE_TTL
        )
        return data

    # 失效单个用户：其角色变更时调用
    async def invalidate(self, user_id: int) -> None:
        await self.redis.delete(self._key(user_id))

    # 失效全部：某角色的权限被改动时，持有该角色的用户可能有多个且难以枚举，
    # 角色权限变更又是低频管理操作，故直接按前缀清空整个 rbac 缓存，靠回源重建
    async def invalidate_all(self) -> None:
        async for key in self.redis.scan_iter(match=f"{settings.RBAC_CACHE_PREFIX}*"):
            await self.redis.delete(key)
