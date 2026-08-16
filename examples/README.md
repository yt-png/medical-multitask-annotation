# LEGACY — 样例与演示（历史 P2 / 预标注链路）

> **非 V1 主流程。** V1 目标为纯人工金标准（见仓库根 README）；本目录中的 adapter / prelabels / `run_p2_demo.py` 仅作冻结 V2 对照与既有测试参考。  
> **〔现状〕**：相关代码与测试仍存在；未宣称已从运行时隔离完毕（见 CHANGELOG Planned / M1–M2）。

本目录提供假数据与演示脚本，用于跑通**历史**链路：

```text
假算法 raw Mapping
  → Example*Adapter + AdapterContext
  → PrelabelDocument
  → Label Studio import JSON（含 predictions）
```

**不包含**真实算法、CLI `convert`（仍为 stub）、Label Studio XML。

## 目录

| 路径 | 说明 |
|---|---|
| `raw/demo_batch/` | 预处理 / 任务包用：假 jpg + Excel（**仍适用于 V1 preprocess/package**） |
| `prelabels/demo_batch/` | **Legacy**：统一中间格式 `prelabels.json` |
| `adapter_raw/demo_batch/` | **Legacy**：算法 raw 与业务上下文分离的假数据 |
| `scripts/run_p2_demo.py` | **Legacy**：端到端演示脚本（非 `src/mma` 业务模块） |

## `adapter_raw/demo_batch/`（Legacy）

| 文件 | 内容 |
|---|---|
| `contexts.json` | 业务信封：`batch_id`、`image_id`、`diagnosis_text`、`image_path`（经 `AdapterContext` 注入） |
| `seg_raw.json` / `det_raw.json` / `cap_raw.json` | **仅**算法相关字段，固定形态 `{"items":[...]}` |

raw 与 contexts 的 `items` **按下标对齐**。

## 运行演示脚本（Legacy）

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

Legacy 契约说明见 [docs/formats.md](../docs/formats.md)。V1 主流程上手见仓库根 [README.md](../README.md)。
