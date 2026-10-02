# 拾序前后端接口设计

> 文档状态：已按用户名 + 密码、后端保存账号数据、任务和对话手动删除、永久删除、单 Agent/SSE 与首期语音草稿流程更新。MiMo 模型与阶段 4 限额/SSE 语义已冻结；语音供应商与上传限制待阶段 6 冻结。

## 1. 已确认的产品与接口边界

- 用户名 + 密码账号；开放自助注册。同账号跨设备共享任务、偏好和对话。首期不提供自助密码找回。认证和用户数据归属由后端确认；前端不发送 user_id，不保存 LLM 密钥或认证 token。
- 后端按已验证账号持久化任务、必要偏好、对话消息、提案和 Agent run。
- 服务端从空数据开始；不自动迁移或导入现有 xihack localStorage 演示数据。
- 用户可创建多个对话、查看并继续旧对话；对话保留到手动删除，不建立跨对话长期记忆或自动画像。
- 用户可单独手动删除任务和对话；删除对话不删除任务。首期不提供“一键删除全部账号数据”。
- Agent 查询可直接执行；所有任务写入（包括页面完成勾选）都生成待确认意图，用户确认后执行。
- 聊天采用两阶段 SSE：先提交消息创建 run 并返回 run_id，再订阅事件；run 状态接口负责断线恢复。
- LLM 使用小米 MiMo OpenAI 兼容 API 与 `mimo-v2.6-flash`；密钥仅通过后端环境变量或部署 Secret 配置。阶段 4 限额和 SSE 细节见第 6 节；部署美元预算另行配置。
- 训练暂缓，不进入本期 OpenAPI。语音采用录音结束后上传、可编辑草稿、用户手动发送流程。

## 2. API 总体结构

    React 前端 ── HTTPS JSON/SSE ── FastAPI
                                      ├─ Auth / Tasks / Conversations / Proposals API
                                      ├─ Agent Run API ── MiMo `mimo-v2.6-flash`
                                      ├─ Transcription API（若确认启用）
                                      └─ Application Use Cases ── PostgreSQL

浏览器携带服务端设置的 HttpOnly session Cookie。后端从会话解析 user_id。内部 Agent Tools 不是给浏览器公开调用的接口；它们与任务 API 复用 Application Use Cases。

建议静态前端和 API 同源部署。若分 origin，需要精确 CORS allowlist、带 credentials 的浏览器请求和 CSRF/Origin 防护；CORS 本身不是鉴权。

## 3. 账号认证 API

### 注册、登录、当前用户与退出

| 方法与路径 | 用途 |
|---|---|
| POST /api/auth/register | 公开自助注册用户名 + 密码账号；成功后创建登录会话并设置 Cookie |
| POST /api/auth/login | 验证用户名与密码；成功后轮换并设置会话 Cookie |
| GET /api/auth/me | 返回当前会话对应的用户公开资料 |
| POST /api/auth/logout | 撤销当前会话并清除 Cookie |
| GET /api/auth/csrf | 返回当前会话的 CSRF token；响应禁止缓存 |

请求示例：

    POST /api/auth/register
    {
      "username": "sample_user",
      "password": "user-entered-passphrase",
      "adult_declared": true
    }

登录/注册成功返回不敏感的用户资料，认证凭证放在 Set-Cookie，不放 JSON 响应正文：

    {
      "user": {
        "username": "sample_user"
      }
    }

生产 Cookie 使用 Secure、HttpOnly、SameSite=Strict、Path=/、`__Host-` 前缀且不设置 Domain。本阶段的注册、登录、退出严格核对 Origin；退出还校验 `X-CSRF-Token`。前端不能从 JavaScript 读取会话 Cookie。本阶段按同源部署，跨 origin 方案待部署阶段评审。

用户名为 3–32 位 ASCII 字母、数字或下划线，比较不区分大小写。密码为 15–128 字符，使用 Argon2id 哈希。注册必须声明已满 18 岁。具体规则见 [ADR 0002](./adr-0002-identity.md)。

登录错误统一返回不暴露账号是否存在的信息。注册与登录使用 PostgreSQL 固定窗口限流，阈值见 ADR 0002。首期不提供密码重置或自助找回接口；用户忘记密码后无法自行恢复账号。

user_id 仅为服务端内部标识，不需要暴露给前端；任何数据 API 都忽略客户端自带的 user_id 字段，并从已验证 Cookie 确定账号范围。

## 4. 账号偏好 API

| 方法与路径 | 用途 |
|---|---|
阶段 2 无已确认且必须跨任务保存的偏好字段，不开放 profile 接口；后续需求确认后再定义。

未来若引入偏好，只保存体验必需且由用户明确设置的值；不把模型推断的偏好当长期画像。

## 5. 任务 API

| 方法与路径 | 用途 |
|---|---|
| GET /api/tasks | 当前账号任务列表、筛选与分页 |
| GET /api/tasks/{task_id} | 当前账号任务详情 |

列表筛选建议支持 keyword、due_from、due_to、important、urgent、status、category、limit 与 cursor。所有查询强制叠加已认证 user_id 条件。

任务响应示例：

    {
      "task_id": "task_123",
      "title": "完成项目周报",
      "due": {"precision": "minute", "at": "2026-10-09T15:00:00+08:00", "timezone": "Asia/Shanghai"},
      "important": true,
      "urgent": false,
      "status": "open",
      "category": "学习",
      "version": 3
    }

task_id 由服务端生成。important 和 urgent 独立保存。`due` 可为 `null`、带日期与 IANA 时区的 `date`，或带分钟精度、UTC 偏移与 IANA 时区的 `minute`；仅日期不解释为午夜。任务状态为 `open`/`completed`，版本从 1 开始。更新字段省略表示不改，`description`、`category`、`due` 的 `null` 表示清空；标题和布尔字段不可置 `null`。所有写入通过第 6 节的统一提案确认，不开放直接任务写路由；当前数据库永久删除，无恢复 API。详见 [ADR 0003](./adr-0003-tasks-confirmation.md)。

## 6. 对话、消息与 SSE

### 对话管理

| 方法与路径 | 用途 |
|---|---|
| GET /api/conversations | 当前账号对话列表，含标题、更新时间、最近消息摘要 |
| POST /api/conversations | 新建空对话，不继承其他对话内容 |
| GET /api/conversations/{conversation_id} | 查看对话消息，供回看和续聊 |
| PATCH /api/conversations/{conversation_id} | 更新标题等允许的元数据 |
| DELETE /api/conversations/{conversation_id} | 手动删除此对话及消息、摘要、未完成提案与关联运行数据，不删除任务 |

阶段 3 对话管理契约：创建请求含必填 `client_request_id`（1–128 字符）与可选 `title`（默认“新对话”，去除首尾空格后长度 1–200）。同一账号重用相同请求 ID 和内容返回原对话；内容不同返回 409 `IDEMPOTENCY_CONFLICT`。创建、改标题、删除是需 Origin 与 CSRF 校验的写请求；同账号重复删除已不存在的 ID 返回 404。标题为空或超长返回 422。

`GET /api/conversations` 使用 `limit`（默认 20，范围 1–100）和不透明 `cursor`；按 `created_at DESC, conversation_id DESC` 排序，保证对话标题修改不会改变翻页位置。每项含最近消息正文的 160 字符摘要；没有消息时为 `null`。`GET /api/conversations/{conversation_id}` 用 `limit`（默认 50，范围 1–100）和 cursor 返回消息页，顺序为 `created_at ASC, message_id ASC`。创建新对话时消息为空，不复制其他会话内容。游标无效返回 422 `INVALID_REQUEST`。消息提交及 Agent run 见下方阶段 4 接口。

对话 ID 仅在当前账号范围内有效；跨账号读取、修改、删除统一返回 404。数据库以 `messages.conversation_id ON DELETE CASCADE` 清理消息；任务表不关联对话外键，删除对话不会删除任务。删除和并发消息插入由 PostgreSQL 外键锁与级联约束协调：插入若先提交，删除随后清理消息；删除若先提交，消息插入因父记录不存在而失败。阶段 4 的 Agent run/事件级联与 worker 最终写入复核见下方。

### 发送消息与运行状态

| 方法与路径 | 用途 |
|---|---|
| POST /api/conversations/{conversation_id}/messages | 原子保存用户消息并排队 Agent run，返回 202 |
| GET /api/runs/{run_id} | 读取当前账号 run 状态、最终可见回复及错误码 |
| GET /api/runs/{run_id}/events | 以 `text/event-stream` 订阅持久事件，支持 `Last-Event-ID` 或 `after` 序号续接 |

发送请求包含 `client_message_id`（1–128 字符）及 `content`（非空，最长 8000 字符），不接受 user_id。成功响应为 `{run_id,status,created_at,replayed}`。同一账号重用 message ID 且 conversation/content 相同，返回原 run；请求指纹不同返回 409 `IDEMPOTENCY_CONFLICT`。对话必须属于当前账号；消息和 run 在同一数据库事务中创建。只保存用户消息与最终助手可见回复，不保存 Tool 参数/返回值或模型内部推理。

消息 POST 校验 Origin 与 `X-CSRF-Token`。提交限流为每账号 10 次/小时、最多 2 个并发 run；每 IP 30 次/小时；全局 10 次/分钟。超限返回 429。每 run 最多 16 次模型请求、16 次只读 Tool 调用、180 秒、64K 输入与 8K 输出 tokens。金额硬上限另在供应商控制台配置，部署阶段再次核对。

事件按 run 单调递增序号持久化到 PostgreSQL；SSE `id` 与序号一致，断开连接不取消 run。事件仅含用户可见状态和回答片段：

    event: run.started
    data: {"run_id":"run_123","sequence":1}

    event: run.status
    data: {"phase":"searching_tasks","message":"正在查找相关事务","sequence":2}

    event: message.delta
    data: {"text":"找到了两条可能相关的事务。","sequence":3}

    event: run.status
    data: {"phase":"answering","sequence":4}

    event: run.completed
    data: {"run_id":"run_123","assistant_message_id":"message_456","sequence":5}

阶段 4 事件类型：`run.status`（`queued`、`thinking`、`searching_tasks`、`answering`）、`run.started`、`message.delta`、`run.completed`、`run.failed`、`run.snapshot`。事件最多保留 7 天；游标早于仍保留的最早序号时先发 `run.snapshot`（含当前状态、最终回复和最新序号），随后从该序号继续。游标无效返回 422。`GET /api/runs/{run_id}` 可在任何时候读取当前状态。跨账号 run ID 统一 404。

Worker 由 `uv run python -m assistant_backend.worker` 启动，使用数据库 lease 与 `SKIP LOCKED` 领取 queued run。重启后 queued run 可继续领取；lease 过期的 in-progress run 收敛为 `failed/WORKER_INTERRUPTED`，不重放可能已经计费的模型调用。失败时保留用户消息并提供安全错误码。对话永久删除通过外键级联清理 run/event/message；worker 每次写事件或助手回复前锁定并复核对话仍存在，防止删除后复活数据；任务表不关联对话，任务不会被删除。阶段 4 没有显式取消 run API，SSE 断开仅停止订阅。

### 提案 API

| 方法与路径 | 用途 |
|---|---|
| POST /api/proposals | 保存手动创建、更新、完成或删除任务的待确认意图，不修改任务 |
| GET /api/proposals/{proposal_id} | 读取当前账号提案预览与状态 |
| POST /api/proposals/{proposal_id}/confirm | 用户确认并执行提案 |
| POST /api/proposals/{proposal_id}/cancel | 用户取消提案 |

阶段 2 的手动提案请求含 `client_request_id`、`operation`（`create`/`update`/`complete`/`delete`）；创建提供 `task`，更新提供 `task_id`、`expected_version`、`changes`，完成与删除提供 `task_id`、`expected_version`。同账号重用 `client_request_id` 且内容相同返回同一提案，不同则 409。确认 JSON 正文携带 `idempotency_key`；同一键重复确认返回原回执，异键返回 409。提案 15 分钟有效，确认时重查归属、状态、期限和任务版本，删除会使该任务其他待确认提案失效。手动提案不带 conversation_id；Agent 接入留到阶段 5。所有提案写请求校验 Origin 和 `X-CSRF-Token`，账号来自 Cookie。LLM 输出提案不表示事务已经写入；只有提交成功的数据库回执才能作为成功响应。

## 7. 内部 Agent Tools

首期候选 Tool：

- search_tasks(filters, limit, cursor)：只读检索当前账号任务。
- get_task(task_id)：只读读取当前账号任务及最新版本。

写入能力经 create/update/complete/delete Application Use Cases 提供，但模型只生成结构化提案。用户确认 API 才能触发实际用例。模型输入字段不得包含 user_id；Tool 参数经 schema、字段 allowlist、长度、时间范围、归属和业务规则校验。每个 run 限制轮数、总时长和 token 用量。

## 8. 语音与训练接口

### 语音转写（首期已确认流程）

推荐的首期用户体验是录音结束后上传音频、后端转写并逐步显示处理结果、用户编辑后再明确发送。上传结束后才能开始显示后端转写文本；这不是边说边出字。

| 方法与路径 | 用途 |
|---|---|
| POST /api/transcriptions | multipart/form-data 上传音频并创建 transcription run，返回 202 和 transcription_id |
| GET /api/transcriptions/{transcription_id}/events | SSE 返回转写状态与可用文本片段 |
| GET /api/transcriptions/{transcription_id} | 断线恢复转写状态与最终文本 |

转写完成不会自动创建 Agent 对话消息。音频仅临时处理，完成或失败后清理；格式、大小、时长、并发、超时、用量和用户告知在阶段 6 冻结。用户可编辑草稿后明确发送文本；实时音频不在首期流程内。

### 训练

训练模块首期暂缓，不进入 OpenAPI。未来是否增加 /api/training/ 由单独产品与接口评审决定。

## 9. 错误、限流与隐私

统一错误结构包含 code、message、request_id、可选 details 和 retryable。建议错误码：

- AUTH_REQUIRED：未登录或会话失效。
- AUTH_INVALID：用户名或密码验证失败；文案不透露具体哪一项错误。
- REGISTRATION_UNAVAILABLE：注册不能完成；使用通用提示，避免泄漏用户名是否已注册。
- FORBIDDEN / NOT_FOUND：对象不属于当前账号时建议统一成 NOT_FOUND，避免泄露他人数据。
- INVALID_REQUEST、VERSION_CONFLICT、PROPOSAL_EXPIRED、RATE_LIMITED。
- MODEL_UNAVAILABLE、MODEL_OUTPUT_INVALID、RUN_FAILED、TRANSCRIPTION_FAILED。

公开服务对注册、登录、任务 API、Agent Tool 轮次、文件上传、并发、响应时长和 LLM 费用设置分层限额。超出预算时停止模型调用并返回清晰、可恢复提示。

LLM 密钥仅由后端环境变量或部署 Secret 提供。通用日志只存 request_id、路由、状态、耗时与用量等元数据；不要记录密码、Cookie、会话 token、完整 prompt、任务正文、对话正文或音频。

## 10. 后续冻结项

- 多设备会话列表和其他设备主动注销界面。
- 跨 origin 部署若需要 CORS，须另行冻结精确来源；当前按同源 Origin 校验。
- 语音转写 provider、音频上限、临时保留与费用告知。
- SSE 事件 schema、保留期限、重连行为和 run 取消策略。
- LLM 供应商、项目预算及账号/IP/全局调用限额。
