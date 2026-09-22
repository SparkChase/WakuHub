"""权限编码集中定义。

约定：code 命名为 `模块:操作`。这里登记的是「代码里会硬引用来守门的权限」，
不是「系统全部权限」——权限真相在 permissions 表（数据）。种子脚本负责把这里的
枚举灌进库，两者对齐。未来纯数据驱动、代码不引用的业务权限，可只存库不进此枚举。

StrEnum：成员值即字符串，PermCode.ROLE_MANAGE 可直接当 str 用（等于 "role:manage"）。
"""
from enum import StrEnum


class PermCode(StrEnum):
    # 权限管理：增删改权限、查看权限列表
    PERMISSION_MANAGE = "permission:manage"
    # 角色管理：增删改角色、给角色分配权限
    ROLE_MANAGE = "role:manage"
    # 用户管理：给用户分配角色等后台操作
    USER_MANAGE = "user:manage"


# code -> 中文名，供种子脚本写入 permissions.name 展示用
PERM_LABELS: dict[PermCode, str] = {
    PermCode.PERMISSION_MANAGE: "权限管理",
    PermCode.ROLE_MANAGE: "角色管理",
    PermCode.USER_MANAGE: "用户管理",
}
