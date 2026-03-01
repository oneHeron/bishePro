# 远程 GPU Worker 架构说明（RQ/Redis 方案）

本文解释当前项目推荐的远程算力方案：
- API 机只负责接收请求、入库、入队
- 远程 GPU 机部署同版本代码，消费自己的队列并执行算法
- 结果和日志回写到同一数据库
- 前端继续轮询现有接口，无需改交互模型

## 1. 为什么采用这个方案

相比“API 机直接 SSH 到远程主机执行”：
- 不需要在 API 服务中维护大量 SSH 会话与私钥
- 扩展多台 GPU 机器更简单（每台机器一个/多个 worker）
- 失败重试、重启恢复、队列可观测性更好
- 与当前代码基线最兼容（项目已内置 RQ/Redis）

## 2. 组件与职责

1. API 服务（FastAPI）
- 接收 `POST /runs`
- 写入 `runs` 表（`pending`）
- 根据方法/参数选择队列并 `enqueue`

2. Redis
- 作为任务队列中间件

3. Worker（RQ worker）
- 从指定队列取任务
- 执行 `execute_run_job(run_id)` -> `_run_pipeline(run_id)`
- 运行算法并更新数据库状态/日志/结果

4. 数据库（当前 SQLite，可替换为 MySQL/PostgreSQL）
- 统一保存 run 状态、日志、指标和结果

5. 前端（Vue）
- 继续调用 `GET /runs/{id}` 与 `GET /runs/{id}/results`
- 展示状态、日志、运行设备、指标结果

## 3. 数据流（端到端）

```text
Browser
  -> POST /runs (method,dataset,params,run_mode,remote)
API
  -> insert runs(status=pending)
  -> resolve queue name (cpu/gpu/remote-*-gpu)
  -> enqueue run_id to Redis queue
Worker (remote GPU host)
  -> dequeue run_id
  -> set status=running
  -> run method subprocess in conda env
  -> write logs + metrics + results + runtime info
  -> set status=finished/failed/cancelled
Browser
  -> poll GET /runs/{id}, /results
  -> render final result
```

## 4. 队列路由规则（当前实现）

后端核心逻辑在：
- `backend/app/runner/mock_runner.py::_resolve_rq_queue_name`

### 4.1 单队列兼容模式（不破坏旧行为）
如果未设置 `RUN_QUEUE_CPU` 和 `RUN_QUEUE_GPU`：
- 所有任务继续进入 `RUN_QUEUE`（默认 `runs`）

### 4.2 本地 CPU/GPU 分流
如果设置了：
- `RUN_QUEUE_CPU=cpu`
- `RUN_QUEUE_GPU=gpu`

则：
- `use_gpu=true` 或 `method.requires_gpu=true` -> `gpu`
- 否则 -> `cpu`

### 4.3 远程模式队列
当前前端 `Run` 页选择 `Remote Server (Beta)` 且填写 `remote.ip` 时：
- CPU：`remote-<ip-normalized>-cpu`
- GPU：`remote-<ip-normalized>-gpu`

例如 `192.168.1.100`：
- `remote-192-168-1-100-cpu`
- `remote-192-168-1-100-gpu`

可通过环境变量覆盖模板：
- `RUN_QUEUE_REMOTE_CPU`（支持 `{target}` 占位符）
- `RUN_QUEUE_REMOTE_GPU`（支持 `{target}` 占位符）

## 5. 状态流转与日志回写

状态流：
- `pending` -> `running` -> `finished`
- 异常：`failed`
- 用户取消：`cancelled`

日志会持续写入 `run.logs`，包含：
- 数据准备
- 调度到哪个 conda env
- runtime 设备决策（requested/actual）
- 结束状态

结果写入 `run.results`，包括：
- `metrics`
- `community_assignment`
- `viz`（小图）
- `runtime`（framework/requested/actual/fallback 等）

## 6. 远程部署步骤（最小可用）

> 前提：API 服务机与远程 worker 机器可访问同一个 Redis，且共享同一个数据库。

### 6.1 API 机

```bash
cd backend
export RUNNER_BACKEND=rq
export REDIS_URL=redis://<redis-host>:6379/0
export RUN_QUEUE_CPU=cpu
export RUN_QUEUE_GPU=gpu
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 6.2 远程 GPU 机（示例 IP=192.168.1.100）

```bash
cd backend
conda activate bsenv
export REDIS_URL=redis://<redis-host>:6379/0
python -m rq worker remote-192-168-1-100-gpu
```

如果还希望它处理该机器的 CPU 任务：

```bash
python -m rq worker remote-192-168-1-100-cpu
```

### 6.3 可选：本地 CPU worker

```bash
cd backend
conda activate bsenv
export REDIS_URL=redis://<redis-host>:6379/0
python -m rq worker cpu
```

## 7. 你最关心的问题

### Q1：结果怎么回到前端？
不是从远程机器“直接回前端”。
- worker 执行后写回数据库
- 前端继续轮询 API
- API 从数据库读结果返回前端

### Q2：会影响原来本地运行吗？
不会，原因：
- 未配置 CPU/GPU 分流变量时，仍走原 `RUN_QUEUE` 单队列
- `RUNNER_BACKEND=auto` 时，队列不可用仍可本地线程兜底（remote 模式除外）

### Q3：为什么 remote 模式不允许本地兜底？
为了避免“你以为在远程跑，实际在本地跑”的误导。
remote 模式队列不可用时直接报错。

## 8. 运维建议

1. 生产数据库建议从 SQLite 升级到 PostgreSQL/MySQL
2. Redis 开启密码、内网访问控制
3. 每台 worker 用 `systemd` 或 `supervisor` 守护进程
4. 用 `rq info` / `rq dashboard` 观察队列积压
5. 记录 worker 主机标识到日志（可选扩展）

## 9. 当前边界与下一步

当前已支持：
- remote 表单参与真实队列路由
- 远程队列消费执行
- 结果回写与前端展示

当前未做（可后续扩展）：
- SSH 直连远端执行
- 自动分发代码/模型/数据
- 远程机器资源自动发现与调度（GPU 空闲优先）

如果后续要做“多 GPU 机自动调度”，建议在本方案上增加：
- worker 心跳注册
- 节点能力上报
- 调度策略（最空闲、指定节点、优先级）
