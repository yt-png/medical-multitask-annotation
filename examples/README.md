# P2 样例与演示（T2.4）

本目录提供假数据与演示脚本，用于跑通：

```text
假算法 raw Mapping
  → Example*Adapter + AdapterContext
  → PrelabelDocument
  → Label Studio import JSON
```

**不包含**真实算法、CLI `convert`、Label Studio XML。

## 目录

| 路径 | 说明 |
|---|---|
| `raw/demo_batch/` | P1 用：假 jpg + Excel（预处理/任务包） |
| `prelabels/demo_batch/` | T2.1：已写好的统一中间格式 `prelabels.json` |
| `adapter_raw/demo_batch/` | T2.4：算法 raw 与业务上下文分离的假数据 |
| `scripts/run_p2_demo.py` | T2.4：端到端演示脚本（非 `src/mma` 业务模块） |

## `adapter_raw/demo_batch/`

| 文件 | 内容 |
|---|---|
| `contexts.json` | 业务信封：`batch_id`、`image_id`、`diagnosis_text`、`image_path`（经 `AdapterContext` 注入） |
| `seg_raw.json` / `det_raw.json` / `cap_raw.json` | **仅**算法相关字段，固定形态 `{"items":[...]}` |

raw 与 contexts 的 `items` **按下标对齐**。

## 运行演示脚本

在项目根目录、已 `pip install -e .` 的环境下：

```bash
python examples/scripts/run_p2_demo.py
python examples/scripts/run_p2_demo.py --out-dir examples/ls_import_demo
```

`--out-dir` 可选：写出 `{seg,det,cap}/tasks.json`（演示产物，默认不入库）。

## 相关测试

```bash
python -m pytest tests/test_p2_pipeline.py -q
python -m pytest tests/ -q
```

契约说明见 [docs/formats.md](../docs/formats.md)。
