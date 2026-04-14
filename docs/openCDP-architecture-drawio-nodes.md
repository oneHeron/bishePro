# OpenCDP 架构图节点清单

本文档用于在 `draw.io`、`Visio`、`ProcessOn` 等工具中手工精修 OpenCDP 总体架构图。

## 1. 推荐分层

### 第一层：前端展示层

- Web 用户界面
- 首页
- 登录注册界面
- 方法/数据集/指标浏览界面
- 运行配置界面
- 结果详情界面
- 运行历史界面

### 第二层：后端接口层

- FastAPI 服务
- 公开接口 `/public/methods`
- 公开接口 `/public/datasets`
- 公开接口 `/public/metrics`
- 数据集预览接口 `/public/datasets/{id}/preview`
- 认证接口 `/auth/register`
- 认证接口 `/auth/login`
- 运行提交接口 `/runs`
- 运行历史接口 `/runs/me`
- 状态查询接口 `/runs/{id}`
- 结果查询接口 `/runs/{id}/results`
- 取消任务接口 `/runs/{id}/cancel`

### 第三层：服务与调度层

- 插件加载服务 `load_builtin_plugins()`
- 参数校验
- 权限校验
- 数据集管理器 `dataset_manager`
- 异步提交入口 `submit_run()`
- 任务取消控制 `cancel_run_execution()`
- 本地线程执行器
- Redis + RQ 队列调度器
- CPU 队列
- GPU 队列
- Remote 队列

### 第四层：插件与算法执行层

- 统一注册中心 `registry`
- 方法注册表 `registry.methods`
- 数据集注册表 `registry.datasets`
- 指标注册表 `registry.metrics`
- 方法插件集合
- Louvain
- K-Means
- NMF
- DeepWalk
- DDGAE
- CDBNE
- CSEA
- 指标计算模块
- NMI
- ACC
- ARI
- Modularity Q
- Conda 子进程执行器 `app.runner.method_subprocess`
- 可视化结果生成
- 社区划分结果生成

### 第五层：数据与持久化层

- SQLite
- SQLAlchemy
- 用户表 `users`
- 运行记录表 `runs`
- 数据集目录 `datasets/manual`
- 数据集缓存目录 `datasets/cache`
- 运行日志
- 指标结果
- 版本信息
- 可视化结果数据
- 社区划分结果文件
- 错误详情

## 2. 推荐连线

### 前端到后端

- Web 用户界面 -> FastAPI
- 运行配置界面 -> 运行提交接口
- 结果详情界面 -> 状态查询接口
- 结果详情界面 -> 结果查询接口
- 运行历史界面 -> 运行历史接口
- 登录注册界面 -> 认证接口

### 后端到服务与调度

- 运行提交接口 -> 参数校验
- 运行提交接口 -> 权限校验
- 运行提交接口 -> 异步提交入口
- 公开接口 -> 插件加载服务
- 公开接口 -> 数据集管理器
- 取消任务接口 -> 任务取消控制

### 服务与调度到插件执行

- 插件加载服务 -> 统一注册中心
- 异步提交入口 -> Redis + RQ 队列调度器
- 异步提交入口 -> 本地线程执行器
- Redis + RQ 队列调度器 -> Conda 子进程执行器
- 本地线程执行器 -> Conda 子进程执行器
- Conda 子进程执行器 -> 方法插件集合
- 方法插件集合 -> 指标计算模块
- 方法插件集合 -> 可视化结果生成
- 方法插件集合 -> 社区划分结果生成

### 执行结果到存储

- 指标计算模块 -> 运行记录表 `runs`
- 可视化结果生成 -> 运行记录表 `runs`
- 社区划分结果生成 -> 运行记录表 `runs`
- 数据集管理器 -> 数据集目录
- 数据集管理器 -> 数据集缓存目录

## 3. 推荐布局

### 方案 A：论文分层框图

- 最左侧放四个侧边标签：
  - 前端展示层
  - 后端接口层
  - 服务与调度层
  - 数据与持久化层
- 中间主体采用四个虚线大框按从上到下排布。
- 每个大框内部再放 3 到 6 个核心方框。
- 使用竖向主箭头表示“请求下行、结果回传”。

### 方案 B：彩色平台示意图

- 左上放用户与浏览器图标。
- 上方放“Web 前端”云朵或卡片。
- 中部放“FastAPI 服务中心”主云团。
- 中下放“算法执行与插件中心”。
- 底部放“SQLite / datasets / results storage”。
- 用橙色虚线或蓝色箭头表示：
  - 任务提交
  - 状态轮询
  - 结果回传
  - 数据读取

## 4. 推荐图形命名

- 图名建议：
  - `OpenCDP 总体架构图`
  - `OpenCDP 系统总体架构设计`
  - `OpenCDP 平台分层架构图`

## 5. 推荐配色

- 主色：青灰蓝 `#3e6b80`
- 辅色：暖金 `#c89b5d`
- 背景：米白 `#fcfaf6`
- 描边：深灰 `#56646d`
- 强调流向：橙色 `#dd7f32`
