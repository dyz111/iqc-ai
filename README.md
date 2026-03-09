# IQC-AI

基于 FastAPI + LLM + RAG 的 IQC 异常单建议服务。

## 功能概览

- 接口：`POST /ai/exception_suggestion`
- 输出：采购/计划/生产/工程/质量五部门建议 + evidence
- 检索：本地 `bge-m3` 向量化 + Chroma 相似案例召回
- LLM：支持云端（DeepSeek）或本地（Ollama）

## 目录结构

- `app/`：主服务代码
- `db_manage/`：数据库连接与历史数据脚本
- `scripts/`：索引构建脚本
- `tests/`：测试代码

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制模板并填写真实值：

```bash
cp .env.example .env
```

至少需要：

- `DEEPSEEK_API_KEY`（云端策略）
- `ACTIVE_LLM_STRATEGY=cloud|local`
- 若使用 `db_manage/db_utils.py`，还需要 `DB_032_*` / `DB_05_*`

### 3. 启动服务

```bash
python -m app.main
```

或：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 10086 --reload
```

### 4. 接口文档

启动后访问：

- `http://127.0.0.1:10086/docs`

## 索引构建（可选）

```bash
python scripts/build_exception_index.py
```

## 安全与提交注意

- 不要提交 `.env`
- 不要提交 `app/storage/chroma_db/`
- 不要提交 `app/weights/`（模型大文件建议用私有制品库或 Git LFS）
- 数据库账号密码只放在本地环境变量中

## 常见问题

1. 报错 `Missing required environment variable`

- 说明 `.env` 未配置完整，补齐对应变量即可。

2. SQL Server 连接报加密/证书错误

- 可尝试：
  - `DB_032_ENCRYPT=no`
  - `DB_05_ENCRYPT=no`
  - `DB_032_TRUST_SERVER_CERTIFICATE=yes`
  - `DB_05_TRUST_SERVER_CERTIFICATE=yes`
