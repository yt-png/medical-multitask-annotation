# 预标注统一中间格式说明（T2.1）

本文档定义 SEG / DET / CAP 进入 Label Studio 转换之前的**统一中间格式**。  
实现代码：`src/mma/formats/intermediate.py`；包内样例：`src/mma/formats/{seg,det,cap}.json`。

相关落盘见 `docs/data_layout.md`。业务结果契约仍见 `src/mma/common/models.py`（本格式层不修改其字段与语义）。

---

## 1. 目标与边界

| 包含 | 不包含 |
|---|---|
| 三类任务统一的 JSON 中间格式 | 算法/大模型原始输出 schema |
| Python 类型与校验 | Label Studio import JSON（T2.2） |
| 样例与测试用落盘约定 | 真实算法调用、工作台 XML |

数据流位置：

```text
算法原始输出  --(T2.3 adapter)-->  统一中间格式  --(T2.2)-->  LS import JSON
                                      ↑
                                   本文档 / T2.1
```

---

## 2. 落盘约定

| 用途 | 路径 |
|---|---|
| 运行时（gitignore 的 `data/`） | `data/prelabels/<batch_id>/{seg,det,cap}/prelabels.json` |
| 测试 / 仓库内样例 | `examples/prelabels/<batch_id>/{seg,det,cap}/prelabels.json` |
| 包内 schema 样例 | `src/mma/formats/{seg,det,cap}.json`（内容与文档样例同构） |

**主文件名固定为 `prelabels.json`。**

SEG 的 mask 文件建议放在同任务目录下，例如：

```text
data/prelabels/<batch_id>/seg/
├── prelabels.json
└── masks/
    └── <image_id>.png
```

`payload.mask_ref` 为相对于**该任务 prelabels 目录根**（含 `prelabels.json` 的目录）的相对路径，例如 `masks/<image_id>.png`。

---

## 3. 关联键与路径语义

1. **`image_id` 是唯一关联键**：与任务包样本、后续 LS 任务、结果合并均以 `image_id` 对齐。  
2. **`image_path` 仅为可选辅助定位字段**：可省略；若出现必须为非空字符串。  
3. **不强制绑定 `task_packages` 路径**：中间格式不要求 `image_path` 指向任务包内文件；转换阶段（T2.2/T3）再按 `image_id` 解析真实图像位置。

同一 `prelabels.json`（同一 `PrelabelDocument`）内 **`image_id` 不得重复**。

---

## 4. 文档结构（`PrelabelDocument`）

```json
{
  "schema_version": "1.0",
  "batch_id": "<batch_id>",
  "package_id": "<batch_id>__seg|det|cap",
  "task_type": "SEG | DET | CAP",
  "items": [ /* PrelabelItem... */ ]
}
```

| 字段 | 要求 |
|---|---|
| `schema_version` | 非空；当前固定 `"1.0"` |
| `batch_id` | 非空 |
| `package_id` | 非空（建议与任务包 ID 一致，校验只要求非空） |
| `task_type` | `SEG` / `DET` / `CAP` |
| `items` | 非空数组；每条见下节 |

每条 `items[]` 的 `schema_version` / `batch_id` / `package_id` / `task_type` 必须与文档级字段一致。

---

## 5. 条目结构（`PrelabelItem`）

```json
{
  "schema_version": "1.0",
  "batch_id": "...",
  "package_id": "...",
  "task_type": "SEG",
  "image_id": "...",
  "diagnosis_text": "...",
  "image_path": "optional/auxiliary/path.jpg",
  "payload": { }
}
```

| 字段 | 要求 |
|---|---|
| `image_id` | 非空；文档内唯一 |
| `diagnosis_text` | 原始诊断文本（非空）；人工工作台只读展示来源 |
| `image_path` | 可选；辅助定位，不作为关联键 |
| `payload` | 与 `task_type` 匹配的任务载荷 |

---

## 6. 任务载荷

### 6.1 SEG

```json
{ "mask_ref": "masks/<image_id>.png" }
```

- **仅文件引用**，不支持内联 mask / RLE 等编码。  
- `mask_ref` 必须为非空字符串。

### 6.2 DET

```json
{
  "bboxes": [
    { "x": 120.0, "y": 80.5, "width": 64.0, "height": 48.0 }
  ]
}
```

- 坐标系：**像素**；原点为图像左上角。  
- `x`、`y` ≥ 0；`width`、`height` > 0。  
- `bboxes` 可为**空数组**（表示无检测框）。  
- 类型名：`PrelabelBBox`（格式层自有，**不修改** `common.models.BBox`）。

### 6.3 CAP

```json
{ "caption": "模型生成的预标注文本" }
```

- `caption`：预标注生成文本（非空）。  
- 与条目上的 `diagnosis_text`（原始诊断）语义分离，二者都要保留。

---

## 7. 与业务模型的关系

| 格式层 | common.models（业务） |
|---|---|
| `PrelabelBBox` | `BBox`（坐标系未在业务层钉死；预标注像素约定只在 formats） |
| `SegPrelabelPayload` 等 | `SegAnnotation` / `DetAnnotation` / `CapAnnotation`（人工确认后结果载荷） |
| `PrelabelItem` / `PrelabelDocument` | 无对等物；结果阶段用 `TaskAnnotationResult` / `ResultBundle` |

预标注阶段**没有** `human_confirmed` / `needs_rework`；勾选状态在 Label Studio 导出后进入结果契约。

---

## 8. Python API

```python
from mma.formats import (
    load_prelabel_document,
    prelabel_document_from_dict,
    validate_prelabel_document,
)

doc = load_prelabel_document("examples/prelabels/demo_batch/seg/prelabels.json")
```

校验失败时抛出 `ValueError`；在可得时尽量在消息中带上 `image_id`。

---

## 9. Label Studio import JSON（T2.2）

实现：`src/mma/converters/to_labelstudio.py`。  
公开 API：`item_to_ls_task` / `document_to_ls_tasks`（**未**接线 `mma convert`）。

### 9.1 共性

| 字段 | 说明 |
|---|---|
| 顶层 `id` | 等于 `image_id`，仅为 LS 任务辅助标识 |
| `data.image_id` | **系统关联主键** |
| `data.image` | 透传 `PrelabelItem.image_path`（可为 `null`）；不复制、不重写路径 |
| `data.diagnosis_text` | 原始诊断文本 |
| `predictions` | 始终存在；`model_version` 为 `mma-prelabel-1.0` |
| 控制名 | 集中在 `DEFAULT_LS_RESULT_SPECS`；T3 XML 应对齐后可统一改 |

### 9.2 分任务

| 任务 | 转换要点 |
|---|---|
| SEG | 无 `mask_root` 时：`data.mask_ref` + `predictions[].result=[]`（兼容 T2.2）。传入 `mask_root`（T3.1b）时：读取相对该根的 `mask_ref`，按 8 连通拆分前景，每块一条 `brushlabels` RLE（`format=rle`，标签 `lesion`）；缺文件严格失败。 |
| DET | 调用方传入 `ImageMetadata(width, height)`；像素框转为 LS **百分比** `rectanglelabels`；空框 → `result: []` |
| CAP | 原文在 `data.diagnosis_text`；预标注在 textarea `value.text` |

```python
from mma.converters import ImageMetadata, document_to_ls_tasks
from mma.formats import load_prelabel_document

doc = load_prelabel_document("examples/prelabels/demo_batch/det/prelabels.json")
tasks = document_to_ls_tasks(
    doc,
    image_metadata_by_id={
        item.image_id: ImageMetadata(width=640, height=480)
        for item in doc.items
    },
)
```

SEG 叠图预填示例：

```python
from pathlib import Path
from mma.converters import document_to_ls_tasks
from mma.formats import load_prelabel_document

doc = load_prelabel_document("examples/prelabels/demo_batch/seg/prelabels.json")
# mask_root = 含 masks/ 与 prelabels.json 的任务 prelabels 目录
tasks = document_to_ls_tasks(doc, mask_root=Path("data/prelabels/demo_batch/seg"))
```

本地导入落盘（T3.4）：`mma.importers.build_ls_import_tasks` / `mma ls-import` 写出 `data/ls_import/<batch>/<task>/tasks.json`，并将 `data.image` 重写为 `/data/local-files/?d=...`（相对 `local_root`，默认等于 `data_root`）。详见 `docs/data_layout.md` §4.5。

---

## 10. 算法原始输出适配器（T2.3）

实现：`src/mma/adapters/`（`AdapterContext` + 三类 Base/Example）。

| 角色 | 说明 |
|---|---|
| Base（`*PrelabelAdapter`） | `adapt_payload` 默认 `NotImplementedError`，约束未来真实算法适配器 |
| Example（`Example*Adapter`） | 假 `Mapping` raw → 合法 Payload；可 `adapt_item` 组 `PrelabelItem` |
| `AdapterContext` | 信封字段由**调用方注入**（`batch_id` / `package_id` / `image_id` / `diagnosis_text` 等） |

约定：

- raw **仅** `Mapping`（调用方若有文件需先自行读成 dict）。  
- 主输出为 **Payload**；`adapt_item` 组装单条 `PrelabelItem`；**不**在 adapter 内生成 `PrelabelDocument`。  
- **不**实现真实 SEG/DET/CAP 算法或大模型调用。

```python
from mma.adapters import AdapterContext, ExampleSegAdapter
from mma.common.models import TaskType

ctx = AdapterContext(
    batch_id="demo_batch",
    package_id="demo_batch__seg",
    task_type=TaskType.SEG,
    image_id="demo_batch__000001",
    diagnosis_text="original diagnosis",
)
item = ExampleSegAdapter().adapt_item(
    {"mask_ref": "masks/demo_batch__000001.png"},
    context=ctx,
)
```

---

## 11. SEG Labeling Config（T3.1）

配置文件：`src/mma/labelstudio/configs/seg.xml`（包内可通过 `mma.labelstudio.seg_config_path` / `load_seg_config_text` 读取）。

| 工作台控件 | 对齐约定 |
|---|---|
| `Image name="image"` / `$image` | 与 T2.2 `data.image`、`DEFAULT_LS_RESULT_SPECS[SEG].to_name` |
| `BrushLabels name="seg_mask"` | 与 `from_name=seg_mask`；标签 `lesion`；叠在原图上编辑 |
| `$diagnosis_text` / `$image_id` 等只读 Text | 与转换 `data.*` 字段名一致；`$mask_ref` 仅路径追溯，**不是**预标注主展示 |
| `Choices name="human_confirmed"` / `needs_rework` | value 为 `yes`/`no`；对齐契约 `human_confirmed` / `needs_rework` |

预标注 brush 叠图写入 `predictions`（含连通域拆分）属 **T3.1b**：调用 `item_to_ls_task` / `document_to_ls_tasks` 时传入 `mask_root`；实现见 `mma.converters.seg_brush`。

---

## 12. DET Labeling Config（T3.2）

配置文件：`src/mma/labelstudio/configs/det.xml`（包内可通过 `mma.labelstudio.det_config_path` / `load_det_config_text` 读取）。

| 工作台控件 | 对齐约定 |
|---|---|
| `Image name="image"` / `$image` | 与 T2.2 `data.image`、`DEFAULT_LS_RESULT_SPECS[DET].to_name` |
| `RectangleLabels name="det_bbox"` | 与 `from_name=det_bbox`；标签 `object`；多框叠在原图上编辑 |
| `$diagnosis_text` / `$image_id` / `$package_id` 只读 Text | 与转换 `data.*` 一致；**无** `$mask_ref` |
| `Choices name="human_confirmed"` / `needs_rework` | 与 SEG 相同：`yes`/`no`；对齐契约字段 |

DET 多框预填已由 T2.2 `bboxes[]` → `predictions` 完成，本任务仅定工作台 XML。

---

## 13. CAP Labeling Config（T3.3）

配置文件：`src/mma/labelstudio/configs/cap.xml`（包内可通过 `mma.labelstudio.cap_config_path` / `load_cap_config_text` 读取）。

| 工作台控件 | 对齐约定 |
|---|---|
| `Image name="image"` / `$image` | 与 T2.2 `data.image`、`DEFAULT_LS_RESULT_SPECS[CAP].to_name` |
| `TextArea name="cap_text"` | 与 `from_name=cap_text`；可编辑预标注文本；由 T2.2 `predictions` 预填 |
| `$diagnosis_text` 只读 Text | 原始诊断对照；**不可**用 TextArea 编辑原文 |
| `$image_id` / `$package_id` 只读 Text | 追溯；**无** `$mask_ref` |
| `Choices name="human_confirmed"` / `needs_rework` | 与 SEG/DET 相同：`yes`/`no` |

---

## 14. 版本

当前中间格式 `schema_version`：`1.0`。后续不兼容变更应递增版本并在本文档说明。
