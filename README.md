# 社区检测集成平台（Monorepo）

本仓库包含：
- `frontend/`：Vue3 + Vite 前端
- `backend/`：FastAPI 后端（线程异步 mock runner）

## 目录结构

```text
.
├── frontend/
└── backend/
```




## 功能概览

- 未登录可访问：
  - `GET /public/methods`
  - `GET /public/datasets`
  - `GET /public/datasets/{id}/preview`
  - `GET /public/metrics`
- 认证：
  - `POST /auth/register`
  - `POST /auth/login`
- 运行：
  - `POST /runs`（需 Bearer Token，异步提交）
  - `GET /runs/{id}`（需 Bearer Token，查看运行状态）
  - `GET /runs/{id}/results`（需 Bearer Token，查看指标结果）
  - `GET /runs/me`（需 Bearer Token，查看我的运行列表）

## 异步执行（RQ + Redis，含本地兜底）

后端支持三种执行模式（环境变量 `RUNNER_BACKEND`）：

- `auto`（默认）：优先尝试 RQ+Redis；失败自动回退本地线程异步
- `rq` / `redis`：强制使用 RQ+Redis（不可用则报错）
- `inline`：同步执行（建议测试使用）

Redis 连接可通过 `REDIS_URL` 配置，默认 `redis://127.0.0.1:6379/0`。
队列名可通过 `RUN_QUEUE` 配置，默认 `runs`。

### 方法执行环境（默认强制 bsenv）

为避免后端主进程环境与算法依赖冲突，运行任务时的方法执行会默认走：

```bash
conda run -n bsenv python -m app.runner.method_subprocess
```

可配置项：
- `RUNNER_CONDA_ENV`：默认 `bsenv`，用于指定方法执行的 conda 环境名
- `RUNNER_CONDA_EXE`：可选，指定 conda 可执行文件绝对路径（如 `/root/miniconda3/bin/conda`）
- `RUNNER_METHOD_TIMEOUT_SEC`：默认 `7200`，单次方法执行超时时间（秒）

启动 RQ worker（示例）：

```bash
cd backend
export REDIS_URL=redis://127.0.0.1:6379/0
export RUN_QUEUE=runs
python -m rq worker runs
```

Run 表当前包含（含兼容字段）：
- `run_id`, `user_id`
- `dataset_id`, `method_id`, `metrics`, `params`
- `status`, `created_at`, `started_at`, `finished_at`, `duration`
- `logs`, `results`

## Docker Compose 一键启动（Redis + Backend + Worker）

在仓库根目录执行：

```bash
docker compose up --build
```

启动后：
- Backend: `http://127.0.0.1:8000`
- Redis: `127.0.0.1:6379`
- Worker: 消费 `runs` 队列异步任务

停止并清理：

```bash
docker compose down
```

说明：
- `RUNNER_BACKEND=rq`，`POST /runs` 会把任务放入 Redis 队列。
- 本地数据集目录 `datasets/` 会挂载到容器内 `/app/datasets`。
- 若你修改了后端依赖，重新执行 `docker compose up --build`。

## 后端启动（Python 3.8，建议 conda env: `bsenv`）

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 前端启动

```bash
cd frontend
npm install
npm run dev
```


默认前端访问 `http://127.0.0.1:5173`，后端 API 访问 `http://127.0.0.1:8000`。

## 联调流程

1. 打开首页，确认方法/数据集/指标加载。
2. 在登录/注册页注册用户（会返回 token 并保存在浏览器本地）。
3. 在运行页选择方法 + 数据集 + 指标，点击运行。
4. 自动跳转结果页，轮询展示 `run_id`、状态、指标与日志。

## 调试方法

### 1) 准备环境

```bash
conda activate bsenv
```

### 2) 后端调试（FastAPI）

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
```

- 打开 Swagger：`http://127.0.0.1:8000/docs`
- 看健康检查：`GET http://127.0.0.1:8000/`
- 常用断点位置：
  - `backend/app/api/runs.py`（参数校验、创建 run）
  - `backend/app/runner/mock_runner.py`（线程 mock 执行过程）
  - `backend/app/core/auth.py`（token 鉴权）

### 3) 前端调试（Vue + Vite）

```bash
cd frontend
npm install
npm run dev
```

- 打开页面：`http://127.0.0.1:5173`
- 浏览器开发者工具：
  - `Network` 看接口是否 200/401/400
  - `Console` 看前端报错
- 前端 API 入口：`frontend/src/api/client.js`（默认后端地址 `http://127.0.0.1:8000`）

### 4) API 手工联调（curl）

1. 注册

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo1234"}'
```

2. 登录并拿 token

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo1234"}'
```

3. 提交运行（把 `<TOKEN>` 替换为登录返回 token）

```bash
curl -X POST http://127.0.0.1:8000/runs \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"method_key":"louvain","dataset_key":"cora","metric_keys":["nmi","modularity_q"],"seed":42,"params":{}}'
```

4. 查询结果（把 `<RUN_ID>` 替换为上一步返回 run_id）

```bash
curl http://127.0.0.1:8000/runs/<RUN_ID> \
  -H "Authorization: Bearer <TOKEN>"
```

### 5) 自动化测试

```bash
cd backend
pytest -q
```

### 6) 常见问题

- `401 Invalid token`：未登录或 `Authorization` 头格式不是 `Bearer <token>`。
- `400 Metric ... requires labels`：拓扑数据集（如 Karate）不能算需要标签的指标（如 NMI/ACC/ARI）。
- 前端请求失败：确认后端在 `8000` 端口运行，前端 API 地址与后端一致。

## 插件化扩展

核心注册表在：`core_modules/registry.py`

- 新增方法：
  1. 在 `core_modules/methods/` 新建文件并调用 `registry.register_method(...)`
  2. 在 `backend/app/services/plugin_loader.py` 中引入并调用 `register()`
- 新增数据集：
  1. 在 `core_modules/datasets/` 新建文件并调用 `registry.register_dataset(...)`
  2. 在 `backend/app/services/plugin_loader.py` 中引入并调用 `register()`
- 新增指标：
  1. 在 `core_modules/methods/metrics.py` 中集中维护指标注册与计算逻辑
  2. 所有方法统一调用该文件中的指标计算入口

这样可以在不改动核心 API/runner 流程的前提下完成扩展。

## 数据集目录与格式（你当前这批数据）

默认数据根目录：`/home/bishePro/datasets`（可通过环境变量 `DATASETS_ROOT` 覆盖）。

你手动提供的数据集目录：

```text
datasets/
└── manual/
    ├── strike/
    │   ├── edges.csv
    │   └── labels.csv
    ├── karate/
    ├── dolphins/
    ├── polbooks/
    ├── football/
    ├── email_eu/
    └── polblogs/
```

`edges.csv` 格式：

```csv
source,target
1,2
2,3
```

`labels.csv` 格式：

```csv
node,label
1,community_a
2,community_a
3,community_b
```

说明：节点编号从 `0` 开始完全支持（例如 `0,1,2,...`）。

可下载数据集（`cora`、`citeseer`）会自动下载并缓存到：

```text
datasets/cache/cora/
datasets/cache/citeseer/
```

下载后会标准化为：
- `edges.csv`
- `labels.csv`
- `features.csv`

`GET /public/datasets/{id}/preview` 返回统一结构：
- `graph`（必有）
- `features`（可选）
- `labels`（可选）
- `meta`（必有）

## 复杂方法模板（神经网络 + 多文件 + GPU）

已内置模板方法：`gnn_template`，代码目录：

```text
core_modules/methods/gnn_template/
├── plugin.py
├── config.py
├── data.py
├── model.py
├── trainer.py
└── utils.py
```

推荐改造方式：
1. 在 `model.py` 替换为你的真实网络结构（GCN/GAT/GraphSAGE 等）。
2. 在 `trainer.py` 中实现训练循环、损失函数、早停、推理逻辑。
3. 保持 `train_and_predict(...) -> List[int]` 输出接口不变。
4. 在 `plugin.py` 中读取参数并调用 trainer。
5. 若需要 GPU：
- 保持 `requires_gpu=True`
- 参数里 `use_gpu=true`
- 若 CUDA 不可用，给出清晰报错（模板已内置）

前端参数（Run 页）已为 `gnn_template` 预置并校验：
- `num_clusters`
- `hidden_dim`
- `num_layers`
- `dropout`（前端用百分比输入）
- `lr`（前端用 `lr_milli` 转换）
- `weight_decay`（前端用 `weight_decay_micro` 转换）
- `epochs`
- `use_gpu`

注意：
- 方法必须使用随机种子。
- 输出标签长度必须等于节点数。
- 若无特征输入，需有拓扑回退方案。

## 手动添加方法（含注意事项）

新增方法建议按以下步骤：

1. 在 `core_modules/methods/plugins.py` 新建一个 `MethodPlugin` 子类，并实现：
- `key`：唯一键（小写下划线）
- `name`：展示名
- `description`：简短说明
- `run(self, data, seed, params) -> List[int]`

2. 在 `run(...)` 中必须满足这几个约束：
- 必须使用 `seed` 控制随机性（保证可复现）
- 输出 `y_pred` 长度必须等于 `len(data.nodes)`
- 输出标签必须是整数类别（如 `0,1,2...`）
- 若使用特征，需兼容 `data.features is None` 的情况（提供拓扑回退）

3. 在 `core_modules/methods/builtin.py` 的 `METHOD_META` 中补充元信息：
- `algorithm_note`：算法说明（答辩展示用）
- `implementation_level`：`standard` / `standard-lite` / `approximate`
- `supports_attributed`：是否支持有属性网络
- `supports_unattributed`：是否支持无属性网络

4. 在 `frontend/src/views/RunView.vue` 同步方法参数配置：
- 更新 `methodParamSchema`（参数表单、默认值、校验范围）
- 如方法支持 `num_clusters`，建议保留该参数；前端会优先用数据集社区数自动填充

5. 建议补测试：
- 至少验证新方法在 Karate 上可跑通（方法->指标）
- 验证输出标签长度与节点数一致

常见坑：
- `key` 冲突：会覆盖旧方法
- 参数名不一致：前端传了参数但方法里没读取
- 未处理无属性数据：导致在仅有 `edges.csv` 时运行失败
- 非确定性随机过程未使用 `seed`：同样输入多次结果波动太大

## 测试

```bash
cd backend
pytest -q
```

当前包含：
- 插件注册与公开接口测试
- 认证 + 创建 run + 查询 run 的 API 流程测试
