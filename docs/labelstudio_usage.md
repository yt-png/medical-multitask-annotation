# Label Studio 本地使用说明

本文说明如何在**本机 Label Studio**中完成 SEG / DET / CAP 三任务的导入与人工标注。  
协作分发仍通过网盘人工完成；本仓库不提供业务服务端，也不自动上传下载。

**V1 目标**：纯人工金标准——首轮为空任务导入（无模型 / prelabel 预填）；返工预填仅为上一轮**人工历史**。  
**已落地（摘要）**：`mma ls-import` 仅从 `task_packages/` 生成空任务（**无** `predictions`）；金标准仅人工 annotation。返工时 LS 字段名可能仍叫 `predictions`，业务上承载的是 **historical human prefill**，**不是**模型推理输出。详见仓库根 README / CHANGELOG。

相关约定见：

- 目录落盘：[data_layout.md](data_layout.md)
- Legacy 预标注格式（非主流程）：[formats.md](formats.md)

---

## 1. 目的与范围

**本文重点**

- 用 `mma ls-import` 生成可导入 JSON
- 配置 Label Studio Local Files，使原图可加载
- 为 SEG / DET / CAP 分别创建项目并加载对应 Labeling Config
- 导入任务、人工标注与勾选、导出结果建议落盘位置
- 区分：**首轮空任务（目标）** vs **返工人工历史预填**

**本文不展开**

- 合并验收细节（`merge` 见 README）
- 真实预标注算法 / 大模型调用（不在 V1 范围；Legacy 见 `formats.md`）

---

## 2. 前置条件

1. 已按仓库 `README.md` 安装本包（建议 `pip install -e .`，Python 3.12+）。
2. 本机已安装可用的 Label Studio（开源桌面/本地服务均可；界面文案可能随版本略有差异）。
3. 运行时数据根下已具备（以 `--data-root data` 为例）：
   - **必需**：`data/task_packages/<batch_id>/{seg|det|cap}/images/`（原图）与同目录 `manifest.json`
   - **不需要** `prelabels/`（历史目录仅作 Legacy 对照，非 V1 首轮导入输入）

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

### 3.1 首轮任务内容

| | 行为（已落地） |
|---|---|
| 输入 | 仅 `task_packages/` |
| `tasks.json` | 每条仅 `data`（`image`、`image_id`、`package_id`、`diagnosis_text`）；**无** `predictions` |
| 标注员所见 | 空白控件，从零人工标注 |

返工导入时可能写入 LS `predictions` 槽位：内容来自 `previous_annotations`（人工历史），**不是**模型推理。

---

## 4. 配置 Label Studio Local Files

1. 打开 Label Studio，进入 **Local Storage**（或 Settings → Cloud Storage → Local files，名称因版本而异）。
2. 将本地存储根目录设置为与 `mma ls-import` 的 **`local_root` 相同**的绝对路径。  
   - 若命令使用 `--data-root D:\多任务标注平台V1\data` 且未指定 `--local-root`，则 Local storage 根应设为该 `data` 绝对路径。
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

标注员角色包内有同步副本（与源文件内容一致，见 M9.2）：`deploy/v1/annotator_{seg,det,cap}/configs/`。权威源仍为 `src/mma/labelstudio/configs/`。

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

控件名勿随意改 `name`：

| 任务 | 主图 | 可编辑标注控件 | 原文 | 勾选 |
|------|------|----------------|------|------|
| SEG | `image` ← `$image` | `PolygonLabels` `seg_mask` / `lesion`（解析仍兼容历史 Brush RLE） | 只读 `$diagnosis_text` | `human_confirmed`、`needs_rework` |
| DET | 同上 | `RectangleLabels` `det_bbox` / `object` | 同上 | 同上 |
| CAP | 同上 | `TextArea` `cap_text` | 同上 | 同上 |

---

## 6. 导入任务

1. 在对应任务项目中选择 **Import**。
2. 导入文件：`data/ls_import/<batch_id>/<task>/tasks.json`。
3. 确认任务列表出现；打开样本应能看到原图。
   - 首轮：无预填几何/模型文本，需人工绘制或填写。
   - 返工包：若见 LS `predictions` 槽位预填，内容来自上一轮**人工** `previous_annotations`，不是模型推理。

---

## 7. 标注操作要点

### 7.1 三任务共通

- **原始诊断文本**：只读对照；CAP 请在 `cap_text` 中书写/编辑**人工**文案，不要把原文控件当成可提交结果。
- **人工确认**（`human_confirmed`）：每张必选；选 `yes` 表示本样本已经过人工处理。选 `no` 表示未确认，导出分类时进入 **rework**（即使 `needs_rework=no`）。
- **是否需要返工**（`needs_rework`）：不确定时可选 `yes`；未勾选/选 `no` **单独不足以**进 normal。分类规则（**当前已实现**）：`should_rework_result = (not human_confirmed) or needs_rework or (not effective_payload)`。
- **空标注 → rework（已落地）**：无有效人工载荷（空 result / 缺 mask·bbox·text）也应进 `rework/`；另含未确认 / 勾选需返工等规则。金标准路径**无** prediction fallback。
- 侧栏 `image_id` / `package_id` 仅供追溯，无需编辑。

### 7.2 SEG

- 工作台为 **PolygonLabels**（`seg_mask` / `lesion`），用**多边形**增删改区域。
- 首轮从空白开始勾画病灶；返工预填若出现，来自上一轮人工历史（非 model/prelabel）。
- `$mask_ref` 仅为路径追溯（若出现），不是主展示图。
- 解析仍兼容历史 Brush RLE 导出；新任务工作台为 polygon。

### 7.3 DET

- 在原图上增删改检测框（标签 `object`）。
- 首轮无预填框；返工预填若出现，来自上一轮人工历史（非 model/prelabel）。

### 7.4 CAP

- 在 **`cap_text`** 中填写/修改人工描述文本。
- 右侧/侧栏 **原始诊断文本** 保持只读，用于对照。
- **勿**将模型预标注文案当作 V1 必经步骤（Legacy 演示除外）。

---

## 8. 导出

1. 在 Label Studio 中导出本轮结果（JSON）。
2. 建议人工保存到：

```text
data/ls_export/<batch_id>/<task>/
```

可选按轮次分子目录，例如 `round_001/`，避免覆盖历史排障材料。

导出后可用下列命令（**二选一** apply / export-split），再生成返工再导入任务：

```bash
# 推荐：一条命令 = apply-current + 返回/写出 normal、rework（勿再跑 apply-current）
mma export-split --batch <batch_id> --task {seg|det|cap} --export <ls_export.json> --data-root data

# 或仅底层同步 current（实现上同样会刷新 normal/rework；勿再紧跟 export-split）
mma apply-current --batch <batch_id> --task {seg|det|cap} --export <ls_export.json> --data-root data

mma rework-import --batch <batch_id> --task {seg|det|cap} --data-root data
```

- `apply-current`：**底层** export → merge `current/`（并全量重建 normal/rework / previous_annotations）；SEG 若有 brush/polygon 会写出 `manual_masks/`
- `export-split`：**高级封装**，内部调用 apply-current，并返回 `normal/`、`rework/` 路径；分类规则（当前）：`should_rework_result = (not human_confirmed) or needs_rework or (not effective_payload)`
- **金标准**：仅人工 annotation；**禁止**将 LS `predictions` 当作模型推理回填金标准（`prediction_fallback` 已删除）。返工预填槽位若存在，语义为人工历史。
- `rework-import`：写出 `data/ls_import/<batch_id>/<task>/rework_tasks.json`（不覆盖首轮 `tasks.json`）。只读 `rework/previous_annotations/<task>.json`；无快照须先 `export-split`（或 `apply-current`）。可选 `--export` 已 deprecated，**不用于预填**。**不读** `prelabels/`。快照不含原图，导入仍依赖同批 `task_packages` 图像路径

### 8.1 返工预填 ≠ 模型预测

| 概念 | 含义 |
|------|------|
| `previous_annotations` | 上一轮**人工**结果快照（几何/文本）；业务权威来源 |
| LS 字段 `predictions` | 返工导入时**可能仍用该字段名**承载人工历史，供工作台预填；**不是** V1 意义上的模型输出 |
| model / prelabel prediction | V1 金标准路径**禁止**；首轮目标亦无 |

### 8.2 `export-split` / `apply-current` 与导出范围

二者均按 `image_id` **合并**写入 `current/`：导出里出现的样本覆盖；**current 已有且本轮未出现的样本保留**。任务包有、但 export 与 current 都没有的样本写入空结果并进入 `rework/`。export 含任务包没有的 id、或缺少任务包 `manifest.json`，整批失败。日常用 `export-split`；勿对同一 export 再跑另一条。

| 轮次 | 导出范围 | 说明 |
|------|----------|------|
| **全量轮**（首轮或刷新整批权威状态） | 建议从对应任务 LS 项目导出本批**全部**样本，再 `export-split` | 漏导出且尚未进入 current 的任务包样本会补为空结果并进 `rework/`，不会静默丢失 |
| **返工轮** | 可只导出返工子集再 `export-split` | 未导出、但 current 已有的 id 保留（含已 normal 样本），符合返工闭环 |

若只同步了子集，却希望尽快 `merge`，须保证 `current/` 中所有样本最终均被后续轮次刷新为不需返工（或本轮即为全量导出）。详见 [data_layout.md](data_layout.md) 中 `current/` 约定。

---

## 9. 常见问题

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 任务有、图不显示 | Local storage 根 ≠ `local_root`；或相对路径层级不对 | 核对 `--data-root` / `--local-root` 与 LS 本地根；确认 `d=` 下路径在磁盘上真实存在 |
| Windows 路径问题 | 混用反斜杠 | 本流水线生成的 `d=` 已用正斜杠；勿手改成 `\` |
| `ls-import` 失败 / 无图 | 缺 `task_packages` 或 Local storage 根不一致 | 确认任务包与 `--data-root` / LS 本地根 |
| 期望首轮无预填但仍看到几何/文本 | 打开的是**返工**包，或误用了 Legacy convert 产物 | 首轮用 `ls-import` 空任务；返工预填 = 人工历史，不是模型预测 |
| DET 转换失败 | 任务包缺图或图损坏 | 检查 `task_packages/.../images/{image_id}.jpg` |
| 导入报控件不匹配 | 项目 XML 与任务类型不一致 | SEG 项目只用 `seg.xml`，勿把 DET 的 `tasks.json` 导进 SEG 项目 |
| `merge` 仍报 needs_rework，但本轮以为已修完 | 只同步了部分导出，旧返工样本仍留在 `current/` | 全量导出再 `export-split`（或 `apply-current`）；或继续返工轮直到 `current/` 无返工残留 |
| 返工导入无图 / 路径失效 | 只拷了 `rework/`，缺少 `task_packages` 图像 | 同机保留或一并拷贝 `task_packages/<batch>/<task>/images/`；`previous_annotations` 不含原图 |

---

## 10. 相关文档与命令速查

```bash
# 生成导入 JSON
mma ls-import --batch <batch_id> --task {seg|det|cap} --data-root data

# 可选：Local storage 根与 data 不同时
mma ls-import --batch <batch_id> --task seg --data-root data --local-root D:\path\to\local_root

# 导出后：二选一（勿对同一 export 连跑）
# 推荐高级封装（内部 = apply-current + 返回 normal/rework 路径）
mma export-split --batch <batch_id> --task {seg|det|cap} --export <ls_export.json> --data-root data
# 或底层同步 current
mma apply-current --batch <batch_id> --task {seg|det|cap} --export <ls_export.json> --data-root data

# 生成返工再导入 tasks（不覆盖 tasks.json；须已有 previous_annotations）
mma rework-import --batch <batch_id> --task {seg|det|cap} --data-root data
```

- [data_layout.md](data_layout.md) — `ls_import` / `ls_export` / `task_packages`；Legacy `prelabels`
- [formats.md](formats.md) — **Legacy** 中间格式与控件名（非 V1 主流程必读）
- [deploy/v1/README.md](../deploy/v1/README.md) — 四角色入口（处理者 / SEG / DET / CAP 标注员）
- 仓库根 [README.md](../README.md) — V1 定位、安装与 CLI 总览
