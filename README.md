# 医学图像多任务标注平台 V1（mma）

**状态**：Medical Image Multi-task Annotation Dataflow V1 Frozen（包版本 `0.1.0`）

V1 是基于冻结 V2 复制后的**独立项目**，面向纯人工医学图像**金标准**生产（SEG / DET / CAP）。医生在 Label Studio 上从空白任务开始标注，经返工闭环后，合并为每张图同时具备三类结果的最终数据集。

协作分发与回传走网盘。本仓库**不包含**业务服务端，也**不实现**预标注算法 / 大模型调用。

### 与冻结 V2 的差异（业务层，非代码兼容承诺）

| | V2（冻结参考） | V1 |
|---|---|---|
| 首轮导入 | 外部 `prelabels/` → LS `predictions` | 仅 `task_packages/` → 空任务（无模型/prelabel 预填） |
| 金标准来源 | 允许 prediction 回退填结果 | 仅人工 `annotation`；禁止 model/prelabel 进金标准 |
| 空标注 | 可能被 prediction 回填 | 空 / 缺结果 → `rework/` |
| prelabel 能力 | 主流程 | **隔离为 legacy**（历史参考，非主流程必做） |

## 流水线一览

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

**协作主路径**：数据处理者 `preprocess` → `package` 后，网盘只分发 `task_packages/<batch>/<task>/`。标注员本机完成导入 / 标注 / 导出 / 返工闭环。回传约定：进行中或换人交接只回传 `rework/`；本任务完成回传 `current/`（SEG 另含 `manual_masks/`）。处理者收齐三路完成态 `current/` 后 `merge`。

**本机全流程测试**：数据处理者可单人跑通 `preprocess → package → ls-import → export-split →（按需）rework-import → … → merge`，用于验收 / 纠错，**不替代**标注员职责。完整 SOP 见 [docs/V1_LOCAL_FULL_CHAIN_TEST_REPORT.md](docs/V1_LOCAL_FULL_CHAIN_TEST_REPORT.md)。

## 角色与部署

四角色薄包装见 [`deploy/v1/`](deploy/v1/)：不复制业务代码，入口调用已安装的 `mma` CLI。

| 角色 | 负责 | 允许的命令 | 禁止 |
|---|---|---|---|
| 数据处理者 `data_processor` | 预处理、拆包、网盘分发 `task_packages/`；收集完成态 `current/`（SEG 另含 `manual_masks/`）后 `merge`；本机可跑全流程测试 | `preprocess`、`package`、`ls-import`、`export-split`、`rework-import`、`merge` | 准备或分发 `prelabels/`；使用 `mma convert` |
| SEG 标注员 `annotator_seg` | 下载 SEG 任务包；本机空任务导入、人工分割、导出、返工闭环至 `rework/` 为空 | 本任务 `ls-import` / `export-split` / `rework-import`（强制 `--task seg`） | `preprocess`、`package`、`merge`；DET/CAP 配置与数据 |
| DET 标注员 `annotator_det` | 同上，仅目标检测 | 本任务三命令（强制 `--task det`） | `preprocess`、`package`、`merge`；SEG/CAP |
| CAP 标注员 `annotator_cap` | 同上，仅文本描述 | 本任务三命令（强制 `--task cap`） | `preprocess`、`package`、`merge`；SEG/DET |

回传：未完成 / 交接质检回传 `results/<batch>/<task>/rework/`；完成态回传 `current/`（SEG 另附 `manual_masks/`）。换人交接三件套：`current/` + `rework/` + 对应 `task_packages/<batch>/<task>/`。

分发、回传与各包操作说明见 [`deploy/v1/README.md`](deploy/v1/README.md)。

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

验证（需另装 pytest，不在运行时依赖中）：

```bash
pip install pytest
pytest
```

默认 `addopts = -m "not legacy"`，历史参考用例被 deselect。仅测 legacy：`pytest -m legacy`。

调用关系：

```text
src/mma（业务实现）
  → mma CLI（`mma` / `python -m mma`）
  → deploy/v1 角色入口（薄包装，不复制业务代码）
```

**原始输入**：图像为 `.jpg`；诊断 Excel 为 `.xlsx`，首表列名固定 `image_name` / `diagnosis_text`。

## CLI 速查

| 命令 | 作用 | 主要产出 |
|------|------|----------|
| `preprocess` | 图文配对、分配 `image_id` | `processed/<batch>/manifest.json`（引用原图，不复制） |
| `package` | 拆 SEG/DET/CAP 全量任务包 | `task_packages/<batch>/{seg,det,cap}/` |
| `ls-import` | 生成首轮 LS 空任务导入 | `ls_import/<batch>/<task>/tasks.json` |
| `export-split` | **推荐**：导出落盘 + 分类 | 更新 `current/`，重建 `normal/`、`rework/` |
| `apply-current` | 底层：仅同步 `current/`（也会刷新 normal/rework） | 同左；日常优先用 `export-split` |
| `rework-import` | 生成返工再导入任务 | `ls_import/<batch>/<task>/rework_tasks.json` |
| `merge` | 三任务合并为最终集 | `final/<batch>/{manifest.json,images/,masks/}` |
| `convert` | **Legacy stub**（退出码 2；V1 不作为 prelabel 转换入口） | — |

`export-split` 与 `apply-current` 对**同一份 export 二选一**，勿连跑。`--task` 仅允许：`seg`、`det`、`cap`。

### 常用命令

```bash
# 1. 预处理 + 拆包
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

# 4. 有返工时再导入（只读 rework/previous_annotations/）
# 返工预填 = 上一轮人工历史；业务上 ≠ 模型 prediction（LS 字段名可能仍叫 predictions）
mma rework-import --batch demo_batch --task cap --data-root data

# 5. 三路 current 均无返工后合并
mma merge --batch demo_batch --data-root data
```

## 关键约定（必读）

**权威结果**：每任务以 `results/<batch>/<task>/current/` 为准。按 `image_id` **合并覆盖**——本轮 export 出现的覆盖；current 已有且本轮未出现的保留。任务包有、但本轮 export 与 current 都没有的样本，写入空结果（未确认、无有效载荷）并进入 `rework/`。export 含任务包没有的 `image_id` 则整批失败。`export-split` / `apply-current` 必须能读到对应任务包 `manifest.json`。

**分类规则**：`should_rework_result = (not human_confirmed) or needs_rework or (not effective_payload)`。仅「已确认、不需返工、且有有效任务载荷」进 `normal/`；其余进 `rework/`（含未提交、空 result、未勾确认、空框/空文案、SEG 空 mask）。未提交或空 result **不中断整批** `export-split`。每次 `export-split` / `apply-current` 后按最新 `current/` **全量重建** normal/rework。

**有效载荷**：DET ≥1 框；CAP strip 后非空文案；SEG 非空 `mask_ref` 且 `has_foreground=True`。`has_foreground` 由 mask **像素**计算（`compute_has_foreground`）：文件缺失或全黑为 `False`；JSON 字段只做类型校验，不能覆盖 mask。合并就绪校验对「已确认且未勾返工但空载荷」报 `empty task payload`。

**金标准来源**：有效结果仅来自人工 `annotation`；不以 LS `predictions` 回填金标准。SEG 不以 `data.mask_ref` 或 pred 几何作金标准（空/无几何写 `manual_masks/`）。

**首轮导入**：`tasks.json` 每条仅含 `data.image` / `image_id` / `package_id` / `diagnosis_text`；**无** `predictions`、`mask_ref` 或 prelabel 字段。输入仅为 `task_packages/`。

**SEG**：人工几何或空/confirm-only 写入 `manual_masks/`。首轮导入无预填。

**DET / CAP**：首轮导入无预填框/文本；导出不回填 prediction；人工清空或 confirm-only → 空框 / 空文案。

**返工预填**：`previous_annotations` = 上一轮**人工**快照（**`previous_annotations` ≠ prediction**）；可写入 LS `predictions` 槽位供展示，**业务语义不是模型预测**，导出金标准不将该槽位作 fallback。`rework-import` 只读 `previous_annotations/`，不读 `prelabels/`；无快照须先 `export-split`（或 `apply-current`）。`--export` 已 deprecated，不用于预填。

**final**：自包含（含 `images/`、`masks/` 与相对路径清单）；未就绪或缺任务则失败，不改写已有 final。拷图优先 `task_packages/<batch>/{seg,det,cap}/images/`，processed 源图路径仅作回退。

**LS 本地文件**：`--local-root`（默认等于 `--data-root`）须与 Label Studio Local Storage 根一致。详见 [docs/labelstudio_usage.md](docs/labelstudio_usage.md)。

## Legacy 参考（非 V1 主流程）

以下内容保留供对照冻结 V2 / 历史测试，**不是** V1 主流程必做步骤：

| 路径 | 说明 |
|------|------|
| [docs/formats.md](docs/formats.md) | **Legacy**：预标注统一中间格式与转换约定 |
| [examples/prelabels/](examples/prelabels/) | **Legacy**：历史样例 `prelabels.json` |
| [examples/README.md](examples/README.md) | **Legacy**：adapter → prelabel → LS 演示（`run_p2_demo.py`） |

## 更多文档

| 文档 | 内容 |
|------|------|
| [docs/V1_LOCAL_FULL_CHAIN_TEST_REPORT.md](docs/V1_LOCAL_FULL_CHAIN_TEST_REPORT.md) | 本地真实数据全链路验收 SOP |
| [docs/data_layout.md](docs/data_layout.md) | 目录树、落盘与合并语义 |
| [docs/labelstudio_usage.md](docs/labelstudio_usage.md) | Label Studio 本地导入与标注（首轮 / 返工语义） |
| [deploy/v1/README.md](deploy/v1/README.md) | 四角色部署包、分发与回传 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |

维护者开发约定见 `.cursor/rules/`。
