# 批次 / 任务包 / 结果包落盘规范

本文档约定本地运行时数据目录的命名、层级与职责，供 V1 流水线与 CLI 统一遵循。  
运行时根目录为项目下的 `data/`（已列入 `.gitignore`，不入库）。

**V1 目标**：纯人工金标准；主流程图**不**包含外部写入 `prelabels/` 或模型预标注步骤。  
**主路径现状（Sprint A/B/C）**：`ls-import` 仅读 `task_packages/`（无 `prelabels/`）；金标准仅人工 annotation（无 prediction fallback）；返工预填源为 `previous_annotations`（人工历史）。`prelabels/` 仅 Legacy。未完成项见仓库根 `CHANGELOG.md`「Planned」与 `.cursor/rules/V1 Development Tasks.md`。

默认数据根、Excel 列名等**不由** `configs/default.yaml` 加载，而由 `common/paths.py`、`common/io.py` 与 CLI 参数约定（配置内嵌）。

相关数据契约见 `src/mma/common/models.py`。

---

## 1. 总原则

1. **批次隔离**：几乎所有阶段以 `batch_id` 为一级键。
2. **三任务物理隔离**：自 `task_packages` 起，SEG / DET / CAP 使用独立子目录；合并前互不写对方路径。
3. **唯一汇合点**：仅 `final/<batch_id>/` 合并三类最终结果。
4. **当前有效结果权威目录**：`results/<batch_id>/<task>/current/` 只保留覆盖后的当前版。
5. **网盘友好**：整目录拷贝某一任务子树即可分发/回收；传输过程无自动化代码要求。
6. **V1 主流程不依赖 prelabels**：目标运行时仅需 raw → processed → task_packages → ls_import → … → final；`prelabels/` 为 **Legacy**（见 §4.4）。
---

## 2. 命名约定

### 2.1 标识符

| 标识 | 规则 | 目录中的体现 |
|---|---|---|
| `batch_id` | 字母、数字、`-`、`_`；禁止 `/`、`\` 及空白 | `data/<stage>/<batch_id>/` |
| `task_type`（契约） | `SEG` / `DET` / `CAP` | — |
| 任务子目录名 | 小写：`seg` / `det` / `cap`（与 CLI `--task` 一致） | `.../<batch_id>/{seg,det,cap}/` |
| `package_id` | 全局可区分的字符串 | **不**单独建目录层；写入该任务包 `manifest.json` |
| `image_id` | 批内唯一 | **不**作为海量目录层级；写入清单/结果 JSON；图像文件建议 `{image_id}.jpg` 或源名 + 清单映射 |

目录名与清单字段中的 `batch_id` 必须一致。  
契约枚举值为大写（`SEG`）；路径段为小写（`seg`）。

### 2.2 路径相对性

自 **task_packages** 起，清单与结果 JSON 内的文件路径，默认写成**相对于所属阶段包根目录**的相对路径（例如相对 `task_packages/<batch_id>/seg/`），便于整包网盘迁移。  
跨阶段引用时，由后续模块按本规范解析。

**例外（processed）**：`processed/<batch_id>/manifest.json` 中的 `image_path` **允许写入预处理时解析得到的绝对路径**（当前 `preprocess` 实现：引用 `--images` 目录下原图，本阶段不强制改为相对路径）。任务包拆分（`package`）按该路径读源图并复制进各任务包；网盘分发以 **task_packages** 为准，不依赖 processed 中绝对路径的可迁移性。  
换机/换盘后若原绝对路径不可读，须**重新执行 preprocess**（或保证原图绝对路径仍可读）后再 `package`。  
`final/<batch_id>/manifest.json` 的 `image_path` / `seg.mask_ref` 在 merge 时**改为相对路径**（`images/{image_id}.jpg`、`masks/{image_id}.png`），并复制资源进 final 目录，因此 final 包可独立迁移。

---

## 3. 目录树

```text
data/
├── raw/<batch_id>/
├── processed/<batch_id>/
├── task_packages/<batch_id>/{seg,det,cap}/
├── prelabels/<batch_id>/{seg,det,cap}/   # LEGACY：非 V1 目标运行时必需
├── ls_import/<batch_id>/{seg,det,cap}/
├── ls_export/<batch_id>/{seg,det,cap}/
├── results/<batch_id>/{seg,det,cap}/
│   ├── normal/
│   ├── rework/
│   │   ├── annotations.json
│   │   └── previous_annotations/   # 上一轮人工标注快照（不含原图）
│   │       ├── <task>.json
│   │       └── masks/              # 仅 seg
│   ├── current/
│   └── manual_masks/          # 仅 seg：人工 brush/polygon 落盘
└── final/<batch_id>/
    ├── images/                 # merge 时复制的原图（统一 {image_id}.jpg）
    ├── masks/                  # merge 时物化的统一 SEG mask
    └── manifest.json           # 相对路径索引；不依赖 raw/processed/prelabels
```

主流程目录（V1）：`raw` → `processed` → `task_packages` → `ls_import` → `ls_export` → `results` → `final`。  
`prelabels/` 不在主流程图内（Legacy only）。
---

## 4. 各目录职责与建议内容

### 4.1 `raw/<batch_id>/`

| 项目 | 说明 |
|---|---|
| 职责 | 原始输入；流水线只读 |
| 内容 | 原始 `.jpg`、诊断文本 Excel（`.xlsx`；若仅有 `.xls` 须先人工转为 `.xlsx`） |
| 关键文件 | 可由数据处理人员约定；P1 通过 CLI 参数显式传入图像目录与 Excel 路径 |

### 4.2 `processed/<batch_id>/`

| 项目 | 说明 |
|---|---|
| 职责 | 预处理阶段产出的**标准化索引与图文绑定结果**（稳定 `image_id` + 图像与诊断文本一一对应） |
| 必须内容 | `manifest.json`（或同等清单：每条含 `image_id`、`image_path`、`diagnosis_text`、可选 `source_image_name` / `batch_id`） |
| `image_path` 形态 | **允许绝对路径**（与当前 `preprocess` 实现一致）；不作为网盘迁移载体 |
| 图像文件 | **不强制**在本目录复制或落盘图像；`image_path` 可指向 `raw` 或其他约定位置 |
| 是否复制图像 | 由 **P1 实现阶段**根据数据规模、磁盘占用与部署方式决定（引用原图 / 复制到本目录 / 其它策略均可，但须在清单中写清可解析路径） |
| 消费者 | 任务包拆分（P1） |

### 4.3 `task_packages/<batch_id>/{seg,det,cap}/`

| 项目 | 说明 |
|---|---|
| 职责 | 按任务类型拆分的**全量**任务包（每类样本数 = 预处理有效图像数 N） |
| 建议内容 | `images/`、诊断文本清单、`manifest.json` |
| `manifest.json` 必填 | `package_id`、`task_type`（`SEG`/`DET`/`CAP`）、`batch_id`、样本列表（`image_id`、`image_path`、`diagnosis_text`） |
| 重跑对齐 | `mma package` 重跑时，各任务 `images/` 与当前 `processed` 清单对齐：按期望文件名做差集，**删除清单外文件**（含同 `image_id` 旧后缀、杂文件）；`images/` 下若出现子目录则失败。已发出的旧网盘包需人工重新分发 |
| 网盘 | 整目录分发给对应任务标注员 |

同一 `batch_id` 下恰好三个任务目录；每个目录对应一个 `package_id`（写在 manifest 中，不另建 `package_id` 目录层）。

### 4.4 `prelabels/<batch_id>/{seg,det,cap}/`（**Legacy**）

| 项目 | 说明 |
|---|---|
| V1 地位 | **非**运行时必需目录；保留供冻结 V2 对照与历史测试（Legacy） |
| 历史职责 | 预标注落点；统一中间格式主文件为 `prelabels.json`（字段见 **Legacy** 文档 `docs/formats.md`） |
| SEG 资源 | 历史约定可含 `masks/`；`mask_ref` 相对本任务 prelabels 目录根 |
| 样例 | `examples/prelabels/`（已标 Legacy） |
| 主路径 | `mma ls-import` / `rework-import` **不读取**本目录（M4 / M4.3 / M5.3） |

### 4.5 `ls_import/<batch_id>/{seg,det,cap}/`

| 项目 | 说明 |
|---|---|
| 职责 | Label Studio 可导入任务与配套资源 |
| 必须内容 | `tasks.json`（首轮）或 `rework_tasks.json`（返工轮，不覆盖首轮文件） |
| 图像 | **不复制**；`data.image` 使用 Local Files URL：`/data/local-files/?d=<相对 local_root 的正斜杠路径>` |
| 默认相对路径 | 相对 `data_root`（常与 LS Local storage 根一致），例如 `task_packages/<batch_id>/seg/images/<image_id>.jpg` |
| 图像来源 | 优先解析 `task_packages/<batch_id>/<task>/images/{image_id}.jpg\|.jpeg` |
| 输入（V1） | **仅** `task_packages/`；首轮任务仅含 `data`（`image` / `image_id` / `package_id` / `diagnosis_text`），**无** `predictions`；不读 `prelabels/`（M4 已落地） |
| CLI | `mma ls-import --batch <id> --task {seg\|det\|cap} [--data-root] [--local-root]` |
| 消费者 | Label Studio 本地导入与返工再导入；工作台 XML 用包内 `labelstudio/configs/*.xml`（不拷贝到本目录） |
### 4.6 `ls_export/<batch_id>/{seg,det,cap}/`

| 项目 | 说明 |
|---|---|
| 职责 | Label Studio 本轮导出原文 |
| 建议 | 按轮次分子目录，避免覆盖历史排障材料：`round_001/`、`round_002/`、… |
| 内容 | 导出 JSON（及 LS 附带资源，若有） |

### 4.7 `results/<batch_id>/{seg,det,cap}/`

#### `normal/`

- 本轮（相对最新 `current/`）分类结果：`should_rework(...)` 为 **false**
  - 即 `human_confirmed == true` **且** `needs_rework == false`
  - 判定函数：`mma.common.models.should_rework`
- **始终表示当前全部已达最终确认状态的样本**；由 `apply-current` / `export-split` 在更新 `current/` 后**全量重建**（禁止按历史 append）
- 建议按轮次另存快照：`normal/round_XXX/`（可选；权威仍以最新 `normal/annotations.json` 为准）
- 用于网盘回传「正常结果包」

#### `rework/`

- 本轮（相对最新 `current/`）分类结果：`should_rework(...)` 为 **true**
  - 定义：`should_rework = (not human_confirmed) OR needs_rework`
  - **含义：未达到最终确认状态**，而不是「仅 `needs_rework=True`」
  - 包含：
    - `human_confirmed == false`（无论 `needs_rework`）
    - `human_confirmed == true` **且** `needs_rework == true`
- 与 `normal/` 同样在每次 apply / export-split 后**全量重建**
- 建议按轮次另存快照：`rework/round_XXX/`（可选）
- 用于网盘回传与返工再导入输入（未确认样本一并进入返工闭环）
- **自包含上一轮标注快照**（`apply-current` / `export-split` 刷新 rework 时同步写出）：

```text
results/<batch>/<task>/rework/
├── annotations.json
└── previous_annotations/
    ├── <task>.json          # det.json | seg.json | cap.json
    └── masks/               # 仅 SEG：复制的 mask PNG
        └── {image_id}.png
```

  - 「自包含」指**标注几何/文本快照**可脱离原始 LS export；**不**包含原图。`rework-import` 仍需同批 `task_packages/.../images/`（及 manifest）生成 `data.image` Local Files URL
  - 数据来自 `TaskAnnotationResult.annotation`（**人工历史**），**不依赖** LS export raw；业务上 **`previous_annotations` ≠ 模型 / prelabel prediction**
  - 返工导入写入 LS 时可能仍使用字段名 `predictions` 承载上述人工历史，仅供工作台预填展示；**不得**再作为导出金标准的 prediction fallback 源（M6.1 已禁止；M4.3 主路径只读本目录）
  - DET：`bboxes[{x,y,width,height}]`（像素；`BBox` 无 label 字段，快照不伪造 label）
  - CAP：`{image_id, caption}`
  - SEG：复制 mask 到 `previous_annotations/masks/`，并用 `build_seg_polygon_results` 写入 `polygons`（空 mask → `polygons: []`）
  - `mma rework-import` **优先**读此目录生成 `rework_tasks.json`；无此目录时才回退 `--export`（旧包兼容）
#### `current/`

- **该任务、该批次的唯一当前有效结果权威目录**
- 写入语义：同 `image_id` **覆盖**旧标注与旧勾选，不并行保留多版有效结果
- **按 `image_id` 合并写入**（`apply-current` / `export-split` → `overwrite_current`）：
  - 本轮解析到的每个 `image_id`：覆盖标注与「人工确认 / 是否返工」勾选
  - **未出现在本轮写入集合中的 `image_id`：保留原记录**（非整表清空）
  - 本轮结果为空时：**不改写**已有 `current/`（no-op）
- **操作约定**（日常推荐 `export-split`；与 `apply-current` 对同一 export **二选一**）：
  - **全量轮**（首轮或意图刷新该任务整批权威状态）：应从对应 LS 项目导出本批该任务**全部已处理样本**，再执行 `export-split`（或等价的 `apply-current`）
  - **返工轮**：允许只导出返工子集再 `export-split` / `apply-current`；未出现的 id **刻意保留**上一轮有效结果（含已 normal 的样本）
  - **禁止**：从全量项目中随意导出少量样本并 apply，却期望其余样本被自动删除或状态被清空
- 合并（P5）只读各任务的 `current/`
- 建议清单文件：`current/annotations.json`（字段对齐 `TaskAnnotationResult`）。可选字段 `export_round`：当 `--export` 位于 `.../round_NNN/` 下时，由 `apply-current` / `export-split` 填入整数轮次（`round_001` → `1`）；非轮次目录为 `null`。**仅追溯**，分类/合并仍只看勾选与 `image_id`；历史排障仍可对照 `ls_export/.../round_XXX/`（及可选的 `normal|rework/round_XXX/` 快照）

#### `manual_masks/`（仅 SEG）

- 路径：`results/<batch_id>/seg/manual_masks/`
- 由 `apply-current` / `export-split` 写出：`{image_id}_manual.png`
- 写出时机（与解析一致）：
  - 本轮有效结果含 **BrushLabels** RLE → 解码写 PNG
  - 本轮有效结果含 **PolygonLabels** → 栅格化写 PNG
  - 有 SEG 操作记录但为空 → 写空 mask PNG
  - **无** SEG 操作记录 → 写空 `manual_masks/`（annotation-only；不再回退 `data.mask_ref` / prelabel）；空/缺有效载荷 → `rework/`（`should_rework_result`）
- `SegAnnotation.mask_ref` 存相对 `results/<batch_id>/seg/` 的路径：`manual_masks/{image_id}_manual.png`
- Legacy：历史实现约定不覆盖 `prelabels/.../masks/`（若目录仍存在）
- **清理**：`apply-current` / `export-split`（SEG）在刷新 `current/` 与 normal/rework 后，按 current 中仍引用的 `manual_masks/` 路径保留文件；删除目录内未被引用的 `*_manual.png`（缺 `current/annotations.json` 时不清理）
`normal/` / `rework/` 是轮次快照；**业务上的当前有效状态以 `current/` 为准**。

### 4.8 `final/<batch_id>/`

| 项目 | 说明 |
|---|---|
| 职责 | 三任务合并后的多任务最终数据集 |
| 前置 | 三路 `results/<batch_id>/{seg,det,cap}/current/` 均就绪，且无返工残留；三路 `image_id` 集合彼此一致且**等于** `processed/<batch_id>/manifest.json` 全量集合；processed 可回填图文 |
| 内容 | 关键清单 `manifest.json`：`{"batch_id", "items"}`；每条对齐 `MergedMultitaskRecord`（必含 SEG+DET+CAP，以及相对路径 `image_path`/`diagnosis_text`）；`image_path` **必须**为 `images/{image_id}.jpg`；缺任务必须阻断，禁止静默缺字段 |
| SEG mask | merge 时复制到 `final/<batch_id>/masks/{image_id}.png`；清单内 `seg.mask_ref` **必须**为 `masks/{image_id}.png`（相对本 final 批次目录）。禁止绝对路径与 `final_assets/` / `manual_masks/` / `prelabels/` 根；空 mask 只复制、不重生成。不修改 `prelabels/` / `manual_masks/` / `current/` |
| 原图 | merge 时从 processed 的 `image_path` 复制到 `final/<batch_id>/images/{image_id}.jpg`（源为 `.jpeg` 时目标仍统一为 `.jpg`）。final 包自包含，迁移后不依赖 raw/processed |

---

## 5. 数据生命周期与目录映射

**V1 目标主流程**（无 prelabel 步骤）：

```text
raw
  → processed
  → task_packages/{seg,det,cap}
  → ls_import/{seg,det,cap}     # 空任务；仅 task_packages/
  → ls_export/{seg,det,cap}/round_XXX
  → results/.../normal|rework
  → results/.../current         # 覆盖写入当前有效版
  →（返工闭环：rework/previous_annotations → ls_import/rework_tasks → ls_export → 分类 → 覆盖 current）
  → final                       # 三任务均无返工后
```

| 业务状态（单任务、单图） | 主要落盘 |
|---|---|
| 已拆包待首轮导入 | `task_packages` 已有 → `ls_import`（目标无需 `prelabels`） |
| 本轮已处理（无需/需返工） | `ls_export` → `results/.../normal` 或 `rework` |
| 当前有效结果 | `results/.../current` |
| 可进入最终集合并 | 三路 `current` 就绪且均无需返工 → `final` |
| Legacy：历史半自动预标注 | `prelabels/`（非 V1 目标状态机节点） |
---

## 6. 三任务独立链路（落盘约束）

1. 自 `task_packages` 至 `results`，一律按 `{seg,det,cap}` 分目录。
2. 任一任务目录的写入不得改写另外两个任务目录。
3. CLI 带 `--task {seg|det|cap}` 时仅触达对应子树。
4. 唯一跨任务汇合目录为 `final/<batch_id>/`。

---

## 7. 返工覆盖规则（落盘语义）

1. 每轮导出解析后，将有效结果**覆盖写入**对应任务的 `current/`。此处「覆盖」针对**本轮 export 中出现的** `image_id`；未出现在本轮集合中的样本**不删除**，以支持返工子集再写入。
2. 同一 `image_id` + 同一任务再次写入时，替换旧标注与「人工确认 / 是否返工」勾选。
3. `current/` 中不并行保留历史多版本作为有效结果（同一 id 只保留最新一版）。
4. **`current/` 为唯一真实数据源**。每次 `apply-current` / `export-split` 在更新 `current/` 后，必须按完整 `current/` **全量重建** `normal/` 与 `rework/`（覆盖写盘，禁止 append 历史子集）。
5. 因此 `normal/` 始终等于「当前全部 `not should_rework` 样本」（已确认且不需返工）；`rework/` 等于「未达最终确认状态」样本。返工修好的 id 会从 rework 进入 normal，无需手工合并首轮 normal。
6. `ls_export` 与可选的 `normal|rework/round_XXX/` 快照用于追溯与网盘协作，不替代 `current/` 的权威语义。
7. 返工再导入必须能展示上一轮**人工**结果：优先使用 `rework/previous_annotations/`（标注快照自包含；**原图仍依赖** `task_packages`）。旧包无该目录时回退 `--export`（legacy）。`previous_annotations` ≠ 模型 / prelabel prediction；写入 LS 的 `predictions` 槽仅供预填；导出金标准禁止 prediction fallback（M6.1 / M4.3 已落地）。
8. 仅当三任务 `current/` 均无 `should_rework_result` 残留（已确认、不需返工、且有有效任务载荷），且三路 `image_id` 集合彼此一致并与 `processed` 全量集合相等时，才允许生成 `final/<batch_id>/`。

## 8. 关键文件约定（最小集）

| 位置 | 文件 | 用途 |
|---|---|---|
| `processed/<batch_id>/` | `manifest.json` | 标准化索引与图文绑定清单（含 `image_id`、`image_path`、`diagnosis_text`）；图像是否复制见 §4.2 |
| `task_packages/<batch_id>/<task>/` | `manifest.json` | `package_id`、`task_type`、`batch_id`、样本列表 |
| `prelabels/<batch_id>/<task>/` | `prelabels.json` | **Legacy**；主路径不读；格式见 `docs/formats.md` |
| `results/<batch_id>/<task>/current/` | `annotations.json` | 当前有效 `TaskAnnotationResult` 列表 |
| `final/<batch_id>/` | `manifest.json` | 合并后的多任务记录清单（字段对齐 `MergedMultitaskRecord`）；`image_path`=`images/{image_id}.jpg`；`seg.mask_ref`=`masks/{image_id}.png` |
| `final/<batch_id>/images/` | `{image_id}.jpg` | merge 时从 processed 源图复制（目标扩展名统一 `.jpg`） |
| `final/<batch_id>/masks/` | `{image_id}.png` | merge 时物化的统一 SEG mask（来源以 current / manual 为准；勿再依赖 prelabel 根） |

轮次目录名建议：`round_001`、`round_002`、…（三位零填充，便于排序）。`TaskAnnotationResult.export_round` 由 `parse_export_round_from_path` 从 export 父目录解析并经 `apply-current` / `export-split` 写入 `current/`；非 `round_*` 布局仍为 `null`。

业务结果 JSON 字段以 `mma.common.models` 为准。Legacy 预标注中间格式见 `docs/formats.md`。
---

## 9. 与后续任务的边界

| 本规范包含 | 本规范不包含 |
|---|---|
| 目录层级、命名、职责、覆盖语义 | 真实 jpg/Excel 读写实现细节 |
| 与 `batch_id` / `package_id` / `task_type` / `image_id` 的对应关系 | Label Studio XML / 导入 JSON 字段级细节（见 `labelstudio_usage.md`） |
| 三任务隔离与 `final` 汇合规则 | 网盘自动上传下载、预标注算法 / 大模型调用 |
| `processed/` 必须产出索引与图文绑定 | V1 代码改造本身（见 Development Tasks M1–M6） |
| Legacy `prelabels/` 目录的存在说明 | 将 Legacy 路径当作 V1 主流程必做步骤 |

路径解析辅助见 `common/paths.py`；与本文档不一致时以代码与 CHANGELOG Planned/落地条目对照。
