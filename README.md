# 剧场票房分账台

巡演票务财务可用五份 CSV 核对联票原分账、现场核销、停演冲正与场馆应收。首页提供样例预览、首次发布、同源重跑和凭证下载。

## 启动与试用

```bash
docker compose up --build
```

打开 `http://localhost:18422`，选择「运行样例」。核销账、差额槽和结算账按相同场次顺序排列。点场次名称筛选「票房证据」，或从左侧切换业务模块。发布后可点「重跑」和「导出凭证」。通过「导入 CSV」可提交自己的五份报表，列定义见[数据字典](docs/DATA-DICTIONARY.md)。`/?run=sample` 始终可看内置样例预览。

本机可用 Python 3.12 启动。

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --port 18422
python -m pytest -q
```

容器测试 `docker compose exec -T app pytest -q`。默认账册数据库位于 `data/theatre.sqlite3`，可通过 `THEATRE_DB_PATH` 指定别处。Compose 用命名卷 `theatre-data` 保存运行记录；若确认可以丢弃整个账册，再执行 `docker compose down -v` 后重启。

## 使用入口

| 模块 | 能看到的结果 | API |
|---|---|---|
| 票源导入 | 采信票款、来源行与隔离原因 | `GET /api/intake/{run_id}` |
| 套票权益 | 合资格权益、场次状态与冲突行 | `GET /api/rights/{run_id}` |
| 入场核销 | 有效核销及保留、拒收依据 | `GET /api/scans/{run_id}` |
| 权重分账 | 原分账、尾差排名与未分配票款 | `GET /api/allocation/{run_id}` |
| 退款冲正 | 原分账限额、冲正与剩余额度 | `GET /api/refunds/{run_id}` |
| 场馆勾稽 | 逐票、逐场、逐馆与源行核对 | `GET /api/reconcile/{run_id}` |
| 结算凭证 | 运行清单、隔离行、凭证 ZIP | `GET /api/evidence/{run_id}` |

各模块读取接口支持 `run_id=sample` 的预览和 `view`、`q`、`show`、`limit`、`offset` 查询。接口文档在 `/docs`。发布接口是 `POST /api/runs/sample` 与 `POST /api/runs`，重跑是 `POST /api/runs/{run_id}/rerun`，下载是 `GET /api/evidence/{run_id}/export`。

单一账册保留首次发布的票款、权益和场次定义。修订用完整快照提交，允许更新核销，新增停演事实和退款。历史批次可重跑或导出，旧批次重跑不会回退当前账册。每个文件限 512 KiB 和 12,000 条逻辑行。本项目覆盖人民币停演退款和整套票按场分账。

`app/modules` 放各业务规则，`sample_data` 放本机样例，`tests` 放业务与原子性回归。[规则与样例登记](docs/DEPTH.md)
