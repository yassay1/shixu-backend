# 拾序后端

当前阶段 1–3 已验收；阶段 4 可恢复 Agent 只读问答进行中。实际接口以 `contracts/openapi.json` 为准。

## 本地开发

1. 使用 Python 3.12 或 3.13，运行 `uv sync --extra dev`。
2. 复制 `.env.example` 为 `.env`，设置测试或开发数据库 URL、`APP_ORIGIN` 和独立 `CSRF_SECRET`。生产环境另设 HTTPS origin 与 `__Host-` Cookie 名。
3. 启动临时测试 PostgreSQL：`docker compose -f compose.test.yml up -d --wait`。它只创建 `shixu_test` 数据库，退出时可用 `docker compose -f compose.test.yml down` 清理。
4. 将 `DATABASE_URL` 设为 `postgresql+psycopg://shixu:shixu_test_password@127.0.0.1:55432/shixu_test`，运行 `uv run alembic upgrade head`；本地 API 可用 `uv run uvicorn assistant_backend.main:app` 启动。阶段 4 Agent worker 使用同一代码包另开终端运行 `uv run python -m assistant_backend.worker`。

测试使用独立可丢弃数据库；`TEST_DATABASE_URL` 必须指向名称以 `_test` 结尾的数据库。运行 `uv run pytest -p no:cacheprovider -q`、`uv run ruff check .`、`uv run alembic check`。更新路由后运行 `uv run python -m assistant_backend.export_contract`，使 OpenAPI 快照与实际应用一致。测试会清空该数据库中的身份表；不要将真实用户数据放入测试库。

生产部署预定在阿里云服务器，域名、代理和预算在部署阶段确认。LLM 使用小米 MiMo `mimo-v2.6-flash`；密钥通过后端 `.env`/Secret 注入，勿提交到仓库。按量费用硬上限需在小米控制台配置。
