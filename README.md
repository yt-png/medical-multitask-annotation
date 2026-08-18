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

> **实现状态**
>
> - **Sprint A（已完成）**：空任务 `ls-import`（M4）；金标准仅人工 annotation、空标注→`rework/`、无 prelabels/prediction 主流程门禁（M6 / M5.1–M5.2 / M5.6 / M12.1–M12.3）。
> - **Sprint B（已完成｜清理与隔离）**：adapters → `legacy/adapters`（M1）；formats 三分 + `legacy_prelabel`（M2 Phase A）；`seg_mask_paths` 无 prelabels fallback（M5.3–M5.5）；converter 语义「LS `predictions` ≠ 模型推理」（M3.2–M3.4）；CLI `convert` / examples 默认 V1（M3.3 / M10.2）；preprocess/packaging 无 legacy 依赖（M7）。
> - **Sprint C（已完成｜必做项）**：M4.3 返工预填源仅 `previous_annotations`；M6.4 快照语义文档收口；M8.1–M8.3 merge；M12.4 独立运行；M12.5 返工闭环 → merge 出 final。
> - **Sprint D（已完成｜含 M12.6 冻结验收）**：四角色部署包 [`deploy/v1/`](deploy/v1/)（M11）；LS 配置回归（M9）；文档定稿（M0）。冻结报告：[docs/M12.6_FINAL_FREEZE_REPORT.md](docs/M12.6_FINAL_FREEZE_REPORT.md)。状态：**Medical Image Multi-task Annotation Dataflow V1 Frozen**（非「最终产品发布完成」）。可选 B2（返工路径脱离 PrelabelItem）不阻塞冻结。

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

调用关系（冻结叙述，不引入新层）：

```text
src/mma（业务实现）
  → mma CLI（`mma` / `python -m mma`）
  → deploy/v1 角色入口（薄包装，不复制业务代码）
```

四角色：`data_processor`、`annotator_seg`、`annotator_det`、`annotator_cap`。协作分发与本机测试说明见 [`deploy/v1/README.md`](deploy/v1/README.md)。

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

**分类规则（当前运行时）**：`should_rework_result = (not human_confirmed) or needs_rework or (not effective_payload)`。仅「已确认、不需返工、且有有效任务载荷」进 `normal/`；其余进 `rework/`（含未勾确认、空框/空文案、SEG 空 mask）。每次 `export-split` / `apply-current` 后按最新 `current/` **全量重建** normal/rework。旧勾选-only 辅助函数 `should_rework` 仍保留。

**有效载荷**：DET ≥1 框；CAP strip 后非空文案；SEG 非空 `mask_ref` 且 `has_foreground=True`（parse 写空 `manual_masks/` 时为 `False`；legacy JSON 缺字段默认 `True`）。合并就绪校验对「已确认且未勾返工但空载荷」报 `empty task payload`。

**金标准来源（M6.1 / M6.2 已落地）**：`resolve_effective_result` 与 `parse_ls_export` 有效结果仅来自人工 `annotation`；已删除 `prediction_fallback`；SEG 不再用 `data.mask_ref` / pred 几何作金标准（空/无几何写 `manual_masks/`）。

**首轮导入（已实现）**：`tasks.json` 每条仅含 `data.image` / `image_id` / `package_id` / `diagnosis_text`；**无** `predictions`、`mask_ref` 或 prelabel 字段。输入仅为 `task_packages/`。

**SEG**：人工几何或空/confirm-only 写入 `manual_masks/`；须提供 `seg_manual_mask_dir`。首轮导入不再做 prelabel 预填。

**DET / CAP**：首轮导入无预填框/文本；导出不再回填 prediction；人工清空或 confirm-only → 空框 / 空文案。

**返工预填**：`previous_annotations` = 上一轮**人工**快照（**`previous_annotations` ≠ prediction**）；可写入 LS `predictions` 槽位供展示，**业务语义不是模型预测**；导出金标准不再将该槽位作 fallback（M6.1/M6.2）。**M4.3**：`rework-import` 默认只读 `previous_annotations/`，不读 `prelabels/`；`--export` 仅为 legacy 旁路。**M6.4**：快照模块命名/文档已收口。

**final**：自包含（含 `images/`、`masks/` 与相对路径清单）；未就绪或缺任务则失败，不改写已有 final。

**LS 本地文件**：`--local-root`（默认等于 `--data-root`）须与 Label Studio Local Storage 根一致。详见 [docs/labelstudio_usage.md](docs/labelstudio_usage.md)。

## 四角色部署包（M11）

按角色分发的薄包装见 [`deploy/v1/`](deploy/v1/)：

| 包 | 说明 |
|---|---|
| `data_processor` | 完整六命令（含本机全流程测试） |
| `annotator_seg` / `annotator_det` / `annotator_cap` | 本任务 LS 配置 + ls-import / export-split / rework-import |

不复制业务代码；入口调用 `mma` CLI。分发仅 `task_packages/`；详见该目录 README。

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
| [docs/M12.6_FINAL_FREEZE_REPORT.md](docs/M12.6_FINAL_FREEZE_REPORT.md) | M12.6 冻结验收报告 |
| [docs/data_layout.md](docs/data_layout.md) | 目录树、落盘与合并语义（含 legacy `prelabels/` 说明） |
| [docs/labelstudio_usage.md](docs/labelstudio_usage.md) | Label Studio 本地导入与标注（首轮 / 返工语义） |
| [docs/formats.md](docs/formats.md) | **Legacy** 预标注中间格式与 LS 控件名 |
| [docs/real_batch_local_test_runbook.md](docs/real_batch_local_test_runbook.md) | real_batch 全链路实测手册（**历史半自动步骤已标 Legacy**；V1 主路径见本文 README） |

开发约定见 `.cursor/rules/`（V1 Requirement / Development Tasks / Specifications）。功能分支开发；提交前本地跑通检查再 `git commit`。
