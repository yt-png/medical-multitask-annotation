# V1 四角色部署包 · 开发者本地独立验收操作手册（real_batch）

本文档面向**开发者交付前自测**：把 `deploy/v1/` 四个角色包当作即将发给数据处理员 / SEG / DET / CAP 标注员的真实交付物，在**独立目录 + 独立虚拟环境 + 独立 `data/`** 下按职责验收全部允许 CLI，并验证越界命令被拦截。

本文**不替代**：

- 仓库级全链路 SOP：[real_batch_local_test_runbook.md](real_batch_local_test_runbook.md)
- 目录契约：[data_layout.md](data_layout.md)
- Label Studio 用法：[labelstudio_usage.md](labelstudio_usage.md)
- 角色包说明：`deploy/v1/README.md` 及各角色 README

材料约定（`batch_id`、N=3、Excel 列名、诊断文本）与全链路手册一致；步骤全部改为 **deploy 薄入口 + 沙箱隔离**。

---

## 0. 目的、范围与总验收标准

| 项 | 说明 |
|---|---|
| 目的 | 确认四角色包可独立交付、按职责运行、交接目录契约正确 |
| 批次 | `batch_id = real_batch`，样本数 **N = 3** |
| 操作系统 | Windows + PowerShell（多条命令用 `;` 分隔，不要用 `&&`） |
| 仓库根（本机示例） | `D:\多任务标注平台V1` |
| 沙箱根（强制，仓库外） | `D:\deploy_acceptance\` |
| V1 硬约束 | 无 `prelabels/`、不调用 `mma convert`、首轮空任务、金标准仅人工 annotation |

**总验收标准（全部满足才算通过）：**

1. 四个沙箱互不共用 `data/`、互不共用 `.venv`。
2. 每个角色**允许的全部 CLI 入口**在本沙箱正向跑通。
3. 每个标注员沙箱的**越界负向用例**全部按预期失败（退出码 2 或脚本不存在）。
4. 网盘式 handoff：只分发 `task_packages/<batch>/<task>/`；完成态回传 `current/`（SEG 另附 `manual_masks/`）；处理员收集后 `merge` 得到 `final/real_batch/`。
5. 静态契约可对照自动化测试 `tests/test_m11_deploy.py`；本手册覆盖运行时 + Label Studio + 真实数据。

---

## 1. 四沙箱隔离架构

```text
D:\deploy_acceptance\
├── sandbox_data_processor\
│   ├── _lib\                 # 从仓库 deploy/v1/_lib 复制
│   ├── data_processor\       # 从仓库 deploy/v1/data_processor 复制
│   ├── .venv\
│   └── data\                 # 本沙箱独立数据根
├── sandbox_annotator_seg\
│   ├── _lib\
│   ├── annotator_seg\
│   ├── .venv\
│   └── data\
├── sandbox_annotator_det\
│   ├── _lib\
│   ├── annotator_det\
│   ├── .venv\
│   └── data\
└── sandbox_annotator_cap\
    ├── _lib\
    ├── annotator_cap\
    ├── .venv\
    └── data\
```

**层级说明（必须遵守）：** 薄入口脚本用 `Path(__file__).parents[2]` 定位 `_lib`。因此 `_lib` 必须与角色目录**同级**，位于沙箱根下。不要把角色目录内容直接摊到沙箱根（否则 `_lib` 解析失败）。

```text
[data_processor 沙箱]
  preprocess → package
        │  拷贝 task_packages/<batch>/<task>/   （模拟网盘分发）
        ▼
[annotator_seg / det / cap 沙箱]  各只含本任务包
  ls-import → LS 标注 → export-split → rework-import 闭环
        │  拷贝 results/<batch>/<task>/current/  （SEG + manual_masks/）
        ▼
[data_processor 沙箱]
  merge → final/<batch>/
```

四沙箱**禁止**共用一个 `data/`，只允许目录拷贝模拟网盘。

---

## 2. 固定约定

| 项 | 值 |
|---|---|
| `--data-root` | **始终使用本沙箱 `data` 的绝对路径** |
| `batch_id` | `real_batch` |
| 原图 | `img_001.jpg`、`img_002.jpg`、`img_003.jpg` |
| Excel | `diagnoses.xlsx`；列名 `image_name`、`diagnosis_text` |
| 诊断文本 | `出血性内痔` |
| `image_id` | `real_batch__000001` … `000003`（以 processed manifest 为准） |
| `package_id` | `real_batch__seg` / `__det` / `__cap` |
| 命令入口 | 一律 `python bin/<script>.py ...`，不要用仓库根的 `mma` 代替角色验收（对照说明除外） |
| 标注员 `--task` | **不要手写**；脚本自动注入。手写错误任务或多次 `--task` 必须失败 |

处理员沙箱数据根简称 `$DP_DATA`：

```text
D:\deploy_acceptance\sandbox_data_processor\data
```

SEG / DET / CAP 沙箱数据根简称 `$SEG_DATA` / `$DET_DATA` / `$CAP_DATA`，同理替换角色名。

---

## 3. 公共准备（一次性）

### 3.1 创建四个沙箱目录并复制部署包

在 PowerShell（无需激活任何 venv）：

```powershell
$Repo = "D:\多任务标注平台V1"
$Acc  = "D:\deploy_acceptance"
New-Item -ItemType Directory -Force -Path `
  "$Acc\sandbox_data_processor", `
  "$Acc\sandbox_annotator_seg", `
  "$Acc\sandbox_annotator_det", `
  "$Acc\sandbox_annotator_cap" | Out-Null

Copy-Item "$Repo\deploy\v1\_lib" "$Acc\sandbox_data_processor\_lib" -Recurse -Force
Copy-Item "$Repo\deploy\v1\data_processor" "$Acc\sandbox_data_processor\data_processor" -Recurse -Force

Copy-Item "$Repo\deploy\v1\_lib" "$Acc\sandbox_annotator_seg\_lib" -Recurse -Force
Copy-Item "$Repo\deploy\v1\annotator_seg" "$Acc\sandbox_annotator_seg\annotator_seg" -Recurse -Force

Copy-Item "$Repo\deploy\v1\_lib" "$Acc\sandbox_annotator_det\_lib" -Recurse -Force
Copy-Item "$Repo\deploy\v1\annotator_det" "$Acc\sandbox_annotator_det\annotator_det" -Recurse -Force

Copy-Item "$Repo\deploy\v1\_lib" "$Acc\sandbox_annotator_cap\_lib" -Recurse -Force
Copy-Item "$Repo\deploy\v1\annotator_cap" "$Acc\sandbox_annotator_cap\annotator_cap" -Recurse -Force
```

每个沙箱**只含本角色目录 + `_lib`**。标注员沙箱不得出现 `data_processor\bin\merge.py`。

### 3.2 每个沙箱独立 venv，安装同一份仓库 `mma`

对四个沙箱分别执行（以处理员为例，其余把路径换成对应沙箱）：

```powershell
cd D:\deploy_acceptance\sandbox_data_processor
python -m venv .venv
.\.venv\Scripts\activate
pip install -e D:\多任务标注平台V1
mma -h
```

**预期：** `mma -h` 列出 `preprocess`、`package`、`ls-import`、`export-split`、`rework-import`、`merge` 等。角色验收时仍只用 `python bin\*.py`。

四套 `.venv` 必须分开；安装源都是 `D:\多任务标注平台V1`（薄包装不含业务代码）。

### 3.3 裁剪 handoff 素材（禁止整份拷贝仓库 `data/`）

不要复制仓库整棵 `data/`（含 `processed` 绝对路径、他任务结果、`final/`）。

| 包 | 内容 | 放入 |
|---|---|---|
| 处理员源材料 | `raw/real_batch/images/` 三张 jpg + `diagnoses.xlsx` | 仅 `$DP_DATA` |
| SEG 接收包 | `task_packages/real_batch/seg/`（`manifest.json` + `images/`） | 仅 `$SEG_DATA`（第 5 章从处理员沙箱拷出） |
| DET 接收包 | `task_packages/real_batch/det/` | 仅 `$DET_DATA` |
| CAP 接收包 | `task_packages/real_batch/cap/` | 仅 `$CAP_DATA` |

处理员沙箱初始整理：

```text
D:\deploy_acceptance\sandbox_data_processor\data\raw\real_batch\
├── images\
│   ├── img_001.jpg
│   ├── img_002.jpg
│   └── img_003.jpg
└── diagnoses.xlsx
```

`images/` 内只能有 `.jpg` / `.jpeg`。Excel 首表必须含 `image_name`、`diagnosis_text`。

加速路径可选材料（第 4.x 标注员加速路径）：仓库已有

```text
D:\多任务标注平台V1\data\ls_export\real_batch\{seg,det,cap}\round_00N\export.json
```

拷入对应标注员沙箱的 `data\ls_export\...`，**不要**连同整份 `results/` / `final/` 一起拷。

---

## 4. 沙箱 A — `data_processor` 独立验收

工作目录：

```powershell
cd D:\deploy_acceptance\sandbox_data_processor\data_processor
.\..\.venv\Scripts\activate
$DP_DATA = "D:\deploy_acceptance\sandbox_data_processor\data"
```

### 4.1 正向：协作职责段（必做）

#### 4.1.1 preprocess

```powershell
python bin\preprocess.py --batch real_batch --images "$DP_DATA\raw\real_batch\images" --excel "$DP_DATA\raw\real_batch\diagnoses.xlsx" --data-root $DP_DATA
```

**预期：** 存在 `$DP_DATA\processed\real_batch\manifest.json`，`items` 长度为 3。

#### 4.1.2 package

```powershell
python bin\package.py --batch real_batch --data-root $DP_DATA
```

**预期：** `$DP_DATA\task_packages\real_batch\{seg,det,cap}\images\` 各 3 张 `{image_id}.jpg`；各 `manifest.json` 的 `package_id` 为 `real_batch__seg` / `__det` / `__cap`。

此时可暂停，把三路 `task_packages` **分别**拷到三个标注员沙箱（见第 5 章）。协作主路径中，处理员日常**不替代**标注员做 LS 标注。

### 4.2 正向：包能力段（必做，本机测试路径）

M11.1 要求处理者包本机可跑全流程，以下三命令必须在本沙箱测通。文档含义是「包有这些入口」，不是「协作时应长期替标注员执行」。

对 `seg`、`det`、`cap` 各执行一次 `ls-import`：

```powershell
python bin\ls_import.py --batch real_batch --task seg --data-root $DP_DATA
python bin\ls_import.py --batch real_batch --task det --data-root $DP_DATA
python bin\ls_import.py --batch real_batch --task cap --data-root $DP_DATA
```

**预期：** `$DP_DATA\ls_import\real_batch\{seg,det,cap}\tasks.json` 各 3 条；仅有 `data` 字段（`image`、`image_id`、`package_id`、`diagnosis_text`）；**无** `predictions`。

`export-split` / `rework-import` 可在本沙箱用测试导出跑通，或放到第 5 章：等标注员沙箱回传 `current/` 后再在处理员沙箱只跑 `merge`。两种都算包能力覆盖，但 **6 个入口文件必须存在且至少被成功调用一次**（本机测试路径若暂无 export，可在第 5 章 merge 前，用标注员回传的 `ls_export` 在处理员沙箱补跑一次 `export-split` / `rework-import`）。

推荐补跑方式（第 5 章回传后，若处理员沙箱尚无 export-split 记录）：将某一任务的 `export.json` 拷到 `$DP_DATA\ls_export\...`，然后：

```powershell
python bin\export_split.py --batch real_batch --task seg --export "$DP_DATA\ls_export\real_batch\seg\round_001\export.json" --data-root $DP_DATA
python bin\rework_import.py --batch real_batch --task seg --data-root $DP_DATA
```

无返工样本时 `rework_tasks.json` 可为 `[]`，命令仍应成功。

#### 4.2.1 merge（协作职责；须在三路 current 就绪后）

merge 前必须：

- 三路 `$DP_DATA\results\real_batch\{seg,det,cap}\current\annotations.json` 就绪
- SEG 另有 `manual_masks/`（若该批 SEG 有人工几何）
- 保留 `processed` 源图**或**任一任务包 `images/`（拷图优先任务包）

```powershell
python bin\merge.py --batch real_batch --data-root $DP_DATA
```

**预期：** 退出码 0；`$DP_DATA\final\real_batch\manifest.json` 存在；`items` 长度为 3。数值不必与仓库参考 `final` 逐字段一致。

### 4.3 负向 / 边界（处理员）

| 检查 | 预期 |
|---|---|
| 本包 `bin\` 含 preprocess / package / ls_import / export_split / rework_import / merge | 六个脚本均存在 |
| 不创建、不分发 `prelabels/` | 沙箱 `data\` 下无该目录 |
| 不调用 `mma convert` | 本包无 convert 入口；文档禁止 |

处理员包**允许**六命令，无需测 merge 被禁。协作时不应长期替标注员标注（文档约束）。

### 4.4 数据处理员验收清单

- [ ] 独立 venv + `pip install -e` 仓库后 `mma -h` 可用
- [ ] `preprocess.py`、`package.py` 正向成功
- [ ] `ls_import.py` 三任务空任务 JSON 无 `predictions`
- [ ] `export_split.py`、`rework_import.py` 至少各成功一次
- [ ] 第 5 章回传后 `merge.py` 得到 3 条 final
- [ ] 无 `prelabels/`、未使用 `convert`

---

## 5. 跨角色 handoff（交付契约，必做）

四沙箱始终独立，只用拷贝模拟网盘。

### 5.1 分发（处理员 → 标注员）

package 成功后：

```powershell
$Acc = "D:\deploy_acceptance"
$Src = "$Acc\sandbox_data_processor\data\task_packages\real_batch"
Copy-Item "$Src\seg" "$Acc\sandbox_annotator_seg\data\task_packages\real_batch\seg" -Recurse -Force
Copy-Item "$Src\det" "$Acc\sandbox_annotator_det\data\task_packages\real_batch\det" -Recurse -Force
Copy-Item "$Src\cap" "$Acc\sandbox_annotator_cap\data\task_packages\real_batch\cap" -Recurse -Force
```

每个标注员沙箱 `data\task_packages\real_batch\` 下**只能有本任务一个子目录**。

### 5.2 回传（标注员 → 处理员）

各标注员完成第 6 章闭环且 `current/` 无返工残留后：

```powershell
$Acc = "D:\deploy_acceptance"
$Dst = "$Acc\sandbox_data_processor\data\results\real_batch"
New-Item -ItemType Directory -Force -Path "$Dst\seg","$Dst\det","$Dst\cap" | Out-Null
Copy-Item "$Acc\sandbox_annotator_seg\data\results\real_batch\seg\current" "$Dst\seg\current" -Recurse -Force
Copy-Item "$Acc\sandbox_annotator_seg\data\results\real_batch\seg\manual_masks" "$Dst\seg\manual_masks" -Recurse -Force
Copy-Item "$Acc\sandbox_annotator_det\data\results\real_batch\det\current" "$Dst\det\current" -Recurse -Force
Copy-Item "$Acc\sandbox_annotator_cap\data\results\real_batch\cap\current" "$Dst\cap\current" -Recurse -Force
```

处理员沙箱还须保留第 4 章已有的 `processed/` 或 `task_packages/` 图像，然后执行 `python bin\merge.py ...`。

未完成/质检模式：可只拷 `rework/` 验证目录可单独带走（不必 merge）。

---

## 6. 标注员沙箱通式（SEG / DET / CAP）

三包同构。下文用 `<ROLE>` = `seg` | `det` | `cap`，`<SANDBOX>` = `sandbox_annotator_<ROLE>`。

### 6.1 环境与工作目录

```powershell
cd D:\deploy_acceptance\<SANDBOX>\annotator_<ROLE>
.\..\.venv\Scripts\activate
$DATA = "D:\deploy_acceptance\<SANDBOX>\data"
```

**确认 `bin\` 不存在** `preprocess.py`、`package.py`、`merge.py`。

**确认 `data\task_packages\real_batch\` 仅有本任务目录。**

### 6.2 Label Studio（换沙箱必改环境变量并重启）

一台机器可共用一个 Label Studio 进程，但：

- SEG / DET / CAP **各建独立项目**
- 切换沙箱时必须把 `LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT` 改成**当前沙箱 `data` 绝对路径**并**重启** Label Studio
- 项目 Local Files / Source Storage 不得指向仓库原 `data\` 或其它沙箱

启动示例（SEG 沙箱）：

```powershell
cd D:\labelstudio-env
.\venv\Scripts\activate
$env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED = "true"
$env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT = "D:\deploy_acceptance\sandbox_annotator_seg\data"
label-studio
```

Labeling Interface 粘贴**本包** XML：

| 角色 | 文件 |
|---|---|
| SEG | `annotator_seg\configs\seg.xml` |
| DET | `annotator_det\configs\det.xml` |
| CAP | `annotator_cap\configs\cap.xml` |

`human_confirmed` 与 `needs_rework` 均为必选；不选无法 Submit。

浏览器自检原图（端口按实际）：

```text
http://localhost:8080/data/local-files/?d=task_packages/real_batch/seg/images/real_batch__000001.jpg
```

将 `seg` 换成当前任务。404 时先核对 DOCUMENT_ROOT 是否为**本沙箱 `data`**，且 `d=` 以 `task_packages/` 开头。

### 6.3 正向：三命令全测

#### 6.3.1 ls-import（不要手写 `--task`）

```powershell
python bin\ls_import.py --batch real_batch --data-root $DATA
```

**预期：** `$DATA\ls_import\real_batch\<ROLE>\tasks.json` 含 3 条空任务；无 `predictions`。脚本自动注入 `--task <ROLE>`。

#### 6.3.2 标注与导出（两条路径）

**主路径（交付验收推荐）：** 导入 `tasks.json` → 3 张全部人工处理：

| 控件 | 要求 |
|---|---|
| 几何 / 文本 | V1 首轮从空白绘制或填写 |
| `human_confirmed` | 全部 `yes` |
| `needs_rework` | **至少 1 张 `yes`**（为返工闭环留样本）；其余 `no` |

Export JSON 保存为：

```text
$DATA\ls_export\real_batch\<ROLE>\round_001\export.json
```

**加速路径（开发者自测可选）：** 将仓库已有 `export.json` 拷到上述路径，跳过手工绘制，仍须跑通后续 CLI。加速路径**不能**替代主路径对「本包 XML + Local Files + 必选控件」的至少一次真实 LS 验收（三角色合计至少各做一次主路径更稳；若时间紧，可一角色主路径、另两角色加速，但 XML/Local Files 仍须在真实 LS 打开并确认能出图、必选生效）。

#### 6.3.3 export-split

```powershell
python bin\export_split.py --batch real_batch --export "$DATA\ls_export\real_batch\<ROLE>\round_001\export.json" --data-root $DATA
```

**预期：**

- `$DATA\results\real_batch\<ROLE>\current\annotations.json` 已更新
- `normal\` 与 `rework\` 已写出（本轮有返工则 `rework` 非空）
- **SEG：** 若导出含 polygon/brush，出现 `$DATA\results\real_batch\seg\manual_masks\<image_id>_manual.png`

对同一 export **不要**再跑 `apply-current`。

**双模式回传检查：**

| 模式 | 可单独带走的目录 |
|---|---|
| 未完成 / 质检 | `results\<batch>\<ROLE>\rework\` |
| 完成态 | `results\<batch>\<ROLE>\current\`（SEG + `manual_masks\`） |

换人交接三件套：`current/` + `rework/` + `task_packages/<batch>/<ROLE>/`。

#### 6.3.4 至少 1 轮返工闭环

```powershell
python bin\rework_import.py --batch real_batch --data-root $DATA
```

**预期：** 写出 `$DATA\ls_import\real_batch\<ROLE>\rework_tasks.json`，**不覆盖**首轮 `tasks.json`。无 `previous_annotations` 时命令应失败（须先 export-split）。

再标注（主路径）：修好的样本 `needs_rework=no`；本手册**不强制第二轮**，本轮结束后将该任务全部改为 `needs_rework=no` 以便后续 merge。

导出 `round_002/export.json` 后再执行一条 `export-split`。

自检 `current/annotations.json`：3 条、全部 `human_confirmed: true`、全部 `needs_rework: false`。

### 6.4 负向：越界必测

在对应标注员沙箱执行：

```powershell
# 1) 禁止脚本不存在
Test-Path bin\preprocess.py   # False
Test-Path bin\package.py      # False
Test-Path bin\merge.py        # False

# 2) 错误 --task（以 SEG 沙箱为例；DET/CAP 换成其它任务）
python bin\ls_import.py --batch real_batch --task det --data-root $DATA
# 预期：退出码 2，stderr 含 deploy: 且提示 --task must be 'seg'

# 3) 多个 --task
python bin\ls_import.py --batch real_batch --task seg --task det --data-root $DATA
# 预期：退出码 2，multiple --task
```

| 尝试 | 预期 |
|---|---|
| `bin` 下 preprocess / package / merge | 文件不存在 |
| `--task` 与本角色不符 | 退出码 **2** |
| 多个 `--task` | 退出码 **2** |
| `data\task_packages` 或 `results` 出现他任务目录 | 不合格 |

标注员**不应**在本沙箱调用 `mma preprocess` / `mma merge`（即使系统 PATH 上的 `mma` 能执行，也属职责越界，验收记不合格）。

---

## 7. 沙箱 B — `annotator_seg`

套用第 6 章，`<ROLE>=seg`。

额外验收：

- [ ] `configs\seg.xml` 与仓库 `src\mma\labelstudio\configs\seg.xml` 内容一致（PolygonLabels + 两项必选 Choices）
- [ ] 完成态回传含 `manual_masks\`
- [ ] `--task det` / `--task cap` 退出码 2

---

## 8. 沙箱 C — `annotator_det`

套用第 6 章，`<ROLE>=det`。

额外验收：

- [ ] `configs\det.xml`（RectangleLabels）
- [ ] **无** `manual_masks\` 要求
- [ ] `--task seg` 退出码 2

---

## 9. 沙箱 D — `annotator_cap`

套用第 6 章，`<ROLE>=cap`。

额外验收：

- [ ] `configs\cap.xml`（TextArea `cap_text`）
- [ ] **无** `manual_masks\` 要求
- [ ] `--task seg` 退出码 2

---

## 10. 与自动化测试的对应

| 手册检查 | 自动化 |
|---|---|
| 四角色目录、`bin` 入口、标注员无 preprocess/package/merge | `tests/test_m11_deploy.py` |
| XML 与 src 一致 | `test_annotator_configs_match_src_normalized`、`test_labelstudio_deploy_sync.py` |
| allowlist / force_task / 多 `--task` | `test_role_cli_*` |
| `needs_rework` 必选 | `test_*_choice_fields_both_required_for_submit` |

pytest **不替代**本手册的真实数据、LS、四沙箱隔离与网盘拷贝。

---

## 11. 常见问题

| 现象 | 处理 |
|---|---|
| LS 图 404 | `DOCUMENT_ROOT` 必须是**当前沙箱 `data` 绝对路径**；换沙箱后重启 LS；勿指向仓库 `data` 或旧项目 |
| `from _lib.role_cli` 失败 | 检查沙箱根是否同时有 `_lib\` 与 `annotator_*\`（或 `data_processor\`），不要摊平角色目录 |
| `mma` 导入到另一份「多任务标注平台」 | 确认已激活**本沙箱** `.venv`，且该 venv 执行过 `pip install -e D:\多任务标注平台V1` |
| merge 报 empty task payload / SEG | 处理员沙箱缺少 SEG `manual_masks` 或 mask 无前景；按契约从 SEG 沙箱回传 |
| LS 无法 Submit | `human_confirmed` 与 `needs_rework` 都必须选择；项目须粘贴**本包最新 XML** |
| `rework-import` 失败 | 须先 `export-split` 写出 `previous_annotations`；且本机仍有 `task_packages/.../images/` |
| 同一 export 连跑 apply-current | 不要；`export-split` 已包含 current 同步 |

---

## 附录 A · 四角色命令速查

| 角色 | 工作目录 | 允许入口 |
|---|---|---|
| data_processor | `sandbox_data_processor\data_processor` | `preprocess.py` `package.py` `ls_import.py` `export_split.py` `rework_import.py` `merge.py` |
| annotator_seg | `sandbox_annotator_seg\annotator_seg` | `ls_import.py` `export_split.py` `rework_import.py`（强制 seg） |
| annotator_det | 同构 | 强制 det |
| annotator_cap | 同构 | 强制 cap |

标注员示例（SEG）：

```powershell
python bin\ls_import.py --batch real_batch --data-root $DATA
python bin\export_split.py --batch real_batch --export <export.json> --data-root $DATA
python bin\rework_import.py --batch real_batch --data-root $DATA
```

---

## 附录 B · 最小目录树

**处理员沙箱测试前：** `data\raw\real_batch\` 仅源材料。

**处理员 package 后：** 另有 `processed\`、`task_packages\real_batch\{seg,det,cap}\`。

**标注员沙箱测试前：** 仅 `data\task_packages\real_batch\<ROLE>\`。

**标注员闭环后：** 另有 `ls_import\`、`ls_export\`、`results\<batch>\<ROLE>\{current,normal,rework}\`；SEG 另有 `manual_masks\`。

**处理员 merge 后：** `data\final\real_batch\manifest.json` + `images\` + `masks\`。

---

## 附录 C · 从全链路产物裁剪 handoff

若已按 [real_batch_local_test_runbook.md](real_batch_local_test_runbook.md) 跑通仓库级链路，可从仓库 `data\` **按需拷贝**，仍禁止整棵复制：

| 目标沙箱 | 可拷 |
|---|---|
| 处理员 | `raw\real_batch\images\` + `diagnoses.xlsx`（不要 processed/final） |
| 标注员加速 | 仅该任务 `ls_export\real_batch\<ROLE>\round_00N\export.json` |
| 处理员 merge 联调 | 优先走第 5 章从标注员沙箱回传 `current/`；不要直接拷仓库 `final\` 当验收通过 |

裁剪原则：标注员看不见 `processed/`、`final/`、他任务 `results/`。
