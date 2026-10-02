# 拾序后端

FastAPI + PostgreSQL 单体。当前已实现账号会话、任务只读与提案确认写入、多对话、消息/run/SSE 和只读任务 Agent。实际已发布路径见 [`contracts/openapi.json`](contracts/openapi.json)；[前后端交接](docs/frontend-backend-handoff.md)有请求示例。阶段 4 的真实 MiMo 凭证 smoke test 尚未通过，不能把 Agent 标为生产可用。

## 当前边界

| 能力 | 状态 |
|---|---|
| 账号、CSRF、任务列表/详情、手动提案/确认/取消、对话历史 | 代码与契约已存在 |
| 消息、Agent run、SSE、只读任务 Tool | 代码与测试已存在；真实 provider 凭证验证待完成 |
| Agent 生成任务写入提案 | 阶段 5，尚未实现 |
| 前端本地语音转写、后端文字校准/业务核验 | 阶段 6，尚未实现；默认不上传音频，见 [ADR 0004](docs/adr-0004-local-voice.md) |
| 训练 API / 眼动 | 不在后端范围；前端保留经典 5×5 舒尔特表 |

## 本地运行

1. 使用 Python 3.12 或 3.13，运行 `uv sync --extra dev`。
2. 复制 `.env.example` 为 `.env`，设置独立的 `CSRF_SECRET`、`DATABASE_URL`、`APP_ORIGIN`。本地数据库可使用 `docker compose -f compose.test.yml up -d --wait`，但该 compose 创建的是可丢弃的 `shixu_test` 测试库，不能用于真实数据或部署。
3. 将 `DATABASE_URL` 指向该库（本地 compose 为 `postgresql+psycopg://shixu:shixu_test_password@127.0.0.1:55432/shixu_test`），运行 `uv run alembic upgrade head`。
4. 启动 API：`uv run uvicorn assistant_backend.main:app --reload`。只读 Agent 还需单独启动 `uv run python -m assistant_backend.worker`，并在服务端配置有效的 `MIMO_API_KEY`。缺少密钥时消息/run 可创建，但模型调用会失败。

前端首个联调切片是登录与任务列表：浏览器调用同源 `/api/auth/me`、注册/登录、`/api/auth/csrf`、`/api/tasks`。当前后端没有 CORS 中间件，前端 Vite 也没有 `/api` 代理；从另一个端口直接调用 API 不能当作可用浏览器方案。开发时新增 Vite `/api` 代理并将 `APP_ORIGIN` 设置为页面 origin；部署时由同源 HTTPS 反向代理转发 `/api`。详见[接入计划](../../frontend/docs/backend-api-data-model.md)。

## 验证与部署前缺口

测试必须使用名称以 `_test` 结尾的独立可丢弃数据库：设置 `TEST_DATABASE_URL` 后运行 `uv run pytest -p no:cacheprovider -q`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run alembic check`。更新实际路由后运行 `uv run python -m assistant_backend.export_contract`。`/healthz` 当前只证明 API 进程可响应，不检查数据库、worker 或模型。

生产部署仍需同源 HTTPS 代理、持久 PostgreSQL 与备份/恢复、迁移发布流程、独立 API 和 worker 进程、密钥注入、可信客户端 IP/限流配置、MiMo 凭证和预算验证。`APP_ENV=production` 时配置 HTTPS `APP_ORIGIN`、`__Host-` 会话 Cookie 名和独立的 32 字符以上 `CSRF_SECRET`；不要使用 `.env.example` 的示例值。仓库目前只有测试 compose，没有生产容器/代理配置。具体入口关口见[开发计划](docs/development-plan.md)。
