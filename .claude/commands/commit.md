---
description: 根据当前 diff 生成规范的 Conventional Commits 提交
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git commit:*)
argument-hint: [可选的提交说明或范围提示]
---

根据当前改动生成一次符合 Conventional Commits 规范的提交。用户附加说明：$ARGUMENTS

## 上下文

- 当前状态：!`git status --short`
- 已暂存改动：!`git diff --cached --stat`
- 未暂存改动：!`git diff --stat`
- 最近提交风格参考：!`git log --oneline -10`

## 执行步骤

1. **确定暂存范围**
   - 若已有暂存内容，只提交暂存的改动，不擅自 `git add` 其它文件。
   - 若没有任何暂存内容，先看整体改动，把逻辑上属于一次变更的文件用 `git add <具体文件>` 暂存；不要用 `git add .` 无脑全加。
   - 若改动跨越多个不相关的关注点，提示用户是否需要拆成多次提交，而不是硬塞进一个 commit。

2. **阅读实际 diff**：用 `git diff --cached` 看清楚改了什么，基于内容判断类型和影响，不要只看文件名猜。

3. **生成 commit message**，格式：

   ```
   <type>(<scope>): <subject>

   <body 可选>
   ```

   - **type** 从以下选取：
     - `feat` 新功能
     - `fix` 修复 bug
     - `docs` 文档
     - `style` 格式（不影响逻辑）
     - `refactor` 重构（非功能非修复）
     - `perf` 性能优化
     - `test` 测试
     - `build` 构建 / 依赖（含 `uv add`、`pyproject.toml`、`uv.lock`）
     - `ci` CI 配置
     - `chore` 杂项（脚手架、配置、工具链）
     - `revert` 回滚
   - **scope**：受影响的模块，如 `core`、`infra`、`middleware`、`config`、`db`、`api`、`deps`。单文件小改可省略。
   - **subject**：英文，祈使句现在时，小写开头，不加句号，≤ 50 字符。
   - **body**：改动较复杂时补充“为什么这么改”，每行 ≤ 72 字符；简单改动可省略。
   - 破坏性变更加 `BREAKING CHANGE:` 脚注或在 type 后加 `!`。

4. **提交前确认**：先展示将要执行的完整 commit message 和涉及的文件清单，让我确认后再执行 `git commit`。

5. **执行提交**：用 `git commit -m "..." -m "..."` 传多段 message，不使用交互式编辑器。

## 约束

- 只做提交，不 `git push`。
- 不修改 git config，不用 `--amend`（除非我明确要求）。
- 遇到 `.env`、密钥、证书等敏感文件出现在暂存区时，先警告我再继续。
- commit message 一律英文。
