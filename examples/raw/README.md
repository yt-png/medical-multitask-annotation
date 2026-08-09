# 假数据样例（P1 开发用）

本目录存放合成假数据，用于本地开发与测试。不含真实医学影像或患者信息。

## `demo_batch/`

| 路径 | 说明 |
|---|---|
| `images/` | 若干 `.jpg` 假图 |
| `diagnoses.xlsx` | 诊断文本表（第一个 sheet） |

Excel 固定列：

- `image_name`：完整文件名（如 `img_001.jpg`）
- `diagnosis_text`：非空诊断文本

配对 API（T1.1，CLI 尚未接线）：

```python
from mma.preprocess import pair_images_with_excel

pairs = pair_images_with_excel(
    "examples/raw/demo_batch/images",
    "examples/raw/demo_batch/diagnoses.xlsx",
    batch_id="demo_batch",
)
```
