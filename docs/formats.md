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

## 9. 版本

当前 `schema_version`：`1.0`。后续不兼容变更应递增版本并在本文档说明。
