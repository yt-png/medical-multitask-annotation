# 医学图像多任务标注平台 V1（mma）本地真实数据全链路测试操作手册

| 项 | 值 |
|---|---|
| 文档性质 | 企业内部研发验收 SOP（本机全流程测试路径） |
| 适用版本 | V1 Frozen（包版本 `0.1.0`） |
| 文档日期 | 2026-08-18 |
| 权威实现 | `src/mma/cli.py` 及对应业务模块 |
| 测试角色 | 数据处理者本机单人验收（可模拟标注员，不替代协作分工） |

本文档依据当前仓库 **代码实现** 编写。若与历史手册不一致，以代码为准，差异见 **附录 A**。

**V1 硬约束（全程禁止违反）：**

- 不使用、不准备、不读取 `prelabels/`
- 不调用 `mma convert`（该命令为 Legacy stub，退出码 2）
- 首轮 `ls-import` 必须生成空任务（无 `predictions`）
- 金标准只来自人工 `annotation`；禁止把 LS `predictions` 当模型结果回填
- 空标注 / 缺有效载荷必须进入 `rework/`
- `merge` 只读三路 `results/<batch>/{seg,det,cap}/current/`

**不要使用的历史路径：** `docs/real_batch_local_test_runbook.md` 中「阶段 2：放置 prelabels」及 raw 下 `masks/` 步骤属于 Legacy，V1 验收跳过。

---

# 1. 测试目标

## 1.1 为什么测试

V1 开发任务（M0–M12）已完成，状态为 **Medical Image Multi-task Annotation Dataflow V1 Frozen**。本 SOP 用于系统验收：在本地用一批真实（或等价真实结构）医学图像，从 raw 输入跑到 `final/` 金标准产出，证明主流程可被新人复现。

自动化单测（`tests/test_m12_*.py` 等）验证规则正确性，**不能替代** Label Studio 人工标注与导出落盘。本手册补齐这一段。

## 1.2 验证哪些能力

| 能力 | 对应命令 / 操作 |
|---|---|
| 图文绑定与稳定 `image_id` | `mma preprocess` |
| SEG / DET / CAP 三类全量任务包独立生成 | `mma package` |
| 首轮空任务导入（无 prelabel / 无 prediction） | `mma ls-import` |
| Label Studio 本机加载原图并完成三类人工标注 | LS 项目 + XML |
| 导出解析、`current/` 覆盖、`normal/` / `rework/` 分类 | `mma export-split` |
| 空标注进 rework；勾选返工进 rework | 首轮标注矩阵 |
| 返工预填仅人工历史（`previous_annotations`） | `mma rework-import` |
| 第一次返工失败、第二次返工成功 | round_002 / round_003 |
| 三路 current 就绪后合并自包含 final | `mma merge` |

## 1.3 测试覆盖范围

- 数据处理者本机全流程：`preprocess → package → ls-import → LS 标注 → export-split → rework-import → 再标注 → export-split → merge`
- 样本规模：`batch_id = real_batch`，**N = 3**
- 三任务独立：SEG / DET / CAP 各自项目、各自 export、各自 results 子树
- 分类规则（代码权威，`should_rework_result`）：

```text
should_rework_result =
    (not human_confirmed)
    or needs_rework
    or (not effective_payload)
```

有效载荷：DET ≥ 1 框；CAP strip 后非空文案；SEG 非空 `mask_ref` 且 `has_foreground=True`。

## 1.4 不包含哪些内容

- 真实 SEG / DET / CAP 算法、大模型、预标注 adapter
- 网盘自动上传下载、业务服务端、Web / DB
- 四角色网盘协作主路径（分发 / 回传）；本手册是处理者本机测试路径
- `mma convert`、`examples/prelabels/`、Legacy adapter（`pytest -m legacy`）
- 标注质量医学评审（框/多边形/文案与参考机数值不必一致）
- 修改 `src/mma` 业务代码

---

# 2. 测试环境准备

## 2.0 约定

| 项 | 值 |
|---|---|
| 项目根 | `D:\多任务标注平台V1`（换机请替换为实际克隆路径，下文记为 `<REPO>`） |
| 数据根 `--data-root` | `data`（即 `<REPO>\data`） |
| `batch_id` | `real_batch` |
| Shell | Windows 用 **PowerShell**；多条命令用 `;` 分隔，不要用 `&&` |
| Python | **3.12+**（`pyproject.toml`：`requires-python = ">=3.12"`） |
| 包版本 | `mma==0.1.0`（`src/mma/__init__.py`） |

下文命令块按仓库文档习惯写 bash 风格；在 PowerShell 中把 `source .venv/bin/activate` 换成 `.\.venv\Scripts\activate`。

---

## 2.1 操作系统要求

**执行：** 确认 64 位 Windows 10/11，或 Linux / macOS。本手册以 Windows 为例。

```bash
python --version
```

**预期结果：** 输出 `Python 3.12.x` 或更高（3.13 可用，仓库测试曾在 3.13 跑通）。低于 3.12 停止，先升级 Python。

---

## 2.2 进入仓库并创建虚拟环境

**执行：**

```bash
cd D:\多任务标注平台V1
python -m venv .venv
```

Windows PowerShell：

```powershell
cd D:\多任务标注平台V1
python -m venv .venv
.\.venv\Scripts\activate
```

Linux / macOS：

```bash
cd /path/to/多任务标注平台V1
python -m venv .venv
source .venv/bin/activate
```

**预期结果：** 提示符前出现 `(.venv)`。`where python`（Windows）或 `which python` 指向 `.venv` 内解释器。

---

## 2.3 安装本项目（可编辑安装）

**执行：**

```bash
pip install -U pip
pip install -e .
```

依赖由 `pyproject.toml` 锁定为：`openpyxl`、`Pillow`、`numpy`、`opencv-python-headless`。无 `configs/default.yaml`，约定内嵌于代码与 CLI。

**预期结果：** 安装成功，无报错。随后：

```bash
mma -h
```

**预期结果：** 退出码 0，帮助列出全部子命令：

```text
preprocess
package
convert
ls-import
export-split
rework-import
apply-current
merge
```

`ls-import` 帮助须写明从 `task_packages` 生成空任务、无 predictions。`convert` 帮助须标明 LEGACY / stub。

等价入口：`python -m mma -h`。

---

## 2.4（可选）自动化门禁冒烟

本 SOP 是人工全链路验收。建议先确认单测绿，避免环境损坏。

```bash
pip install pytest
pytest
```

**预期结果：** 默认 `addopts = -m "not legacy"`，legacy 用例被 deselect。冻结报告记录为全量通过量级（当时 408 passed）。任一 V1 主测失败则先修环境/代码，再做本手册。

---

## 2.5 Label Studio 安装（独立虚拟环境，强制）

**禁止** 与 mma 共用同一个 venv（依赖冲突风险）。另建目录，例如 `D:\labelstudio-env`。

**执行：**

```powershell
cd D:\labelstudio-env
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install label-studio
label-studio --version
```

**预期结果：** 能打印 Label Studio 版本号。界面文案随版本可能略有差异，操作以「Local Files + JSON 导入/导出」为准。

---

## 2.6 Label Studio 环境变量与启动

每次启动前，在 **Label Studio 的 PowerShell 会话** 设置（路径必须是 `data` 的绝对路径，且与 `--data-root` 解析结果一致）：

```powershell
cd D:\labelstudio-env
.\venv\Scripts\activate
$env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED = "true"
$env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT = "D:\多任务标注平台V1\data"
label-studio
```

Linux / macOS：

```bash
export LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
export LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT="/path/to/多任务标注平台V1/data"
label-studio
```

**预期结果：** 浏览器可打开（一般为 `http://localhost:8080`），可注册/登录本地账号。

**判断成功：** 服务持续运行；mma 虚拟环境仍在另一个终端保持激活。

---

## 2.7 环境变量与路径对照（验收前钉死）

| 变量 / 参数 | 必须等于 |
|---|---|
| `mma --data-root` | `data`（相对项目根）或 `D:\多任务标注平台V1\data` |
| `mma ls-import --local-root` | 默认等于 `--data-root`，本 SOP **不要改** |
| `LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT` | `data` 的绝对路径 |
| LS Cloud Storage「Absolute local path」 | `D:\多任务标注平台V1\data\task_packages`（必须是 DOCUMENT_ROOT **子目录**） |

`tasks.json` 中图像 URL 形如：

```text
/data/local-files/?d=task_packages/real_batch/seg/images/real_batch__000001.jpg
```

对应磁盘：

```text
D:\多任务标注平台V1\data\task_packages\real_batch\seg\images\real_batch__000001.jpg
```

---

## 2.8 环境准备 Checklist

| 检查项 | 预期 | 实际 | 是否通过 |
|---|---|---|---|
| Python 版本 | ≥ 3.12 |  |  |
| mma venv 已激活 | `(.venv)` |  |  |
| `pip install -e .` | 成功 |  |  |
| `mma -h` 含子命令 | 含 preprocess / package / ls-import / export-split / rework-import / merge |  |  |
| `mma convert -h` | 标明 LEGACY，非 V1 主流程 |  |  |
| Label Studio 独立 venv | 与 mma 分离 |  |  |
| `LABEL_STUDIO_LOCAL_FILES_*` | serving=true，DOCUMENT_ROOT=data 绝对路径 |  |  |
| 浏览器可打开 LS | localhost:8080 可登录 |  |  |

---

# 3. 测试数据准备

## 3.1 批次设计

| 项 | 值 | 为什么这样设计 |
|---|---|---|
| `batch_id` | `real_batch` | 与历史联调批次名一致；仅含字母数字 `_`，满足 `validate_batch_id` |
| 样本数 N | **3** | 刚好覆盖：正常 / 空标注 / 返工闭环，又足够小可手工标注 |
| 图像格式 | 仅 `.jpg` | `list_image_files` 只允许 `.jpg` / `.jpeg`；目录内出现其它文件整批失败 |
| Excel | `diagnoses.xlsx` | 只接受 `.xlsx`；`.xls` 须先人工转换 |
| 列名 | 首表固定 `image_name` / `diagnosis_text` | `read_diagnosis_excel` 按列名定位，缺列即失败 |
| 配对键 | **完整文件名**（含扩展名） | 去空白 + 大小写不敏感；图与表必须一一对应 |

**不要**在 `images/` 放入 mask、xlsx、子目录。preprocess **不读取** `masks/`。

## 3.2 目录

```text
data/raw/real_batch/
├── images/
│   ├── img_001.jpg
│   ├── img_002.jpg
│   └── img_003.jpg
└── diagnoses.xlsx
```

V1 **不需要**：`data/raw/real_batch/masks/`、`data/prelabels/`。

## 3.3 图像来源

**优先：真实医学 JPG（推荐验收用法）。** 三张图须可肉眼区分病灶/结构，便于 SEG 画多边形、DET 画框、CAP 写描述。文件名必须改为上表三名。

**若暂时没有真实图：** 可从仓库假数据拷贝后改名（结构合法，但医学内容非真实）：

```powershell
New-Item -ItemType Directory -Force -Path data\raw\real_batch\images | Out-Null
Copy-Item examples\raw\demo_batch\images\img_001.jpg data\raw\real_batch\images\img_001.jpg
Copy-Item examples\raw\demo_batch\images\img_002.jpg data\raw\real_batch\images\img_002.jpg
Copy-Item examples\raw\demo_batch\images\img_003.jpg data\raw\real_batch\images\img_003.jpg
```

## 3.4 Excel 格式与生成

首表示例：

| image_name | diagnosis_text |
|---|---|
| img_001.jpg | 出血性内痔 |
| img_002.jpg | 出血性内痔 |
| img_003.jpg | 出血性内痔 |

规则：

- `image_name` 必须与文件名完全对应（可大小写不同，preprocess 会 casefold）
- `diagnosis_text` 不能为空
- 图有表无、表有图无 → 整批 `ValueError`

在已激活的 **mma venv** 生成 Excel：

```powershell
python -c "from pathlib import Path; from openpyxl import Workbook; p=Path('data/raw/real_batch'); p.mkdir(parents=True, exist_ok=True); wb=Workbook(); ws=wb.active; ws.append(['image_name','diagnosis_text']);
[ws.append([n,'出血性内痔']) for n in ['img_001.jpg','img_002.jpg','img_003.jpg']]; wb.save(p/'diagnoses.xlsx'); print(p/'diagnoses.xlsx')"
```

**预期结果：** 存在 `data/raw/real_batch/diagnoses.xlsx`。

## 3.5 `image_id` 预计算（preprocess 后必须核对）

`assign_image_ids` 按 **规范化文件名排序** 后从 1 开始编号：`{batch_id}__{sequence:06d}`。

本批文件名排序后为 `img_001.jpg` → `img_002.jpg` → `img_003.jpg`，因此：

| source_image_name | 预期 image_id |
|---|---|
| img_001.jpg | `real_batch__000001` |
| img_002.jpg | `real_batch__000002` |
| img_003.jpg | `real_batch__000003` |

`package_id`：`real_batch__seg` / `real_batch__det` / `real_batch__cap`。

## 3.6 三样本业务角色（贯穿全手册）

| 样本 | image_id | 角色 | 用途 |
|---|---|---|---|
| A | `real_batch__000001` | **正常样本** | 首轮即有效载荷 + 已确认 + 不返工 → `normal/` |
| B | `real_batch__000002` | **空标注样本** | 首轮只勾选、不画/不写 → `rework/`；第 1 轮返工修好 |
| C | `real_batch__000003` | **返工闭环样本** | 首轮有效标注但 `needs_rework=yes`；第 1 轮仍失败；第 2 轮成功 |

三任务 SEG / DET / CAP **使用同一矩阵**，才能在 merge 时三路 `image_id` 集合一致。

## 3.7 数据准备 Checklist

| 检查项 | 预期 | 实际 | 是否通过 |
|---|---|---|---|
| 目录 `data/raw/real_batch/images/` | 仅 3 个 jpg |  |  |
| 无 png / xlsx / 子目录混入 images | 通过 |  |  |
| `diagnoses.xlsx` 列名 | `image_name` / `diagnosis_text` |  |  |
| 三行文件名 | 与三张图一一对应 |  |  |
| 诊断文本非空 | 通过 |  |  |
| 未创建 `prelabels/` | 通过 |  |  |
| 未放入 raw `masks/`（或不作为输入） | 通过 |  |  |

---

# 4. 全链路测试执行步骤

全程在项目根、**mma venv 已激活**。Label Studio 用另一个终端。

成功命令的 stdout（代码行为）：

| 命令 | stdout |
|---|---|
| `preprocess` | 一行：`processed/real_batch` 绝对路径 |
| `package` | 一行：`task_packages/real_batch` 绝对路径 |
| `ls-import` | 一行：`.../tasks.json` 绝对路径 |
| `export-split` | 两行：`normal/annotations.json` 然后 `rework/annotations.json` |
| `rework-import` | 一行：`.../rework_tasks.json` 绝对路径 |
| `merge` | 一行：`final/real_batch/manifest.json` 绝对路径 |

失败时 stderr 前缀为 `mma <command>: ...`，退出码 **2**。

**禁止：** 对同一份 export 先 `export-split` 再 `apply-current`（或反过来）。日常只用 `export-split`。

---

## Step 1 preprocess 测试

### 说明

读取 `--images` 与 `--excel`，一对一绑定，分配 `image_id`，写入 `processed/<batch>/manifest.json`。**不复制图像**；`image_path` 为预处理时的绝对路径。

### 执行命令

```bash
mma preprocess --batch real_batch --images data/raw/real_batch/images --excel data/raw/real_batch/diagnoses.xlsx --data-root data
```

### 看什么输出

终端打印类似：

```text
D:\多任务标注平台V1\data\processed\real_batch
```

退出码 0。

### 检查输出目录

应存在且仅需清单（无强制拷图）：

```text
data/processed/real_batch/manifest.json
```

### 检查 manifest.json

```powershell
python -c "import json; from pathlib import Path; m=json.loads(Path('data/processed/real_batch/manifest.json').read_text(encoding='utf-8')); print('batch', m['batch_id']); print('n', len(m['items']));
[print(i['source_image_name'], '->', i['image_id'], '|', i['diagnosis_text'][:20], '|', i['image_path']) for i in m['items']]"
```

### 验证

- `batch_id == "real_batch"`
- `items` 长度 **3**
- `image_id` 为 `real_batch__000001` / `000002` / `000003`，并与 `source_image_name` 按下表对应
- 每条 `diagnosis_text` 非空（本设计为「出血性内痔」）
- `image_path` 指向真实存在的 jpg（绝对路径）；换盘后不可迁移，本机须保持原图可读，否则后续 package/merge 失败

### 负例（不必每次做，排障时用）

- images 混入 `.png` → `unsupported file in images directory`
- Excel 缺列 → `excel must contain columns 'image_name' and 'diagnosis_text'`
- 图文数量不一致 → `images without excel rows` / `excel rows without images`

### Step 1 Checklist

| 检查项 | 预期 | 实际 | 是否通过 |
|---|---|---|---|
| 命令退出码 | 0 |  |  |
| stdout 为 processed 目录 | `...\data\processed\real_batch` |  |  |
| manifest 生成 | 成功 |  |  |
| image 数量 | 3 |  |  |
| image_id 规则 | `{batch}__00000N` |  |  |
| 图文绑定 | 3 对全部匹配 |  |  |
| diagnosis 读取 | 非空 |  |  |
| 未写 prelabels | 通过 |  |  |

---

## Step 2 package 测试

### 说明

从 processed 清单复制全量图像到三类任务包，文件名改为 `{image_id}.jpg`，并写各包 `manifest.json`。三任务样本数均等于 N。

### 执行命令

```bash
mma package --batch real_batch --data-root data
```

### 看什么输出

```text
D:\多任务标注平台V1\data\task_packages\real_batch
```

### 检查

```text
data/task_packages/real_batch/
├── seg/
│   ├── manifest.json
│   └── images/
│       ├── real_batch__000001.jpg
│       ├── real_batch__000002.jpg
│       └── real_batch__000003.jpg
├── det/   （结构相同）
└── cap/   （结构相同）
```

抽查一份 manifest：

```powershell
python -c "import json; from pathlib import Path
for t in ('seg','det','cap'):
 p=Path('data/task_packages/real_batch')/t/'manifest.json'; m=json.loads(p.read_text(encoding='utf-8'))
 print(t, m['package_id'], m['task_type'], m['batch_id'], 'samples', len(m['samples']))
 print('  paths', [s['image_path'] for s in m['samples']])"
```

### 验证

- 三类任务**独立目录**，互不混写
- `package_id`：`real_batch__seg` / `__det` / `__cap`
- `task_type`：`SEG` / `DET` / `CAP`（契约大写）
- 每包 `samples` 长度 3；`image_path` 形如 `images/real_batch__000001.jpg`
- 每包 `images/` 恰好 3 张图，可打开
- 重跑 package 会按 processed 对齐并删除清单外杂文件；本 SOP 不要往 `images/` 塞无关文件

### Step 2 Checklist

| 检查项 | 预期 | 实际 | 是否通过 |
|---|---|---|---|
| 命令退出码 | 0 |  |  |
| 三类目录均存在 | seg / det / cap |  |  |
| 每包图片数量 | 3 |  |  |
| 文件名 | `{image_id}.jpg` |  |  |
| package_id | `real_batch__{task}` |  |  |
| 图片完整可打开 | 通过 |  |  |
| 无 prelabels 步骤 | 通过 |  |  |

---

## Step 3 ls-import 测试

### 说明

**仅读取** `task_packages/<batch>/<task>/`。写出 `ls_import/.../tasks.json`。每条任务只有 `data` 四字段，**禁止**出现 `predictions`、`mask_ref`、prelabel 字段。图像不复制，只写 Local Files URL。

分别测 SEG / DET / CAP。

### 执行命令

```bash
mma ls-import --batch real_batch --task seg --data-root data
mma ls-import --batch real_batch --task det --data-root data
mma ls-import --batch real_batch --task cap --data-root data
```

### 看什么输出

三次各打印一行，例如：

```text
D:\多任务标注平台V1\data\ls_import\real_batch\seg\tasks.json
```

det / cap 同理。

### 验证空任务（必须用脚本，不要只看文件存在）

```powershell
python -c "import json; from pathlib import Path
ALLOWED={'image','image_id','package_id','diagnosis_text'}
for t in ('seg','det','cap'):
 tasks=json.loads(Path(f'data/ls_import/real_batch/{t}/tasks.json').read_text(encoding='utf-8'))
 assert isinstance(tasks, list) and len(tasks)==3
 for task in tasks:
  assert 'predictions' not in task, t
  assert set(task.keys())=={'data'}, t
  assert set(task['data'].keys())==ALLOWED, (t, task['data'].keys())
  assert 'mask_ref' not in task['data']
  img=task['data']['image']
  assert img.startswith('/data/local-files/?d=task_packages/real_batch/'+t+'/images/')
  assert '\\' not in img
 print(t, 'OK', [x['data']['image_id'] for x in tasks])"
```

**预期结果：** 打印 `seg OK ...` / `det OK ...` / `cap OK ...`，无 AssertionError。

抽查 URL 对应文件存在：

```powershell
python -c "from pathlib import Path; p=Path('data/task_packages/real_batch/seg/images/real_batch__000001.jpg'); print(p.exists(), p.resolve())"
```

### 符合 Label Studio 导入格式

- 顶层是 **JSON 数组**
- 每项含 `data.image`（Local Files URL）、`data.image_id`、`data.package_id`、`data.diagnosis_text`
- 无 `id` 也可导入（代码首轮不写 `id`；返工包才会写 `id`）

### Step 3 Checklist

| 检查项 | 预期 | 实际 | 是否通过 |
|---|---|---|---|
| 三个 `tasks.json` 生成 | 成功 |  |  |
| 每文件任务数 | 3 |  |  |
| 顶层仅 `data` 键 | 通过 |  |  |
| 无 `predictions` 字段 | 通过 |  |  |
| 无 `mask_ref` / prelabel | 通过 |  |  |
| `data.image` 为正斜杠 Local Files URL | 通过 |  |  |
| URL 相对 data 根且文件在磁盘存在 | 通过 |  |  |
| 未读取 `prelabels/` | 目录不存在或未被访问 |  |  |

---

## Step 4 Label Studio 人工标注模拟

**不要假设人工已经完成。** 本步必须在 LS 里真实点选、绘制、导出。

### 4.1 创建三个项目并加载 XML

为 SEG / DET / CAP **各建一个项目**（名称建议：`v1-real_batch-seg` 等）。

在 Labeling Interface 中分别粘贴（**勿改控件 `name`**）：

| 任务 | XML 权威路径 |
|---|---|
| SEG | `src/mma/labelstudio/configs/seg.xml` |
| DET | `src/mma/labelstudio/configs/det.xml` |
| CAP | `src/mma/labelstudio/configs/cap.xml` |

同步副本（内容应一致）：`deploy/v1/annotator_{seg,det,cap}/configs/`。

控件对照：

| 任务 | 主图 | 可编辑控件 | 勾选 |
|---|---|---|---|
| SEG | `Image name="image"` | `PolygonLabels name="seg_mask"`，标签 `lesion` | `human_confirmed`、`needs_rework`（yes/no） |
| DET | 同上 | `RectangleLabels name="det_bbox"`，标签 `object` | 同上 |
| CAP | 同上 | `TextArea name="cap_text"` | 同上 |

CAP XML 左侧标题为「人工描述」。V1 首轮 TextArea **为空**，必须人工填写，不要当成模型预填。

可用 Python 打印已安装包内路径：

```python
from mma.labelstudio import seg_config_path, det_config_path, cap_config_path
print(seg_config_path())
print(det_config_path())
print(cap_config_path())
```

### 4.2 每个项目配置 Local Files Source Storage

Settings → Cloud Storage → Add Source Storage → **Local Files**：

| 字段 | 值 |
|---|---|
| Absolute local path | `D:\多任务标注平台V1\data\task_packages` |

**不得**填与 `DOCUMENT_ROOT` 完全相同的 `...\data`（Label Studio 通常拒绝根路径等于 DOCUMENT_ROOT）。保存后 Test / Sync（若界面有）。

三个项目都要配。

### 4.3 导入首轮空任务

| 项目 | 导入文件 |
|---|---|
| SEG | `data/ls_import/real_batch/seg/tasks.json` |
| DET | `data/ls_import/real_batch/det/tasks.json` |
| CAP | `data/ls_import/real_batch/cap/tasks.json` |

打开任意样本：

- **必须能看到原图**
- 多边形/框/文本控件为**空白**
- 侧栏只读：诊断文本、`image_id`、`package_id`
- 若已有几何或模型文案：说明导错了返工包或 Legacy convert 产物，停止并检查文件

### 4.4 首轮标注矩阵（round_001）——必须按表执行

对 **每一个任务**（SEG、DET、CAP）的三张图，按下表操作后提交（Submit）。`human_confirmed` 在 XML 中为 required。

| image_id | 人工操作 | 勾选 | 制造类型 |
|---|---|---|---|
| `real_batch__000001` | **画出/填写有效结果** | confirmed=`yes`，rework=`no` | 正常样本 |
| `real_batch__000002` | **不画框/不画多边形/不写 cap_text**（或 CAP 只留空白） | confirmed=`yes`，rework=`no` | 空标注样本 |
| `real_batch__000003` | **画出/填写有效结果** | confirmed=`yes`，rework=`yes` | 需返工样本 |

#### SEG 如何模拟标注

1. 选择工具 `lesion` 多边形。
2. **000001 / 000003**：在病灶或任意可见结构上画 **至少 3 个点** 的闭合多边形（可很粗，验收不看医学精度）。
3. **000002**：不要添加任何多边形。只选 confirmed=yes、rework=no 后提交。
4. 不要依赖 `$mask_ref`（首轮任务无此字段）。

#### DET 如何模拟标注

1. 选择 `object` 矩形。
2. **000001 / 000003**：画 **至少 1 个框**，框要有可见宽高。
3. **000002**：不画任何框，只勾选后提交。

#### CAP 如何模拟标注

1. 在 `cap_text` 填写人工描述，**不要**把只读「原始诊断文本」当作提交结果。
2. **000001 / 000003**：写入非空中文，例如「可见痔核，建议对照诊断文本复核。」
3. **000002**：TextArea 保持空；若界面强制有内容，提交前清空。confirmed=yes，rework=no。

### 4.5 首轮导出（全量轮）

每个项目：Export → 选择 **JSON**（任务数组，不是 CSV）。保存为：

```text
data/ls_export/real_batch/seg/round_001/export.json
data/ls_export/real_batch/det/round_001/export.json
data/ls_export/real_batch/cap/round_001/export.json
```

要求：

- 每个文件是 JSON **数组**
- 各含 **3** 条任务（全量）
- 每条有 `data.image_id` 和 `annotations`（至少一条未取消的 annotation）
- **不要**把 SEG 的 export 喂给 DET/CAP 命令
- 父目录必须叫 `round_001`，以便 `export_round=1` 写入 current（仅追溯，不影响分类）

快速检查：

```powershell
python -c "import json; from pathlib import Path
for t in ('seg','det','cap'):
 p=Path(f'data/ls_export/real_batch/{t}/round_001/export.json')
 data=json.loads(p.read_text(encoding='utf-8'))
 assert isinstance(data, list) and len(data)==3
 ids=[x['data']['image_id'] for x in data]
 print(t, 'ids', ids)
 for x in data:
  anns=x.get('annotations') or []
  assert anns, x['data']['image_id']"
```

### Step 4 Checklist

| 检查项 | 预期 | 实际 | 是否通过 |
|---|---|---|---|
| 三项目 XML 与任务类型匹配 | 通过 |  |  |
| Local Files 根/子路径正确 | 图能显示 |  |  |
| 首轮无预填几何/模型文本 | 通过 |  |  |
| 000001 有效标注 | 每任务都有 |  |  |
| 000002 空载荷 | 每任务都空 |  |  |
| 000003 勾选 needs_rework=yes | 每任务都是 |  |  |
| 三份 round_001/export.json | 各 3 条 |  |  |
| export 为 JSON 数组且含 annotations | 通过 |  |  |

---

## Step 5 export-split 测试（第 1 轮）

### 说明

内部调用 `apply-current`：解析 LS export（**只取人工 annotation**）→ 按 `image_id` 合并写入 `current/` → **全量重建** `normal/` 与 `rework/`，并写出 `rework/previous_annotations/`。

分类不以「是否勾了 needs_rework」为唯一条件。000002 即使 confirmed=yes 且 rework=no，也会因空载荷进 rework。

### 执行命令

```bash
mma export-split --batch real_batch --task seg --export data/ls_export/real_batch/seg/round_001/export.json --data-root data
mma export-split --batch real_batch --task det --export data/ls_export/real_batch/det/round_001/export.json --data-root data
mma export-split --batch real_batch --task cap --export data/ls_export/real_batch/cap/round_001/export.json --data-root data
```

### 看什么输出

每个任务打印两行路径（先 normal 后 rework），退出码 0。

### 输出目录

每个任务：

```text
data/results/real_batch/<task>/
├── current/annotations.json
├── normal/annotations.json
├── rework/
│   ├── annotations.json
│   └── previous_annotations/
│       ├── <task>.json          # seg.json / det.json / cap.json
│       └── masks/               # 仅 SEG
└── manual_masks/                # 仅 SEG：{image_id}_manual.png
```

### 验证分类（第 1 轮预期）

每个任务均应为：

| 目录 | image_id |
|---|---|
| `normal/` | 仅 `real_batch__000001` |
| `rework/` | `real_batch__000002`（空载荷）与 `real_batch__000003`（needs_rework） |
| `current/` | 上述 3 条全部存在 |


SEG 额外检查：

- `data/results/real_batch/seg/manual_masks/` 下应有 `real_batch__000001_manual.png`、`000002_manual.png`（空 mask）、`000003_manual.png`
- 000002 的 `annotation.has_foreground` 应为 `false`（若字段存在）
- DET 000002 的 `annotation.bboxes` 为 `[]`；CAP 000002 的 `caption` 为 `""`

previous_annotations：

- 存在 `rework/previous_annotations/seg.json`（及 det.json / cap.json）
- 条目对应 rework 的 2 个 image_id
- **这是人工快照，不是模型预测**；文件内不应被当成 prelabels.json

### 负例：此时 merge 必须失败

```bash
mma merge --batch real_batch --data-root data
```

**预期：** 退出码 2，stderr 含 `batch not ready for merge`，并指出 `needs_rework residual` 和/或 `empty task payload`。`data/final/real_batch/` 不应被写成完整金标准（失败不得改写已有 final；若目录本不存在则仍不存在）。

### Step 5 Checklist

| 检查项 | 预期 | 实际 | 是否通过 |
|---|---|---|---|
| 三任务 export-split 退出码 | 0 |  |  |
| current 条数 | 各 3 |  |  |
| 正常样本进 normal | 仅 000001 |  |  |
| 空标注进 rework | 000002 |  |  |
| 勾选返工进 rework | 000003 |  |  |
| SEG manual_masks 写出 | 有 PNG |  |  |
| previous_annotations 写出 | 有，且仅人工历史 |  |  |
| 无 prediction_fallback 填金标准 | current 空样本仍空 |  |  |
| 此时 merge | 失败 |  |  |
| 未再跑 apply-current | 通过 |  |  |

---

## Step 6 rework-import 测试（第一次返工准备）

### 说明

V1 主路径：**优先**读 `rework/previous_annotations/<task>.json`，**忽略** `--export` 的几何预填。不读 `prelabels/`。空 rework 时写出 `[]`。输出文件名为 `rework_tasks.json`，**不覆盖**首轮 `tasks.json`。

快照 **不含原图**；生成 URL 仍依赖 `task_packages/.../images/`。

### 输入

```text
data/results/real_batch/<task>/rework/annotations.json
data/results/real_batch/<task>/rework/previous_annotations/
data/task_packages/real_batch/<task>/
```

### 执行

不要传 `--export`（本机已有 previous_annotations）：

```bash
mma rework-import --batch real_batch --task seg --data-root data
mma rework-import --batch real_batch --task det --data-root data
mma rework-import --batch real_batch --task cap --data-root data
```

### 看什么输出

各打印 `data/ls_import/real_batch/<task>/rework_tasks.json`。

说明（易混点）：

- 返工 JSON **会有** LS 字段名 `predictions`，`model_version` 固定为 `mma-rework-prev-1.0`
- **业务语义是上一轮人工历史预填**，不是模型推理
- 后续 `export-split` 解析金标准时 **不会** 用该槽位回填（`prediction_fallback` 已删除）
- 000002 的预填几何/文本应为空或空 mask；000003 应能看到上一轮人工多边形/框/文案

### Step 6 Checklist

| 检查项 | 预期 | 实际 | 是否通过 |
|---|---|---|---|
| `rework_tasks.json` 生成 | 成功 |  |  |
| 未覆盖 `tasks.json` | 首轮仍 3 条空任务结构 |  |  |
| 返工条数 | 2（000002、000003） |  |  |
| 预填源 | previous_annotations，无 --export |  |  |
| 无 prelabels 读取 | 通过 |  |  |
| LS `predictions` 槽 | 仅人工历史，version=`mma-rework-prev-1.0` |  |  |
| 原图 URL 仍指向 task_packages | 通过 |  |  |

---

## Step 7 第二轮返工测试（失败一轮 + 成功一轮）

目标：证明 rework 闭环。至少：**第一次返工失败，第二次返工成功**。

### 7.1 导入返工任务到 Label Studio

在对应 SEG/DET/CAP 项目中 Import `rework_tasks.json`。

打开 000003：应看到上一轮人工结果预填。打开 000002：应仍接近空白。

**导出防重复（硬性）：** `parse_ls_export` 遇到同一文件内重复 `image_id` 会失败。因此：

- 同一项目里若仍保留首轮 3 条任务，**禁止**整项目全量 Export
- 只导出**本轮新导入的返工任务**（界面勾选 000002、000003 再导出）
- 或每轮新建项目，只导入 `rework_tasks.json`

### 7.2 第一次返工标注（round_002）——故意失败闭环未完成

| image_id | 操作 | 勾选 |
|---|---|---|
| `real_batch__000002` | **补上有效标注**（SEG 多边形 / DET 至少 1 框 / CAP 非空文本） | confirmed=`yes`，rework=`no` |
| `real_batch__000003` | 可微调，但 **保持** `needs_rework=yes` | confirmed=`yes`，rework=`yes` |

这就是「第一次返工失败」：000003 仍需返工。

导出到：

```text
data/ls_export/real_batch/{seg,det,cap}/round_002/export.json
```

每个文件应含 **2** 条（子集）。然后：

```bash
mma export-split --batch real_batch --task seg --export data/ls_export/real_batch/seg/round_002/export.json --data-root data
mma export-split --batch real_batch --task det --export data/ls_export/real_batch/det/round_002/export.json --data-root data
mma export-split --batch real_batch --task cap --export data/ls_export/real_batch/cap/round_002/export.json --data-root data
```

**验证（第 1 次返工后）：**

| 目录 | 预期 image_id |
|---|---|
| current | 仍为 3 条（000001 未出现在本轮 export，被保留） |
| normal | `000001` + `000002` |
| rework | 仅 `000003` |


```

此时再跑 `mma merge` **仍必须失败**（000003 `needs_rework`）。

再次生成返工导入（只剩 000003）：

```bash
mma rework-import --batch real_batch --task seg --data-root data
mma rework-import --batch real_batch --task det --data-root data
mma rework-import --batch real_batch --task cap --data-root data
```

**预期：** `rework_tasks.json` 各 **1** 条，`image_id=real_batch__000003`。

### 7.3 第二次返工标注（round_003）——成功清零

Import 新的 `rework_tasks.json`（仅 000003）。本轮：

- 确认预填来自 round_002 的人工结果
- 必要时修正多边形/框/文本
- `human_confirmed=yes`，`needs_rework=no`
- 保持有效载荷（不要清空）

导出到：

```text
data/ls_export/real_batch/{seg,det,cap}/round_003/export.json
```

各 1 条。然后 `export-split` 三条（同上，把 `round_002` 换成 `round_003`）。

**验证（第 2 次返工后 / merge 前自检）：**

三路 `current/annotations.json`：

- 各 3 条
- 全部 `human_confirmed: true`
- 全部 `needs_rework: false`
- SEG：`has_foreground: true` 且 `mask_ref` 非空
- DET：`bboxes` 长度 ≥ 1
- CAP：`caption` strip 后非空
- `image_id` 集合等于 processed 全量 `{000001,000002,000003}`
- `normal/` 3 条，`rework/annotations.json` 为 `[]`


### Step 7 Checklist

| 检查项 | 预期 | 实际 | 是否通过 |
|---|---|---|---|
| round_002 子集导出 | 各 2 条 |  |  |
| 000002 进入 normal | 通过 |  |  |
| 000003 仍在 rework（第一次失败） | 通过 |  |  |
| 000001 仍在 current（未被子集导出删掉） | 通过 |  |  |
| 第二次 rework-import 仅 000003 | 通过 |  |  |
| 返工预填可见上一轮人工结果 | 通过 |  |  |
| round_003 后 rework 为空 | 通过 |  |  |
| 三路 current 无 should_rework_result | 通过 |  |  |

---

## Step 8 merge 测试

### 执行条件

同时满足（`validate_ready`）：

1. SEG、DET、CAP 的 `current/annotations.json` 均可加载且非空
2. 无 `should_rework_result` 残留（未确认 / 需返工 / 空载荷）
3. 三路 `image_id` 集合彼此相等
4. 该集合等于 `processed/real_batch/manifest.json` 全量
5. processed 中 `image_path` 指向的原图文件仍存在（merge 要从这里拷图）

不依赖 `prelabels/`。缺任一任务直接失败，禁止静默缺字段。

### 执行

```bash
mma merge --batch real_batch --data-root data
```

### 看什么输出

```text
D:\多任务标注平台V1\data\final\real_batch\manifest.json
```

退出码 0。

### 检查 final/

```text
data/final/real_batch/
├── manifest.json
├── images/
│   ├── real_batch__000001.jpg
│   ├── real_batch__000002.jpg
│   └── real_batch__000003.jpg
└── masks/
    ├── real_batch__000001.png
    ├── real_batch__000002.png
    └── real_batch__000003.png
```

```powershell
python -c "import json; from pathlib import Path
root=Path('data/final/real_batch')
m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
assert m['batch_id']=='real_batch' and len(m['items'])==3
for it in m['items']:
 iid=it['image_id']
 assert it['image_path']==f'images/{iid}.jpg'
 assert it['seg']['mask_ref']==f'masks/{iid}.png'
 assert (root/it['image_path']).is_file()
 assert (root/it['seg']['mask_ref']).is_file()
 assert len(it['det']['bboxes'])>=1
 assert str(it['cap']['caption']).strip()
 assert it.get('diagnosis_text')
 print(iid, 'OK', 'bbox', len(it['det']['bboxes']), 'cap', it['cap']['caption'][:24])
print('final OK')"
```

### 验证要点

- `image_path` **必须**相对路径 `images/{image_id}.jpg`（禁止绝对路径）
- `seg.mask_ref` **必须** `masks/{image_id}.png`（禁止 `manual_masks/`、`prelabels/`、`final_assets/`）
- DET `bboxes` 为像素框列表（x/y/width/height）
- CAP `caption` 为人工文案，可与 Excel `diagnosis_text` 不同
- final 自包含：拷走 `final/real_batch/` 即可，不依赖 raw/processed
- 数值不必与其它机器一致；结构必须一致

### Step 8 Checklist

| 检查项 | 预期 | 实际 | 是否通过 |
|---|---|---|---|
| merge 退出码 | 0 |  |  |
| manifest 生成 | 成功 |  |  |
| items 数量 | 3 |  |  |
| 每条含 seg+det+cap | 通过 |  |  |
| images/ 三张 jpg | 存在 |  |  |
| masks/ 三张 png | 存在 |  |  |
| 相对路径契约 | `images/*.jpg`、`masks/*.png` |  |  |
| caption 非空 | 通过 |  |  |
| detection 至少 1 框 | 通过 |  |  |
| 未改写 current / manual_masks | 通过 |  |  |

---

# 5. 分阶段验收 Checklist 汇总

可将下表复制到测试记录。每行填「实际 / 是否通过」。

## 5.1 环境

| 检查项 | 预期 |
|---|---|
| Python | ≥ 3.12 |
| `mma -h` | 列出 V1 子命令 |
| LS 独立安装并启动 | 可登录 |
| DOCUMENT_ROOT | data 绝对路径 |

## 5.2 preprocess

| 检查项 | 预期 |
|---|---|
| manifest 生成 | 成功 |
| image 数量 | 3 |
| image_id | `real_batch__000001`…`000003` |
| diagnosis | 读取成功 |

## 5.3 package

| 检查项 | 预期 |
|---|---|
| 三类任务独立生成 | 成功 |
| 每包图片 | 3 |
| manifest package_id | `real_batch__seg/det/cap` |

## 5.4 ls-import

| 检查项 | 预期 |
|---|---|
| tasks.json | 三个文件，各 3 条 |
| 无 prediction 字段 | 通过 |
| 仅 data 四字段 | 通过 |
| 符合 LS 导入格式 | JSON 数组 |

## 5.5 人工标注与导出

| 检查项 | 预期 |
|---|---|
| 首轮空白可标 | 通过 |
| 正常 / 空 / 返工样本已按矩阵制造 | 通过 |
| round_001 全量 JSON | 各 3 条 |

## 5.6 export-split round_001

| 检查项 | 预期 |
|---|---|
| 000001 → normal | 通过 |
| 000002 空标注 → rework | 通过 |
| 000003 → rework | 通过 |
| current 更新 | 3 条 |
| merge 仍失败 | 通过 |

## 5.7 返工闭环

| 检查项 | 预期 |
|---|---|
| rework-import 2 条 | 通过 |
| 预填为人工历史 | 通过 |
| 第 1 次返工后仍有 000003 | 通过 |
| 第 2 次返工后 rework=[] | 通过 |

## 5.8 merge

| 检查项 | 预期 |
|---|---|
| final/manifest.json | 成功 |
| items | 3 |
| images + masks | 齐全 |
| 三任务字段完整 | 通过 |

---

# 6. 异常排查

## 6.1 `mma` 命令不存在

**原因：** 未激活 venv，或未 `pip install -e .`，或用了错误解释器。

**解决：**

```powershell
.\.venv\Scripts\activate
pip install -e .
mma -h
```

仍失败则用 `python -m mma -h`。

---

## 6.2 Label Studio 无法加载图片

**原因：** `DOCUMENT_ROOT` ≠ `--local-root`/`--data-root`；Cloud Storage 路径填成了 `data` 本身或项目根；`d=` 被改成反斜杠；尚未 `package`；LS 未开 Local Files serving。

**解决：**

1. 确认环境变量 `LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true`
2. `DOCUMENT_ROOT` = `D:\多任务标注平台V1\data`
3. Source Storage Absolute path = `...\data\task_packages`
4. 打开 `tasks.json` 看 `data.image`，在资源管理器打开对应 jpg
5. 重启 Label Studio 后再 Sync

---

## 6.3 export 后没有 rework

**原因：** 三张都有效标注且全部 confirmed=yes、rework=no；或看错了任务目录；或以为空勾选会进 normal（V1 不会）。

**解决：** 按 Step 4 矩阵重标 000002（空）和 000003（needs_rework=yes），全量导出后再 `export-split`。检查 `should_rework_result` 三条支路。注意：`docs/data_layout.md` §4.7 若只写了勾选规则、未写空载荷，以 **代码** `should_rework_result` 为准。

---

## 6.4 merge 失败

**常见 stderr：**

| 片段 | 含义 | 处理 |
|---|---|---|
| `needs_rework residual` | current 仍有返工勾选 | 继续返工或全量刷新 |
| `human_confirmed missing` | 未确认 | 勾选 yes 后 export-split |
| `empty task payload` | 已确认且未勾返工但空框/空文/空 mask | 补有效标注 |
| `image_id sets differ` | 三任务集合不一致 | 缺的任务补全量轮 |
| `does not match processed` | 与 processed 全量不等 | 首轮必须全量导出 3 条 |
| `processed manifest not found` | 缺 preprocess | 重跑 preprocess |
| `source image not found` | processed 绝对路径失效 | 原图仍在原路径，或重跑 preprocess+package 后再 merge |
| `duplicate image_id in export` | 一份 export 里同一 id 两次 | 子集导出，勿混首轮+返工 |

---

## 6.5 `mma preprocess` 报 unsupported file

**原因：** `images/` 里有非 jpg/jpeg（png、xlsx、Thumbs.db 等）。

**解决：** 只保留三张 jpg。

---

## 6.6 `mma ls-import` 失败

**原因：** 未 package；`--task` 不是 `seg|det|cap`；图像不在 local_root 之下。

**解决：** 先 package；`--local-root` 保持默认等于 data-root。

---

## 6.7 `mma export-split` 与未提交 / 空标注

**现行行为（P1）：** 导出 JSON 里已出现的样本，若 `annotations` 为空/`null`、全部 cancelled、`result` 为空/`null`、或缺少 `human_confirmed`，会解析为空载荷（`human_confirmed=false`）并进入 **`rework/`**，**不**因此整批失败。金标准仍只认人工 annotation，不会用 predictions 回填。

**仍会整批失败的情况：** JSON 不是数组；缺 `data.image_id`；`human_confirmed` 值为非法（非 yes/no）；控件串任务；SEG 空样本且无法从任务包得到图像尺寸。

**未出现在本轮 export 中的样本：** current 里已有的 id **保留**旧值（支持返工子集导出）。任务包有、但本轮 export 与 current 都没有的 id，写入空结果（未确认、无有效载荷）并进入 **`rework/`**。export 含任务包没有的 `image_id`、或缺少任务包 `manifest.json`，整批失败。

---

## 6.8 返工导入无图 / 无预填

**原因：** 只拷了 `rework/` 没有 `task_packages` 图像；或缺少 `previous_annotations`。

**解决：** 本机保留任务包图像。无快照须先 `export-split` / `apply-current`。`rework-import --export` 不用于预填。

---

## 6.9 首轮任务里看到预填

**原因：** 导入了 `rework_tasks.json`，或使用了 Legacy `mma.legacy.converters.document_to_ls_tasks` / 历史 convert 产物。

**解决：** 首轮只导入 `tasks.json`。确认文件无 `predictions` 键。

---

## 6.10 `mma convert` 被执行

**原因：** 按 V2/历史文档操作。

**解决：** 该命令是 stub，stderr 提示改用 `ls-import`，退出码 2。V1 验收禁止依赖它。

---

## 6.11 SEG 多边形导出后 mask 全黑 / has_foreground=false

**原因：** 未真正提交多边形；或画在错误控件上；或导出的不是 annotation。

**解决：** 确认 `from_name=seg_mask`。空 mask 会进 rework。补画后重新 export-split。

---

## 6.12 PowerShell `&&` 报错

**原因：** 旧版 PowerShell 不支持 `&&`。

**解决：** 用 `;` 分隔，或逐条执行。

---

# 7. 测试最终验收标准

同时满足以下条件，判定 **V1 本地真实数据全链路测试通过**：

1. **preprocess 成功**：`processed/real_batch/manifest.json` 存在，3 条绑定，`image_id` 规则正确。
2. **package 成功**：三类 `task_packages/real_batch/{seg,det,cap}/` 独立存在，图与 manifest 完整。
3. **LS 导入成功**：三个 `tasks.json` 可导入；原图可见；**无** `predictions`。
4. **人工标注结果成功导出**：三轮 JSON 按约定落在 `ls_export/.../round_00N/`，且均为 annotation 而非 prediction 金标准。
5. **normal / rework 逻辑正确**：000001→normal；000002 空标注→rework；000003 勾选→rework。
6. **两轮返工闭环成功**：第 1 轮返工后 000003 仍在 rework；第 2 轮后三路 `rework=[]`，current 全确认且有效载荷齐全。
7. **SEG / DET / CAP merge 成功**：`mma merge` 退出码 0。
8. **final 数据结构正确**：`manifest.json` 3 条；相对路径 `images/{id}.jpg`、`masks/{id}.png`；含 caption 与 detection 框；包自包含。

附加否决项（任一条即不通过）：

- 主流程依赖 `prelabels/` 或 `mma convert`
- 空标注进入 `normal/`
- 金标准来自 LS `predictions` / 模型预填
- 只完成单任务就 merge 成功
- 文档步骤与本机命令不一致且未按代码执行

---

# 8. 测试记录模板

复制本节填写后随验收材料归档。

```text
================================================================
V1 本地真实数据全链路测试记录
================================================================

测试日期：__________
代码版本：mma 0.1.0 / git commit：__________
测试人员：__________
操作系统 / Python：__________ / __________
数据 batch：real_batch
图像来源：□ 真实医学图  □ examples/raw/demo_batch 拷贝
Label Studio 版本：__________

----------------------------------------------------------------
执行结果（勾选）
----------------------------------------------------------------
[ ] Step 1 preprocess
[ ] Step 2 package
[ ] Step 3 ls-import（空任务、无 predictions）
[ ] Step 4 LS 人工标注 + round_001 导出
[ ] Step 5 export-split（normal/rework/current 符合矩阵）
[ ] Step 5b 提前 merge 失败（预期失败）
[ ] Step 6 rework-import（previous_annotations）
[ ] Step 7 第一次返工失败（000003 仍 rework）
[ ] Step 7 第二次返工成功（rework 空）
[ ] Step 8 merge → final 结构正确

总评：□ 通过  □ 不通过  □ 有条件通过（说明）

----------------------------------------------------------------
问题记录
----------------------------------------------------------------
编号 | 步骤 | 现象 | 日志/路径 | 严重程度
1    |      |      |           |
2    |      |      |           |

----------------------------------------------------------------
修复记录
----------------------------------------------------------------
编号 | 处理 | 验证人 | 日期
1    |      |        |

----------------------------------------------------------------
关键路径摘录（可选粘贴命令 stdout）
----------------------------------------------------------------
preprocess:
package:
ls-import seg/det/cap:
export-split round_001:
merge:

----------------------------------------------------------------
签字
----------------------------------------------------------------
测试：__________ 日期：__________
复核：__________ 日期：__________
```

---

# 附录 A. 文档与代码差异（以代码为准）

编写本 SOP 时核对到的不一致，验收时不要按过时段落执行：

| 来源 | 过时 / 不完整表述 | 代码实际 |
|---|---|---|
| `docs/data_layout.md` §4.7 | 已与 `should_rework_result` 三支路对齐 | 运行时：`(not human_confirmed) or needs_rework or (not effective_payload)` |
| `docs/real_batch_local_test_runbook.md` | 项目根写成 `D:\多任务标注平台`；含放置 prelabels、raw `masks/` | 本仓库为 V1 路径；preprocess 不读 masks；主流程不读 prelabels |
| `docs/labelstudio_usage.md` §4 | 只强调 Local storage 根 = data | 实践上 DOCUMENT_ROOT=`data`，Cloud Storage 绝对路径须为 **子目录** `data/task_packages`（与旧 runbook 4.3 一致，且符合 LS 限制） |
| `docs/formats.md` | 整份为 Legacy 预标注格式 | V1 验收不要准备 `prelabels.json` |
| `src/mma/labelstudio/configs/cap.xml` | 界面标题已改为「人工描述」 | 首轮 `cap_text` 为空，须人工填写 |
| README vs 旧 runbook | README 已是空任务主路径 | 旧手册历史半自动步骤仅对照，不作为 V1 必做 |

权威优先级：**`src/mma` 实现 > README.md > 本 SOP > 其它 docs。**

---

# 附录 B. 真实 CLI 速查（禁止虚构）

摘自 `src/mma/cli.py`，参数名为实现所有：

```bash
mma preprocess --batch <id> --images <dir> --excel <xlsx> [--data-root data]
mma package --batch <id> [--data-root data]
mma ls-import --batch <id> --task {seg|det|cap} [--data-root data] [--local-root]
mma export-split --batch <id> --task {seg|det|cap} --export <export.json> [--data-root data]
mma apply-current --batch <id> --task {seg|det|cap} --export <export.json> [--data-root data]
mma rework-import --batch <id> --task {seg|det|cap} [--export <legacy.json>] [--data-root data] [--local-root]
mma merge --batch <id> [--data-root data]
mma convert --batch <id> --task {seg|det|cap}    # LEGACY stub，退出码 2
```

`--task` 仅允许：`seg`、`det`、`cap`。

角色薄包装（可选，等价调用 `mma`）：见 `deploy/v1/data_processor/README.md` 的 `python bin/*.py ...`。本 SOP 以仓库根 `mma` 为准。

---

# 附录 C. 轮次与样本状态机（本批）

```text
round_001 全量标注
  000001 有效 + 确认 + 不返工     → normal
  000002 空载荷 + 确认 + 不返工   → rework   （空标注规则）
  000003 有效 + 确认 + 要返工     → rework
  merge → 失败

round_002 返工子集
  000002 补有效 + 确认 + 不返工   → normal   （第一次返工成功该样本）
  000003 仍要返工                 → rework   （第一次返工失败）
  000001 未出现在 export          → current 保留
  merge → 失败

round_003 返工子集
  000003 有效 + 确认 + 不返工     → normal   （第二次返工成功）
  rework = []
  merge → final 3 条金标准
```

---

# 附录 D. 相关文件

| 文件 | 用途 |
|---|---|
| `README.md` | V1 定位与 CLI 总览 |
| `docs/data_layout.md` | 目录契约（分类规则以代码补全） |
| `docs/labelstudio_usage.md` | LS 操作说明 |
| `docs/real_batch_local_test_runbook.md` | 历史手册；V1 跳过 Legacy 段 |
| `docs/formats.md` | Legacy，非本验收输入 |
| `docs/M12.6_FINAL_FREEZE_REPORT.md` | 冻结报告 |
| `tests/test_m12_1_normal_path.py` 等 | 规则自动化门禁，不替代本 SOP |
| `src/mma/cli.py` | 命令与参数权威 |
| `src/mma/common/models.py` | `should_rework_result` 权威 |
