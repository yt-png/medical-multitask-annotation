# 医学图像多任务标注平台 V1（mma）

**V1 定位**：基于冻结 V2 复制后的**独立项目**，目标是纯人工医学图像**金标准**生产流程（SEG / DET / CAP），经 Label Studio 标注与返工闭环后，合并为每张图同时具备三类结果的最终数据集。

协作分发与回传走网盘；本仓库**不包含**业务服务端，也**不实现**预标注算法 / 大模型调用。

### 与冻结 V2 的差异（业务层，非代码兼容承诺）

| | V2（冻结参考） | V1（目标） |
|---|---|---|
| 首轮导入 | 外部 `prelabels/` → LS `predictions` | 仅 `task_packages/` → 空任务（无模型/prelabel 预填） |
| 金标准来源 | 允许 prediction 回退填结果 | 仅人工 `annotation`；禁止 model/prelabel 进金标准 |
| 空标注 | 可能被 prediction 回填 | 空 / 缺结果 → `rework/` |
| prelabel 能力 | 主流程 | **隔离为 legacy**（历史参考，非主流程必做） |

> **实现状态**：首轮 **空任务 `ls-import` 已落地**（M4.1 / M4.2）；**M6.1/M6.2 已落地**：有效结果与 parse 金标准仅人工 annotation（无 `prediction_fallback` / 不以 `data.mask_ref` 或 pred 填结果）。下列项**仍未完成**：空标注→rework、adapters/formats legacy 隔离等（见 CHANGELOG「Planned」与 `.cursor/rules/V1 Development Tasks.md`）。与尚未交付行为不一致处仍标 **〔现状〕**。

## 流水线一览（V1）

```text
raw 图文
  → preprocess          # 图文绑定 → processed/<batch>/manifest.json
  → package             # 拆成三类全量任务包 → task_packages/
  → ls-import           # 仅从任务包生成空 LS 任务（无 prelabels）
  → [Label Studio 人工标注]
  → export-split        # 导出 → 更新 current/，并重建 normal/ + rework/
  → rework-import       # （有返工时）再导入「上一轮人工历史」预填 → 再标注 → 再 export-split
  → merge               # 三路 current 就绪后 → final/<batch>/
```

`ls-import` 输入仅为 `task_packages/<batch>/<task>/`（含 `manifest.json` 与 `images/`）；**不读取** `prelabels/`。

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
| `convert` | **未接线**（stub；V1 不作为 prelabel 转换入口） | — |

`export-split` 与 `apply-current` 对**同一份 export 二选一**，勿连跑。

### 常用命令

```bash
# 1. 预处理 + 拆包（V1 与当前实现均适用）
mma preprocess --batch demo_batch \
  --images examples/raw/demo_batch/images \
  --excel examples/raw/demo_batch/diagnoses.xlsx \
  --data-root data
mma package --batch demo_batch --data-root data

# 2. 生成 LS 空任务导入（仅需 task_packages/；无需 prelabels/）
mma ls-import --batch demo_batch --task seg --data-root data

# 3. LS 导出后落盘（建议按轮次存放 export）
mma export-split --batch demo_batch --task cap \
  --export data/ls_export/demo_batch/cap/round_001/export.json \
  --data-root data

# 4. 有返工时再导入（优先读 rework/previous_annotations/）
# 返工预填 = 上一轮人工历史；业务上 ≠ 模型 prediction（LS 字段名可能仍叫 predictions）
mma rework-import --batch demo_batch --task cap --data-root data

# 5. 三路 current 均无返工后合并
mma merge --batch demo_batch --data-root data
```

## 关键约定（必读）

**权威结果**：每任务以 `results/<batch>/<task>/current/` 为准。按 `image_id` **合并覆盖**——本轮出现的覆盖，未出现的保留；首轮请导出该任务本批全部样本。

**分类规则（当前已实现）**：`should_rework = (not human_confirmed) or needs_rework`。仅「已确认且不需返工」进 `normal/`；其余进 `rework/`（含未勾确认）。每次 `export-split` / `apply-current` 后按最新 `current/` **全量重建** normal/rework。

**空标注 → rework（V1 目标，尚未实现）**：无有效人工载荷（空 result / 缺 mask·bbox·text）也应进入 `rework/`。〔现状〕分类仍主要看勾选。

**金标准来源（M6.1 / M6.2 已落地）**：`resolve_effective_result` 与 `parse_ls_export` 有效结果仅来自人工 `annotation`；已删除 `prediction_fallback`；SEG 不再用 `data.mask_ref` / pred 几何作金标准（空/无几何写 `manual_masks/`）。

**首轮导入（已实现）**：`tasks.json` 每条仅含 `data.image` / `image_id` / `package_id` / `diagnosis_text`；**无** `predictions`、`mask_ref` 或 prelabel 字段。输入仅为 `task_packages/`。

**SEG**：人工几何或空/confirm-only 写入 `manual_masks/`；须提供 `seg_manual_mask_dir`。首轮导入不再做 prelabel 预填。

**DET / CAP**：首轮导入无预填框/文本；导出不再回填 prediction；人工清空或 confirm-only → 空框 / 空文案。

**返工预填**：`previous_annotations` = 上一轮**人工**快照；可写入 LS `predictions` 槽位供展示，**业务语义不是模型预测**；导出金标准不再将该槽位作 fallback（M6.1/M6.2）；返工语义文档收紧见 M6.4。

**final**：自包含（含 `images/`、`masks/` 与相对路径清单）；未就绪或缺任务则失败，不改写已有 final。

**LS 本地文件**：`--local-root`（默认等于 `--data-root`）须与 Label Studio Local Storage 根一致。详见 [docs/labelstudio_usage.md](docs/labelstudio_usage.md)。

## Legacy 参考（非 V1 主流程）

以下内容保留供对照冻结 V2 / 历史测试，**不是** V1 主流程必做步骤，主 README 不要求「必须准备 prelabels」：

| 路径 | 说明 |
|------|------|
| [docs/formats.md](docs/formats.md) | **Legacy**：预标注统一中间格式与转换约定 |
| [examples/prelabels/](examples/prelabels/) | **Legacy**：历史样例 `prelabels.json` |
| [examples/README.md](examples/README.md) | **Legacy**：adapter → prelabel → LS 演示（`run_p2_demo.py`） |

## 更多文档

| 文档 | 内容 |
|------|------|
| [docs/data_layout.md](docs/data_layout.md) | 目录树、落盘与合并语义（含 legacy `prelabels/` 说明） |
| [docs/labelstudio_usage.md](docs/labelstudio_usage.md) | Label Studio 本地导入与标注（首轮 / 返工语义） |
| [docs/formats.md](docs/formats.md) | **Legacy** 预标注中间格式与 LS 控件名 |
| [docs/real_batch_local_test_runbook.md](docs/real_batch_local_test_runbook.md) | real_batch 全链路实测手册（仍可能描述当前实现路径） |

开发约定见 `.cursor/rules/`（V1 Requirement / Development Tasks / Specifications）。功能分支开发；提交前本地跑通检查再 `git commit`。
