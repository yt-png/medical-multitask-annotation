# Label Studio 本地使用说明（T3.5）

本文说明如何在**本机 Label Studio**中完成 SEG / DET / CAP 三任务的导入与人工确认。  
协作分发仍通过网盘人工完成；本仓库不提供业务服务端，也不自动上传下载。

相关约定见：

- 目录落盘：[data_layout.md](data_layout.md)
- 预标注格式与工作台控制名：[formats.md](formats.md)

---

## 1. 目的与范围

**本文重点**

- 用 `mma ls-import` 生成可导入 JSON
- 配置 Label Studio Local Files，使原图可加载
- 为 SEG / DET / CAP 分别创建项目并加载对应 Labeling Config
- 导入任务、人工确认与勾选、导出结果建议落盘位置

**本文不展开（见 README / 其他文档）**

- P4/P5 的命令细节与合并验收（导出后可用 `apply-current` / `export-split` / `rework-import` / `merge`，见本文 §8 与仓库 README）
- 真实预标注算法 / 大模型调用（不在本阶段范围）

---

## 2. 前置条件

1. 已按仓库 `README.md` 安装本包（建议 `pip install -e .`，Python 3.12+）。
2. 本机已安装可用的 Label Studio（开源桌面/本地服务均可；界面文案可能随版本略有差异）。
3. 运行时数据根下已具备（以 `--data-root data` 为例）：
   - `data/task_packages/<batch_id>/{seg|det|cap}/images/`（原图）
   - `data/prelabels/<batch_id>/{seg|det|cap}/prelabels.json`（统一中间格式）
   - SEG 另需 mask 文件，路径与 `prelabels.json` 中 `mask_ref` 一致（相对该任务 prelabels 目录）

---

## 3. 生成本地导入文件

对每个任务类型各执行一次（将 `demo_batch` / `seg` 换成实际批次与任务）：

```bash
mma ls-import --batch demo_batch --task seg --data-root data
mma ls-import --batch demo_batch --task det --data-root data
mma ls-import --batch demo_batch --task cap --data-root data
```

**输出**

- `data/ls_import/<batch_id>/<task>/tasks.json`

**参数说明**

| 参数 | 含义 |
|------|------|
| `--data-root` | 运行时数据根（默认当前目录下的 `data`） |
| `--local-root` | 写入 Local Files URL 时的相对根；**默认等于 `--data-root`**。必须与 Label Studio 中配置的 Local storage 根一致 |

生成后，任务里的 `data.image` 形如：

```text
/data/local-files/?d=task_packages/demo_batch/seg/images/demo_batch__000001.jpg
```

即：`d=` 后面是相对 `local_root` 的**正斜杠**路径。图像**不会**复制进 `ls_import/`。

SEG 在导入生成时会默认以 `data/prelabels/<batch>/seg` 为 `mask_root`，将 mask 拆连通域后写入 brush 预填；缺 mask 文件会失败（需先补齐预标注资源）。

---

## 4. 配置 Label Studio Local Files

1. 打开 Label Studio，进入 **Local Storage**（或 Settings → Cloud Storage → Local files，名称因版本而异）。
2. 将本地存储根目录设置为与 `mma ls-import` 的 **`local_root` 相同**的绝对路径。  
   - 若命令使用 `--data-root D:\多任务标注平台\data` 且未指定 `--local-root`，则 Local storage 根应设为 `D:\多任务标注平台\data`。
3. 保存并确保存储已启用 / 可同步（按你使用的 LS 版本操作）。

**注意：** Local storage 根若指错（例如指到项目根而 URL 相对的是 `data/`），会出现任务能导入但**原图空白/加载失败**。

---

## 5. 创建三任务项目并加载工作台 XML

建议为 SEG / DET / CAP **各建一个项目**（链路独立）。

### 5.1 配置文件位置

安装本包后，XML 在包内：

| 任务 | 文件 |
|------|------|
| SEG | `src/mma/labelstudio/configs/seg.xml`（或已安装包中的同名文件） |
| DET | `src/mma/labelstudio/configs/det.xml` |
| CAP | `src/mma/labelstudio/configs/cap.xml` |

也可用 Python 打印路径后打开：

```python
from mma.labelstudio import seg_config_path, det_config_path, cap_config_path
print(seg_config_path())
print(det_config_path())
print(cap_config_path())
```

### 5.2 加载方式

在对应项目的 **Labeling Interface / Labeling Config** 中：

1. 打开上述 XML，**全选复制**到 Label Studio 配置编辑器；或按 LS 版本提供的「从文件导入配置」加载。
2. 保存配置。

控件名已与转换层对齐（勿随意改 `name`）：

| 任务 | 主图 | 可编辑预标注 | 原文 | 勾选 |
|------|------|--------------|------|------|
| SEG | `image` ← `$image` | `BrushLabels` `seg_mask` / `lesion` | 只读 `$diagnosis_text` | `human_confirmed`、`needs_rework` |
| DET | 同上 | `RectangleLabels` `det_bbox` / `object` | 同上 | 同上 |
| CAP | 同上 | `TextArea` `cap_text` | 同上 | 同上 |

---

## 6. 导入任务

1. 在对应任务项目中选择 **Import**。
2. 导入文件：`data/ls_import/<batch_id>/<task>/tasks.json`。
3. 确认任务列表出现；打开样本应能看到原图，以及预标注（SEG 刷子 / DET 框 / CAP 文本）。

---

## 7. 标注操作要点

### 7.1 三任务共通

- **原始诊断文本**：只读对照，不要当成 CAP 预标注去改。
- **人工确认**（`human_confirmed`）：每张必选；选 `yes` 表示本样本已经过人工处理（无论是否改过预标注）。
- **是否需要返工**（`needs_rework`）：不确定时可选 `yes`；未勾选/选 `no` 表示本轮不进入返工包（后续分类逻辑见 P4）。
- 侧栏 `image_id` / `package_id` 仅供追溯，无需编辑。

### 7.2 SEG

- 预标注 mask 应叠在**原图**上，使用画笔修改区域。
- 同一张 mask 内多块不连通病灶会拆成多条同标签 `lesion` 区域，可分别编辑。
- `$mask_ref` 仅为路径追溯，不是主展示图。

### 7.3 DET

- 预标注框叠在原图上，可增删改多个框（标签 `object`）。
- 空框样本可在原图上新画框。

### 7.4 CAP

- 在 **预标注文本**（`cap_text`）中修改模型生成文案。
- 右侧/侧栏 **原始诊断文本** 保持只读，用于对照。

---

## 8. 导出

1. 在 Label Studio 中导出本轮结果（JSON）。
2. 建议人工保存到：

```text
data/ls_export/<batch_id>/<task>/
```

可选按轮次分子目录，例如 `round_001/`，避免覆盖历史排障材料。

导出后可用 P4 覆盖写入、按返工分类，并生成返工再导入任务：

```bash
mma apply-current --batch <batch_id> --task {seg|det|cap} --export <ls_export.json> --data-root data
mma export-split --batch <batch_id> --task {seg|det|cap} --export <ls_export.json> --data-root data
mma rework-import --batch <batch_id> --task {seg|det|cap} --export <ls_export.json> --data-root data
```

- `apply-current`：写出 `data/results/<batch_id>/<task>/current/annotations.json`（含本轮仍需返工样本）；SEG 若有 brush RLE 会同时写出 `results/.../seg/manual_masks/<image_id>_manual.png`
- `export-split`：写出 `.../normal/annotations.json` 与 `.../rework/annotations.json`（空侧为 `[]`）；SEG 与 current 同步物化 manual mask
- `rework-import`：写出 `data/ls_import/<batch_id>/<task>/rework_tasks.json`（不覆盖首轮 `tasks.json`）

### 8.1 `apply-current` 与导出范围

`apply-current` 按 `image_id` **合并**写入 `current/`：导出里出现的样本覆盖；**未出现的样本保留**。

| 轮次 | 导出范围 | 说明 |
|------|----------|------|
| **全量轮**（首轮或刷新整批权威状态） | 从对应任务 LS 项目导出本批**全部**已标注样本，再 apply | 避免旧返工标记因未出现在本轮 export 中而残留 |
| **返工轮** | 可只导出返工子集再 apply | 未导出的 id 留在 `current/`（含已 normal 样本），符合返工闭环 |

若只 apply 了子集，却希望尽快 `merge`，须保证 `current/` 中所有样本最终均被后续轮次刷新为不需返工（或本轮即为全量导出）。详见 [data_layout.md](data_layout.md) 中 `current/` 约定。

---

## 9. 常见问题

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 任务有、图不显示 | Local storage 根 ≠ `local_root`；或相对路径层级不对 | 核对 `--data-root` / `--local-root` 与 LS 本地根；确认 `d=` 下路径在磁盘上真实存在 |
| Windows 路径问题 | 混用反斜杠 | 本流水线生成的 `d=` 已用正斜杠；勿手改成 `\` |
| SEG 无预填刷子 | 生成导入时缺 mask，或未成功跑通 `ls-import` | 检查 `prelabels/.../masks/` 与 `mask_ref`；重新执行 `mma ls-import --task seg` |
| DET 转换失败 | 任务包缺图或图损坏 | 检查 `task_packages/.../images/{image_id}.jpg` |
| 导入报控件不匹配 | 项目 XML 与任务类型不一致 | SEG 项目只用 `seg.xml`，勿把 DET 的 `tasks.json` 导进 SEG 项目 |
| `merge` 仍报 needs_rework，但本轮以为已修完 | 只 apply 了部分导出，旧返工样本仍留在 `current/` | 全量导出再 `apply-current`；或继续返工轮直到 `current/` 无返工残留 |

---

## 10. 相关文档与命令速查

```bash
# 生成导入 JSON
mma ls-import --batch <batch_id> --task {seg|det|cap} --data-root data

# 可选：Local storage 根与 data 不同时
mma ls-import --batch <batch_id> --task seg --data-root data --local-root D:\path\to\local_root

# 导出后覆盖 current/
mma apply-current --batch <batch_id> --task {seg|det|cap} --export <ls_export.json> --data-root data

# 按返工分类写出 normal/rework
mma export-split --batch <batch_id> --task {seg|det|cap} --export <ls_export.json> --data-root data

# 生成返工再导入 tasks（不覆盖 tasks.json）
mma rework-import --batch <batch_id> --task {seg|det|cap} --export <ls_export.json> --data-root data
```

- [data_layout.md](data_layout.md) — `ls_import` / `ls_export` / `task_packages` / `prelabels`
- [formats.md](formats.md) — 中间格式与 SEG/DET/CAP 控制名对齐
- 仓库根 [README.md](../README.md) — 安装与 CLI 总览
