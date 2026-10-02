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

## Docker 本地启动

在本目录运行：

```bash
docker compose up --build -d --wait
```

打开 **[http://localhost:8000/docs](http://localhost:8000/docs)** 查看并试用 API；[OpenAPI JSON](http://localhost:8000/openapi.json) 和 [健康检查](http://localhost:8000/healthz) 也可直接打开。Compose 会启动持久化 PostgreSQL、执行 Alembic 迁移，再启动 API。这个 `compose.yml` 仅供本机开发，API 只绑定 `127.0.0.1:8000`；`compose.test.yml` 是另一个可丢弃的测试库。

在 Swagger 的 **Try it out** 中先调用 `POST /api/auth/register`（用户名、至少 15 位密码、`adult_declared: true`），再调用 `GET /api/auth/csrf`；随后 `GET /api/tasks` 会显示新账号的空列表。后续写请求把取得的 token 填入 `X-CSRF-Token`。

若 8000 端口已被占用，可运行 `LOCAL_API_PORT=8001 LOCAL_APP_ORIGIN=http://localhost:8001 docker compose up --build -d --wait`，然后打开 `http://localhost:8001/docs`。

```bash
docker compose logs -f api       # 查看启动/请求日志；Ctrl-C 退出日志
docker compose down              # 停止，保留数据库数据
docker compose down -v           # 重置本地数据库，删除所有本地数据
```

默认不启动 Agent worker，浏览 `/docs`、认证和任务 API 不需要 MiMo 密钥。需要运行只读 Agent 时，把有效的 `MIMO_API_KEY` 放入本地 `.env`（已被 Git 和 Docker 构建忽略），再运行 `docker compose --profile agent up --build -d --wait`。没有有效密钥时 Agent run 会失败；阶段 4 的真实凭证验证仍待完成。

前端联调应让浏览器请求同源 `/api/...`：开发时在 Vite 配置 `/api` 代理，并用 `LOCAL_APP_ORIGIN=http://localhost:5173 docker compose up -d` 匹配前端页面 origin。当前 Vite 代理尚未实现；直接跨端口请求会遇到 CORS。生产环境需要同源 HTTPS 反向代理。详见[接入计划](../../frontend/docs/backend-api-data-model.md)。

## 不使用 Docker 开发

使用 Python 3.12/3.13、`uv sync --extra dev` 和独立 PostgreSQL。设置 `DATABASE_URL`、`APP_ORIGIN`、`CSRF_SECRET` 后依次运行 `uv run alembic upgrade head` 与 `uv run uvicorn assistant_backend.main:app --reload`。如需 Agent，再运行 `uv run python -m assistant_backend.worker`。`.env.example` 列出配置项；不要把真实密钥提交到仓库。

## 验证与部署前缺口

测试必须使用名称以 `_test` 结尾的独立可丢弃数据库：设置 `TEST_DATABASE_URL` 后运行 `uv run pytest -p no:cacheprovider -q`、`uv run ruff check .`、`uv run ruff format --check .`、`uv run alembic check`。更新实际路由后运行 `uv run python -m assistant_backend.export_contract`。`/healthz` 当前只证明 API 进程可响应，不检查数据库、worker 或模型。

生产部署仍需同源 HTTPS 代理、持久 PostgreSQL 与备份/恢复、迁移发布流程、独立 API 和 worker 进程、密钥注入、可信客户端 IP/限流配置、MiMo 凭证和预算验证。`APP_ENV=production` 时配置 HTTPS `APP_ORIGIN`、`__Host-` 会话 Cookie 名和独立的 32 字符以上 `CSRF_SECRET`；不要使用 `.env.example` 的示例值。仓库目前只有测试 compose，没有生产容器/代理配置。具体入口关口见[开发计划](docs/development-plan.md)。
