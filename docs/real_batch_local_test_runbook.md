# real_batch 本地真实数据全链路测试操作手册

> **V1 文档冻结说明（M0）**  
> **当前 V1 主流程不放置、不读取 `prelabels/`，首轮 `ls-import` 为空任务（无 prediction 预填）。**  
> 下文中「阶段 2：放置 prelabels」及「应看到预标注」等步骤是 **Legacy / 历史半自动 SOP**，仅供对照冻结 V2 联调记录，**不是** V1 必做。  
> 现行路径：`preprocess` → `package` → `ls-import`（空任务）→ Label Studio 人工标注 → `export-split` →（按需）`rework-import` → `merge`。详见仓库根 README 与 [labelstudio_usage.md](labelstudio_usage.md)。  
> 历史段落予以保留，不删除。

本文档是一份**自包含 SOP**：同伴在另一台 Windows 机器上，使用同一批 `real_batch` 真实数据，按本手册从零跑通 **P1 → P5**，且主流程**必须包含至少两轮返工**。

不替代 [data_layout.md](data_layout.md)、[formats.md](formats.md)、[labelstudio_usage.md](labelstudio_usage.md)；细节契约以仓库文档与代码为准。本手册不接入真实 SEG/DET/CAP 算法。历史联调曾使用统一中间格式预标注包（P2）；**V1 不再要求该包。**

---

## 1. 目的与范围

| 项 | 说明 |
|---|---|
| 目的 | 复现 `real_batch` 本地真实数据全链路联调 |
| 批次 | `batch_id = real_batch`，样本数 **N = 3** |
| 主流程（**V1 现行**） | preprocess → package → **ls-import（空任务，无 prelabels）** → LS 标注 → **export-split** → **返工第 1 轮** → **返工第 2 轮** → merge |
| 历史对照（Legacy，非 V1 必做） | 曾含「放置 prelabels」；见第 3.2 / 第 7 节 |
| 不包含 | 真实算法、网盘自动化、Web/DB、业务代码修改 |

---

## 2. 固定约定

| 项 | 值 |
|---|---|
| 项目根目录（强制） | `D:\多任务标注平台` |
| `--data-root` | `data`（即 `D:\多任务标注平台\data`） |
| `batch_id` | `real_batch` |
| 原图文件名 | `img_001.jpg`、`img_002.jpg`、`img_003.jpg` |
| Excel | `diagnoses.xlsx`；首表列名 `image_name`、`diagnosis_text` |
| 诊断文本 | `出血性内痔`（与联调一致） |
| `image_id`（preprocess 后） | `real_batch__000001`、`real_batch__000002`、`real_batch__000003`（以 `processed` manifest 为准） |
| `package_id` | `real_batch__seg` / `real_batch__det` / `real_batch__cap` |
| Label Studio 项目名 | **不强制**；须保证 XML 与 `tasks.json` 任务类型一一对应 |
| 导出轮次目录 | `data/ls_export/real_batch/{seg\|det\|cap}/round_00N/export.json` |

PowerShell 下多条命令请用 `;` 分隔，不要使用 `&&`。

---

## 3. 从负责人获取的材料

向负责人索取以下两包（可合并为一个压缩包），**不要**直接拷贝参考机整份 `data/`（其中 `processed` / `final` 可能含绝对路径，换机不可靠）。

### 3.1 源材料包（最小集）

| 文件 | 用途 |
|---|---|
| `img_001.jpg`、`img_002.jpg`、`img_003.jpg` | 原图 |
| `diagnoses.xlsx` | 诊断文本表 |
| `img_001.png`、`img_002.png`、`img_003.png` | **Legacy**：历史 SEG 预标注 mask 源文件；V1 首轮不需要 |

### 3.2 prelabels 包（**Legacy / 历史对照，V1 主流程不需要**）

解压后应得到：

```text
data/prelabels/real_batch/
├── seg/
│   ├── prelabels.json
│   └── masks/
│       ├── real_batch__000001.png
│       ├── real_batch__000002.png
│       └── real_batch__000003.png
├── det/
│   └── prelabels.json
└── cap/
    └── prelabels.json
```

DET 可为占位 bbox；CAP `caption` 可与 Excel 原文略有不同。放置时机见第 7 节（须先完成 preprocess，确认 `image_id` 与包内一致）。

---

## 4. 环境准备

### 4.1 安装本仓库（mma）

在 `D:\多任务标注平台`：

```powershell
cd D:\多任务标注平台
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
mma -h
```

**预期**：`mma -h` 列出 `preprocess`、`package`、`ls-import`、`export-split`、`rework-import`、`apply-current`、`merge` 等子命令。

### 4.2 Label Studio（独立 venv）

建议与 mma 分离，例如 `D:\labelstudio-env`。每次启动前在**同一 PowerShell 会话**设置：

```powershell
cd D:\labelstudio-env
.\.venv\Scripts\activate
$env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED = "true"
$env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT = "D:\多任务标注平台\data"
label-studio
```

浏览器打开 Label Studio（一般为 `http://localhost:8080`）并登录。

### 4.3 Local Files Source Storage（每个标注项目）

在 **SEG / DET / CAP 各项目**的 Settings → Cloud Storage → Add Source Storage → Local Files：

| 字段 | 值 |
|---|---|
| Absolute local path | `D:\多任务标注平台\data\task_packages` |

**不得**填 `D:\多任务标注平台\data`（与 `DOCUMENT_ROOT` 相同会被拒绝）。保存后按界面提示 Test / Sync（若有）。

图像 URL 形如：

```text
/data/local-files/?d=task_packages/real_batch/seg/images/real_batch__000001.jpg
```

对应磁盘文件：

```text
D:\多任务标注平台\data\task_packages\real_batch\seg\images\real_batch__000001.jpg
```

---

## 5. 阶段 0：整理 raw 目录

将源材料整理为：

```text
data/raw/real_batch/
├── images/
│   ├── img_001.jpg
│   ├── img_002.jpg
│   └── img_003.jpg
├── masks/
│   ├── img_001.png
│   ├── img_002.png
│   └── img_003.png
└── diagnoses.xlsx
```

- `images/` 内**只能**有 `.jpg` / `.jpeg`，不要放入 mask 或 xlsx。
- `masks/` 仅用于整理与对照；preprocess **不读取**该目录。mask 进入链路的方式是 prelabels 包内的 `seg/masks/<image_id>.png`。
- Excel 首表必须含列 `image_name`、`diagnosis_text`；`image_name` 为完整文件名且与三张图一一对应。

---

## 6. 阶段 1：preprocess + package

在项目根、已激活 mma 虚拟环境：

```powershell
mma preprocess --batch real_batch --images data/raw/real_batch/images --excel data/raw/real_batch/diagnoses.xlsx --data-root data
mma package --batch real_batch --data-root data
```

**预期成功**：

- 终端分别打印 `...\data\processed\real_batch` 与 `...\data\task_packages\real_batch`（或等价绝对路径）
- 存在 `data/processed/real_batch/manifest.json`，`items` 长度为 **3**
- 存在 `data/task_packages/real_batch/{seg,det,cap}/images/`，各含 3 张 `{image_id}.jpg`
- 各任务包 `manifest.json` 中 `package_id` 为 `real_batch__seg` / `__det` / `__cap`

打开 `processed` manifest，确认 `image_id` 与 `source_image_name` 对应关系。**V1 至此即可进入 `ls-import`；不必放置 prelabels。** 若仅对照历史半自动 SOP，放置步骤见第 7 节（Legacy）。

---

## 7. 阶段 2：放置 prelabels（**Legacy，跳过不影响 V1**）

向负责人索取 **prelabels 包**，解压到：

```text
D:\多任务标注平台\data\prelabels\real_batch\
```

**自检**：

- [ ] `seg` / `det` / `cap` 各有一份 `prelabels.json`，每份 `items` 长度为 3
- [ ] `image_id`、`diagnosis_text`、`batch_id` 与 `processed` manifest 一致
- [ ] `data/prelabels/real_batch/seg/masks/` 下存在三个按 `image_id` 命名的 `.png`

---

## 8. 阶段 3：ls-import + Label Studio 项目

### 8.1 生成导入 JSON

```powershell
mma ls-import --batch real_batch --task seg --data-root data
mma ls-import --batch real_batch --task det --data-root data
mma ls-import --batch real_batch --task cap --data-root data
```

**预期**：分别写出：

```text
data/ls_import/real_batch/seg/tasks.json
data/ls_import/real_batch/det/tasks.json
data/ls_import/real_batch/cap/tasks.json
```

每个文件为含 **3** 条任务的数组。

### 8.2 创建三个 Label Studio 项目

为 SEG / DET / CAP **各建一个项目**（名称自定）。在各项目 Labeling Interface 中分别粘贴：

| 任务 | XML 路径 |
|---|---|
| SEG | `D:\多任务标注平台\src\mma\labelstudio\configs\seg.xml` |
| DET | `D:\多任务标注平台\src\mma\labelstudio\configs\det.xml` |
| CAP | `D:\多任务标注平台\src\mma\labelstudio\configs\cap.xml` |

勿改 XML 中控件 `name`。按第 4.3 节为**每个项目**配置 Local Files Source Storage。

### 8.3 导入任务

| 项目 | 导入文件 |
|---|---|
| SEG | `data/ls_import/real_batch/seg/tasks.json` |
| DET | `data/ls_import/real_batch/det/tasks.json` |
| CAP | `data/ls_import/real_batch/cap/tasks.json` |

打开样本应能看到原图。**V1 首轮为空任务**，控件无模型/prelabel 预填；若仍见几何/文本，说明导入的是返工包或 Legacy convert 产物。不要混导任务类型。

---

## 9. 阶段 4：首轮标注与导出（round_001）

### 9.1 标注要求

对 **SEG / DET / CAP** 各 **3** 张图全部完成人工处理：

| 控件 | 要求 |
|---|---|
| 预标注 | **Legacy SOP**：可微调历史预填。**V1 首轮**：从空白人工绘制/填写 |
| `human_confirmed` | 全部选 **`yes`** |
| `needs_rework` | **至少 1 张**选 **`yes`**（建议某任务 1–2 张）；其余选 **`no`** |

首轮必须制造返工样本，否则无法进入后续强制返工轮。

### 9.2 导出

每个任务项目分别 Export → JSON，保存为：

```text
data/ls_export/real_batch/seg/round_001/export.json
data/ls_export/real_batch/det/round_001/export.json
data/ls_export/real_batch/cap/round_001/export.json
```

首轮为**全量轮**：每个 export 须包含本批该任务全部已标注样本（3 条）。**勿**把 SEG 的 export 用于 DET/CAP 命令。

---

## 10. 阶段 4.1：export-split（第 1 轮；含 current 同步）

对每个任务执行**一条** `export-split` 即可（内部已调用 apply-current；**不要**对同一 export 再跑 `apply-current`）：

```powershell
mma export-split --batch real_batch --task seg --export data/ls_export/real_batch/seg/round_001/export.json --data-root data
mma export-split --batch real_batch --task det --export data/ls_export/real_batch/det/round_001/export.json --data-root data
mma export-split --batch real_batch --task cap --export data/ls_export/real_batch/cap/round_001/export.json --data-root data
```

**预期**：

- `data/results/real_batch/{seg,det,cap}/current/annotations.json` 已更新
- 对应 `normal/annotations.json` 与 `rework/annotations.json` 已写出（有返工时 `rework` 非空）
- SEG 若导出含 brush/polygon，可能出现 `data/results/real_batch/seg/manual_masks/<image_id>_manual.png`
- 有返工时 `rework/previous_annotations/` 已写出（标注快照；不含原图）

**此时不要执行 `mma merge`**（仍存在 `should_rework` 为真的样本，例如未确认或 `needs_rework=true`）。

---

## 11. 阶段 4.2：返工第 1 轮（round_002）

本手册要求主流程**至少两轮返工**。本轮结束后仍须保留至少 1 张 `needs_rework=yes`，以便进入第 2 轮。

### 11.1 生成返工再导入任务

对每个任务（建议三任务都执行；无返工时产出可为 `[]`）。  
`apply-current` / `export-split` 已写出 `rework/previous_annotations/` 时执行：

```powershell
mma rework-import --batch real_batch --task seg --data-root data
mma rework-import --batch real_batch --task det --data-root data
mma rework-import --batch real_batch --task cap --data-root data
```

注意：`previous_annotations` **不含原图**；本机仍须有 `data/task_packages/real_batch/{seg,det,cap}/images/`（与首轮相同 Local Files 根）。无快照时 `rework-import` 失败，须先 `export-split` / `apply-current`（`--export` 不用于预填）。

**预期**：写出（不覆盖首轮 `tasks.json`）：

```text
data/ls_import/real_batch/{seg,det,cap}/rework_tasks.json
```

### 11.2 Label Studio 再标注

在对应项目中 Import `rework_tasks.json`（仅返工子集）。本轮：

- 已修好的样本：`human_confirmed=yes`，`needs_rework=no`
- **故意保留至少 1 张**：`needs_rework=yes`（为第 2 轮留样本）

### 11.3 导出与写回

导出到：

```text
data/ls_export/real_batch/{seg,det,cap}/round_002/export.json
```

返工轮允许**子集** export。然后对有更新的任务执行**一条** `export-split`（勿再跑 apply-current）：

```powershell
mma export-split --batch real_batch --task det --export data/ls_export/real_batch/det/round_002/export.json --data-root data
```

将 `<task>` 替换为实际更新的 `seg` / `det` / `cap`。

---

## 12. 阶段 4.3：返工第 2 轮（round_003）

### 12.1 再生成 rework 导入

基于 **round_002** 的 export：

```powershell
mma rework-import --batch real_batch --task seg --data-root data
mma rework-import --batch real_batch --task det --data-root data
mma rework-import --batch real_batch --task cap --data-root data
```

（仅对仍有返工样本的任务有实质任务条目；其余可为 `[]`。）

### 12.2 再标注（本轮清零返工）

Import 对应 `rework_tasks.json`，本轮要求：

- 全部样本 `human_confirmed=yes`
- 全部样本 `needs_rework=no`

### 12.3 导出与写回

导出到：

```text
data/ls_export/real_batch/{seg,det,cap}/round_003/export.json
```

然后执行**一条** `export-split`（勿再跑 apply-current）：

```powershell
mma export-split --batch real_batch --task cap --export data/ls_export/real_batch/cap/round_003/export.json --data-root data
```
### 12.4 merge 前自检

三路 `data/results/real_batch/{seg,det,cap}/current/annotations.json` 均满足：

- [ ] 各 3 条记录
- [ ] 全部 `human_confirmed: true`
- [ ] 全部 `needs_rework: false`
- [ ] `image_id` 集合与 `data/processed/real_batch/manifest.json` 全量一致

若某任务曾只 apply/export-split 子集，而 `current/` 仍残留旧返工标记，须对该任务再做**全量**导出并 `export-split`（或 `apply-current`），直至 `current/` 无返工残留。

---

## 13. 阶段 5：merge 与验收

```powershell
mma merge --batch real_batch --data-root data
```

**验收标准**：

1. 命令退出码为 0  
2. 存在文件 `data/final/real_batch/manifest.json`  
3. 该文件中 `items` 长度为 **3**（每条含 SEG + DET + CAP 字段）

**不要求** bbox / caption / `mask_ref` 等数值与参考机 `final` 完全一致；人工标注差异可接受。

---

## 14. 命令与产物对照表

| 步骤 | 命令或操作 | 关键产物 |
|---|---|---|
| 环境 | `pip install -e .`；`mma -h` | 可执行 `mma` |
| 阶段 0 | 整理 raw | `data/raw/real_batch/...` |
| 阶段 1 | `mma preprocess` / `mma package` | `processed/`、`task_packages/` |
| 阶段 2 | **V1 跳过**（Legacy：解压 prelabels 包） | 历史路径 `data/prelabels/real_batch/...` |
| 阶段 3 | `mma ls-import` ×3；LS 导入 | `ls_import/.../tasks.json` |
| 首轮标注 | LS 标注 + Export | `ls_export/.../round_001/export.json` |
| P4 第 1 轮 | `export-split` ×3（勿再连跑 apply-current） | `results/.../current|normal|rework/` |
| 返工第 1 轮 | `rework-import` → LS → Export → `export-split` | `rework_tasks.json`；`round_002/` |
| 返工第 2 轮 | 同上（基于 round_002） | `round_003/`；`current/` 无返工 |
| 合并 | `mma merge` | `data/final/real_batch/manifest.json` |

### 返工硬性规则（摘要）

1. **首轮**必须制造 ≥1 张 `needs_rework=yes`。  
2. **返工第 1 轮**结束后仍须保留 ≥1 张需返工。  
3. **返工第 2 轮**结束后三路 `current` 无返工，方可 `merge`。  
4. 每轮 export 按任务分目录；`export-split` / `rework-import` 的 `--task` 必须与 export 文件任务类型一致（`apply-current` 为底层等价入口，勿与 `export-split` 对同一文件连跑）。
