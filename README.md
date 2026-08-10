# 医学图像多任务标注数据流（mma）

本地化、可脚本化的医学图像多任务标注数据流工程：对同一批医学图像完成 SEG / DET / CAP 三类标注链路的数据预处理、任务包拆分、预标注格式统一、Label Studio 导入导出、返工覆盖与最终合并。

协作分发与回传通过网盘人工完成；本仓库不包含业务服务端，也不在现阶段实现具体预标注算法或大模型调用。

## 环境要求

- Python 3.12+

## 安装

在项目根目录创建虚拟环境并安装本包（可编辑模式）：

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
# source .venv/bin/activate

pip install -e .
```

运行时依赖见 `requirements.txt`（当前含 `openpyxl`，用于读取诊断 Excel）。

## CLI

安装后可使用：

```bash
mma -h
python -m mma -h
```

已注册子命令：`preprocess`、`package` 已接线；其余仍为骨架 stub：

`preprocess` · `package` · `convert` · `ls-import` · `export-split` · `rework-import` · `apply-current` · `merge`

预处理与任务包示例：

```bash
mma preprocess --batch demo_batch --images examples/raw/demo_batch/images --excel examples/raw/demo_batch/diagnoses.xlsx --data-root data
mma package --batch demo_batch --data-root data
```

- `preprocess`：写出 `data/processed/<batch_id>/manifest.json`（引用原图，不复制）
- `package`：复制三类全量图像并写出各任务包 `manifest.json`（含 `package_id`）

预标注 → Label Studio import（T2.2，Python API，CLI `convert` 仍为 stub）：

```python
from mma.converters import ImageMetadata, document_to_ls_tasks
from mma.formats import load_prelabel_document

doc = load_prelabel_document("examples/prelabels/demo_batch/seg/prelabels.json")
tasks = document_to_ls_tasks(doc)  # DET 需额外传入 image_metadata_by_id
```

P2 端到端演示（T2.4，假 raw → Example adapter → LS JSON）：

```bash
python examples/scripts/run_p2_demo.py
```

说明见 [examples/README.md](examples/README.md)。

## 当前进度

- 已完成：P0 / T0.1–T0.4 工程骨架、契约、落盘规范、CLI 入口
- 已完成：P1 / T1.1–T1.5 预处理与三类任务包（配对、`image_id`、processed 落盘、拆包图像、`package_id`+manifest、CLI）
- 已完成：P2 / T2.1–T2.4 预标注统一中间格式、LS 转换 API、适配器接口/示例、假 raw 样例与端到端演示脚本/测试（不含真实算法与 CLI convert）
- 已完成：T3.1 SEG Label Studio 工作台 XML（`src/mma/labelstudio/configs/seg.xml`）；叠图预填（T3.1b）与 DET/CAP 工作台尚未做
- 后续：T3.1b / T3.2–T3.5 等（见 `.cursor/rules/Development Tasks.md`）

## 文档

- 数据目录与落盘约定：[docs/data_layout.md](docs/data_layout.md)
- 预标注统一中间格式与 SEG 工作台控制名对齐：[docs/formats.md](docs/formats.md)

## 开发说明

请遵循项目规则与需求文档（`.cursor/rules/`）。功能分支开发；提交前由开发者本地运行检查后再 `git commit`。
