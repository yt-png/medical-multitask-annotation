# Examples（样例与演示）

本目录提供假数据与脚本。默认演示 **V1 主流程**；历史对照演示单独放在下方 Legacy 一节。

V1 目标：纯人工金标准（见仓库根 [README.md](../README.md)）。

---

## 1. V1 Workflow

默认路径（**不依赖**历史预标注目录）：

```text
raw data (examples/raw/<batch>/)
    ↓  mma preprocess
processed/<batch>/manifest.json
    ↓  mma package
task_packages/<batch>/{seg,det,cap}/
    ↓  mma ls-import
ls_import/<batch>/{seg,det,cap}/tasks.json   # 空任务，无 predictions
```

`task_packages` 是 Label Studio 首轮导入的入口；`mma ls-import` 只读任务包，生成空标注任务。

### 快速命令（demo_batch）

```bash
mma preprocess --batch demo_batch \
  --images examples/raw/demo_batch/images \
  --excel examples/raw/demo_batch/diagnoses.xlsx \
  --data-root data

mma package --batch demo_batch --data-root data

mma ls-import --batch demo_batch --task seg --data-root data
mma ls-import --batch demo_batch --task det --data-root data
mma ls-import --batch demo_batch --task cap --data-root data
```

更多说明见 [raw/README.md](raw/README.md)。

### 目录（V1 相关）

| 路径 | 说明 |
|---|---|
| `raw/demo_batch/` | 假 jpg + Excel，供 preprocess / package / ls-import |
| `raw/uat_demo_001/` | 同上，UAT 用假数据 |
| `scripts/prepare_uat_demo_001.py` | 准备 UAT raw 样例 |
| `scripts/run_p4_current_demo.py` | 本地 current 相关演示（非历史转换脚本） |

---

## 2. Legacy Examples

以下**仅用于历史兼容 / 对照**，**not part of V1 runtime**。新人默认不必运行。

| 路径 | 说明 |
|---|---|
| `prelabels/` | 历史 `prelabels.json` 样例布局 |
| `adapter_raw/` | 假算法 raw + `AdapterContext` 信封 |
| `scripts/run_p2_demo.py` | LEGACY：raw → Example adapter → LS JSON（含 predictions） |
| `ls_import_demo/` | `run_p2_demo` 可选写出目录（演示产物） |

Legacy 链路（参考）：

```text
假算法 raw Mapping
  → Example*Adapter + AdapterContext
  → PrelabelDocument
  → Label Studio import JSON（含 predictions）
```

```bash
# LEGACY only — not V1
python examples/scripts/run_p2_demo.py
python examples/scripts/run_p2_demo.py --out-dir examples/ls_import_demo
```

契约说明见 [docs/formats.md](../docs/formats.md)。CLI `mma convert` 为 legacy stub，V1 请用 `ls-import`。
