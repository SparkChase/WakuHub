"""RBAC 种子脚本：初始化基础权限 + 超级管理员账号。

解决"先有鸡还是先有蛋"：管理接口挂了 require_permission 后，库里若没人持有对应
权限，就没人能创建角色/分配权限，系统自锁死。故用脚本直接写库绕过接口，
造出第一个 is_superuser=True 的账号（它无视权限检查，可放行一切）。

用法：
    uv run python scripts/seed_rbac.py

幂等：权限按 code、超管按 username 判重，重复执行不会造成重复数据。
超管密码从环境变量 SEED_ADMIN_PASSWORD 读，未设置则报错退出（不硬编码默认密码）。
"""
import asyncio
import os
import sys

from sqlalchemy import select

from src.core.permissions import PERM_LABELS
from src.infra.database import AsyncSessionLocal
from src.modules.permission.model import Permission
from src.modules.user.model import User
from src.utils.password import PasswordHasher

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@wakuhub.local"


async def seed() -> None:
    # 超管密码只从环境变量取，缺失直接退出，避免脚本里出现明文默认密码
    password = os.getenv("SEED_ADMIN_PASSWORD")
    if not password:
        print("请先设置环境变量 SEED_ADMIN_PASSWORD，再运行本脚本", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        # 1. 灌入基础权限：遍历 PermCode 枚举，按 code 判重后插入
        for code, label in PERM_LABELS.items():
            existing = await db.execute(
                select(Permission).where(Permission.code == code)
            )
            if existing.scalar_one_or_none():
                print(f"权限已存在，跳过: {code}")
                continue
            db.add(Permission(code=str(code), name=label))
            print(f"创建权限: {code} ({label})")

        # 2. 创建超级管理员：按 username 判重
        existing = await db.execute(
            select(User).where(User.username == ADMIN_USERNAME)
        )
        if existing.scalar_one_or_none():
            print(f"超管已存在，跳过: {ADMIN_USERNAME}")
        else:
            db.add(
                User(
                    username=ADMIN_USERNAME,
                    email=ADMIN_EMAIL,
                    hashed_password=PasswordHasher.hash(password),
                    is_superuser=True,
                )
            )
            print(f"创建超级管理员: {ADMIN_USERNAME}")

        # 3. 一次性提交
        await db.commit()
    print("种子数据初始化完成")


if __name__ == "__main__":
    asyncio.run(seed())
