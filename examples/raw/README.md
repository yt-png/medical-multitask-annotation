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

### 配对 API

```python
from mma.preprocess import pair_images_with_excel

pairs = pair_images_with_excel(
    "examples/raw/demo_batch/images",
    "examples/raw/demo_batch/diagnoses.xlsx",
    batch_id="demo_batch",
)
```

### 生成 processed、任务包与 LS 空任务导入

```bash
mma preprocess --batch demo_batch --images examples/raw/demo_batch/images --excel examples/raw/demo_batch/diagnoses.xlsx --data-root data
mma package --batch demo_batch --data-root data
mma ls-import --batch demo_batch --task seg --data-root data
mma ls-import --batch demo_batch --task det --data-root data
mma ls-import --batch demo_batch --task cap --data-root data
```

- processed：`data/processed/demo_batch/manifest.json`（不复制图像）
- 任务包：`data/task_packages/demo_batch/{seg,det,cap}/`（含 `images/` 与 `manifest.json`）
- LS 导入：`data/ls_import/demo_batch/{seg,det,cap}/tasks.json`（空任务；**task_packages 是 Label Studio 导入入口**，不依赖 `prelabels/`）
