# 医学图像多任务标注数据流（mma）

本地可脚本化的医学图像标注流水线：对同一批图像分别完成 **SEG / DET / CAP** 三类标注，经 Label Studio 人工确认与返工闭环后，合并为每张图同时具备三类结果的最终数据集。

协作分发与回传走网盘；本仓库**不包含**业务服务端，也**不实现**预标注算法 / 大模型调用。

## 流水线一览

```text
raw 图文
  → preprocess          # 图文绑定 → processed/<batch>/manifest.json
  → package             # 拆成三类全量任务包 → task_packages/
  → 外部写入 prelabels/ # 统一中间格式（本仓库不跑算法）
  → ls-import           # 生成 Label Studio 导入 JSON
  → [Label Studio 标注]
  → export-split        # 导出 → 更新 current/，并重建 normal/ + rework/
  → rework-import       # （有返工时）再导入 → 再标注 → 再 export-split
  → merge               # 三路 current 就绪后 → final/<batch>/
```

数据根默认 `./data`（可用 `--data-root`）。目录职责见 [docs/data_layout.md](docs/data_layout.md)。

## 环境与安装

- Python **3.12+**
- 依赖：`openpyxl`、`Pillow`、`numpy`、`opencv-python-headless`

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux / macOS: source .venv/bin/activate
pip install -e .
```

入口：`mma -h` 或 `python -m mma -h`。无 `configs/default.yaml`；约定内嵌于代码与 CLI。

**原始输入**：图像为 `.jpg`；诊断 Excel 为 `.xlsx`，首表列名固定 `image_name` / `diagnosis_text`。

## CLI 速查

| 命令 | 作用 | 主要产出 |
|------|------|----------|
| `preprocess` | 图文配对、分配 `image_id` | `processed/<batch>/manifest.json`（引用原图，不复制） |
| `package` | 拆 SEG/DET/CAP 全量任务包 | `task_packages/<batch>/{seg,det,cap}/` |
| `ls-import` | 生成首轮 LS 导入任务 | `ls_import/<batch>/<task>/tasks.json` |
| `export-split` | **推荐**：导出落盘 + 分类 | 更新 `current/`，重建 `normal/`、`rework/` |
| `apply-current` | 底层：仅同步 `current/`（也会刷新 normal/rework） | 同左；日常优先用 `export-split` |
| `rework-import` | 生成返工再导入任务 | `ls_import/<batch>/<task>/rework_tasks.json` |
| `merge` | 三任务合并为最终集 | `final/<batch>/{manifest.json,images/,masks/}` |
| `convert` | **未接线**（stub） | — |

`export-split` 与 `apply-current` 对**同一份 export 二选一**，勿连跑。

### 常用命令

```bash
# 1. 预处理 + 拆包
mma preprocess --batch demo_batch \
  --images examples/raw/demo_batch/images \
  --excel examples/raw/demo_batch/diagnoses.xlsx \
  --data-root data
mma package --batch demo_batch --data-root data

# 2. 预标注就绪后生成 LS 导入（需 prelabels/ + task_packages/）
mma ls-import --batch demo_batch --task seg --data-root data

# 3. LS 导出后落盘（建议按轮次存放 export）
mma export-split --batch demo_batch --task cap \
  --export data/ls_export/demo_batch/cap/round_001/export.json \
  --data-root data

# 4. 有返工时再导入（优先读 rework/previous_annotations/）
mma rework-import --batch demo_batch --task cap --data-root data

# 5. 三路 current 均无返工后合并
mma merge --batch demo_batch --data-root data
```

## 关键约定（必读）

**权威结果**：每任务以 `results/<batch>/<task>/current/` 为准。按 `image_id` **合并覆盖**——本轮出现的覆盖，未出现的保留；首轮请导出该任务本批全部样本。

**分类规则**：`should_rework = (not human_confirmed) or needs_rework`。仅「已确认且不需返工」进 `normal/`；其余进 `rework/`（含未勾确认）。每次 `export-split` / `apply-current` 后按最新 `current/` **全量重建** normal/rework。

**预标注覆盖**：`ls-import` 要求任务包与 `prelabels.json` 的 `image_id` 集合完全一致；缺/多均失败，不静默跳过。

**SEG**：默认 polygon 预填；人工几何写入 `manual_masks/`，不覆盖 `prelabels/.../masks/`。  
**DET / CAP**：人工结果优先；未操作可回退预标注；人工清空则保留空结果。

**final**：自包含（含 `images/`、`masks/` 与相对路径清单）；未就绪或缺任务则失败，不改写已有 final。

**LS 本地文件**：`--local-root`（默认等于 `--data-root`）须与 Label Studio Local Storage 根一致。详见 [docs/labelstudio_usage.md](docs/labelstudio_usage.md)。

## 预标注与演示

预标注统一中间格式见 [docs/formats.md](docs/formats.md)。落点：`data/prelabels/<batch>/{seg,det,cap}/prelabels.json`。

Python 转换 API（CLI `convert` 仍为 stub）：

```python
from pathlib import Path
from mma.converters import document_to_ls_tasks
from mma.formats import load_prelabel_document

doc = load_prelabel_document("data/prelabels/demo_batch/seg/prelabels.json")
tasks = document_to_ls_tasks(doc, mask_root=Path("data/prelabels/demo_batch/seg"))
```

假数据端到端演示：`python examples/scripts/run_p2_demo.py`（见 [examples/README.md](examples/README.md)）。

## 更多文档

| 文档 | 内容 |
|------|------|
| [docs/data_layout.md](docs/data_layout.md) | 目录树、落盘与合并语义 |
| [docs/formats.md](docs/formats.md) | 预标注中间格式与 LS 控件名 |
| [docs/labelstudio_usage.md](docs/labelstudio_usage.md) | Label Studio 本地导入与标注 |
| [docs/real_batch_local_test_runbook.md](docs/real_batch_local_test_runbook.md) | real_batch 全链路实测手册 |

开发约定见 `.cursor/rules/`。功能分支开发；提交前本地跑通检查再 `git commit`。
