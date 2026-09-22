# WakuHub

## 使用 uv 管理项目依赖

### 安装 uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装完成后验证：

```bash
uv --version
```

### 克隆项目并安装依赖

```bash
# 克隆仓库
git clone <仓库地址>
cd WakuHub

# uv 会自动根据 pyproject.toml 和 uv.lock 创建虚拟环境并安装依赖
uv sync
```

`uv sync` 会自动：
1. 读取 `.python-version` 确定 Python 版本（本项目为 3.13）
2. 创建 `.venv` 虚拟环境
3. 根据 `uv.lock` 安装完全一致的依赖版本

### 运行项目

```bash
uv run main.py
```

### 添加新依赖

```bash
# 添加运行依赖
uv add <包名>

# 添加开发依赖（如测试、lint 工具）
uv add --dev <包名>

# 移除依赖
uv remove <包名>
```

添加后 `uv.lock` 会自动更新，提交代码时需一同提交。

### 常用命令速查

| 命令 | 说明 |
|------|------|
| `uv sync` | 同步安装所有依赖 |
| `uv run <脚本>` | 在虚拟环境中运行脚本 |
| `uv add <包>` | 添加依赖 |
| `uv remove <包>` | 移除依赖 |
| `uv pip list` | 查看已安装的包 |
| `uv python pin 3.13` | 锁定 Python 版本 |

### 环境变量

项目使用 `.env` 文件管理环境变量（已在 `.gitignore` 中排除）。复制模板并填入你的配置：

```bash
cp .env.example .env
```

### 常见问题

**Q: `uv sync` 报 Python 版本不存在？**
A: uv 会自动下载对应版本的 Python，确保网络通畅。也可手动安装 Python 3.13。

**Q: 如何更新依赖？**
A: 运行 `uv lock --upgrade` 更新锁文件，再 `uv sync` 安装。

**Q: `.venv` 和 `uv.lock` 需要提交吗？**
A: `.venv` 不需要（已在 `.gitignore` 中），`uv.lock` 需要提交以保证团队依赖一致。


cd docker
docker compose -f docker-compose.yaml up -d 


fastapi dev src/main.py

alembic init -t async alembic 

后续流程：
每次修改Model
# 1.生成前一文件
alembic revision --autogenerate -m "描述本次变更"

# 2.检查生活的迁移文件（在alembic/versions/ 下）

# 3.迁移文件
alembic upgrade 

# 其他常用命令
alembic downgrade -1 
alembic current
alembic history
