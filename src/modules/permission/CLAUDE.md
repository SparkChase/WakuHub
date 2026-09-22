# RBAC 权限模块

user ─(user_roles)─ role ─(role_permissions)─ permission，两张多对多关联表。
用户的权限 = 其所有角色的权限并集。超级管理员（`user.is_superuser`）无视权限检查。

## 模块分布

- `permission/` — 权限的 CRUD（本模块）
- `role/` — 角色 CRUD + 给角色分配权限（`PUT /roles/{id}/permissions`，全量覆盖）
- `user/` — 给用户分配角色（`PUT /users/{id}/roles`，全量覆盖）
- `auth/deps.py` — `get_current_user` / `get_current_perms` / `require_permission`（鉴权 + 鉴权依赖）
- `auth/cache.py` — 用户权限缓存（Cache-Aside）
- `core/permissions.py` — `PermCode` 枚举，登记代码里硬引用的权限编码

## 权限编码 PermCode

`code` 命名约定 `模块:操作`（如 `role:manage`）。集中定义在 `core/permissions.py`：

```python
class PermCode(StrEnum):
    PERMISSION_MANAGE = "permission:manage"
    ROLE_MANAGE = "role:manage"
    USER_MANAGE = "user:manage"
```

用 `StrEnum`：成员值即字符串，`PermCode.ROLE_MANAGE` 可直接当 `"role:manage"` 用。
IDE 可补全、拼错编译期暴露、改名一处生效。

**边界**：枚举登记的是「代码里会硬引用来守门的权限」，不是「系统全部权限」。
权限真相在 `permissions` 表（数据）。纯数据驱动、代码不 import 的业务权限可只存库、不进枚举。

## 给接口挂权限保护

用 `dependencies`（只守门、不把返回值传给函数）：

```python
@router.post(
    "",
    response_model=ResponseSchema[RoleRead],
    dependencies=[Depends(require_permission(PermCode.ROLE_MANAGE))],
)
async def create_role(...): ...
```

`require_permission` 链路：解析 token 拿 user_id → `get_current_perms` 取权限数据
（走缓存，见下）→ 超管放行 → 否则目标 code 不在权限集合 → 抛 403。

## 权限缓存（Cache-Aside）

问题：每次受保护请求都要 解析 JWT → 查 users → selectin roles → selectin permissions，
至少 3 次 DB 查询。用户量大 / 多机部署时开销显著（多机还需共享同一份权限视图）。

方案：`auth/cache.py` 把「用户权限 code 集合 + 是否超管」按 `rbac:perms:{user_id}` 存 Redis。

- **读**（`get_current_perms`）：先查缓存，命中直接用；未命中回源 DB 并回填缓存（带 TTL 兜底）
- **写失效**：
  - 给用户分配角色 → `invalidate(user_id)`，只失效该用户
  - 改角色权限 / 删角色 → `invalidate_all()`，持有该角色的用户难枚举且属低频操作，
    直接按前缀清空整个 rbac 缓存，靠回源重建

缓存值：`{"is_superuser": bool, "perms": [code, ...]}`。TTL 由 `RBAC_CACHE_TTL` 配置。
只需完整用户信息（非权限校验）的接口仍用 `get_current_user` 直接查库。

实测（同一受保护接口连续两次请求，统计底层 SQL SELECT 次数）：
首次冷启动 miss 走 DB 共 4 次 SELECT（user + roles + permissions + 业务查询）；
二次命中缓存降到 1 次（仅剩业务本身的查询），权限校验部分省掉 3 次 DB 查询。

## 初始化（破解自锁死）

管理接口挂保护后，库里若没人持有权限就没人能授权，系统自锁死。
靠种子脚本直接写库造第一个超管（无视权限检查）：

```bash
alembic upgrade head                                              # 建表
SEED_ADMIN_PASSWORD='xxx' uv run python scripts/seed_rbac.py      # 造超管 + 灌基础权限
```

脚本幂等（权限按 code、超管按 username 判重），密码从 `SEED_ADMIN_PASSWORD` 读，不硬编码。

## 新增一个受保护接口的步骤

1. 若需新权限：在 `PermCode` 加成员 + `PERM_LABELS` 加中文名
2. 路由 `dependencies` 挂 `Depends(require_permission(PermCode.XXX))`
3. 重跑种子脚本把新权限灌进库（幂等，只补新增的）
4. 用 admin 登录 → 建角色分配该权限 → 给用户分配角色
