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

已注册子命令：`preprocess` 已接线；其余仍为骨架 stub：

`preprocess` · `package` · `convert` · `ls-import` · `export-split` · `rework-import` · `apply-current` · `merge`

预处理示例：

```bash
mma preprocess --batch demo_batch --images examples/raw/demo_batch/images --excel examples/raw/demo_batch/diagnoses.xlsx --data-root data
```

成功时 stdout 打印 `data/processed/<batch_id>/` 路径；不复制图像，仅写 `manifest.json`（绝对路径引用原图）。

## 当前进度

- 已完成：P0 / T0.1 工程初始化（可安装本地工程）
- 已完成：P0 / T0.2 核心数据契约（`src/mma/common/models.py`）
- 已完成：P0 / T0.3 落盘规范（`docs/data_layout.md`）
- 已完成：P0 / T0.4 统一 CLI 入口（骨架 / stub）
- 已完成：P1 / T1.1 图文配对 API（`mma.preprocess.pair_images_with_excel`）
- 已完成：P1 / T1.2 确定性 `image_id` 绑定（`mma.preprocess.assign_image_ids`）
- 已完成：P1 / T1.3 标准化 `processed/<batch_id>/` 落盘与 `mma preprocess` 接线
- 已完成：P1 / T1.4 三类全量任务包图像拆分（`mma.packaging.split_task_packages`；CLI `package` 仍 stub，manifest/`package_id` 留待 T1.5）
- 后续：P1 / T1.5（任务包 `package_id` 与 `manifest.json`，见 `.cursor/rules/Development Tasks.md`）

## 文档

- 数据目录与落盘约定：[docs/data_layout.md](docs/data_layout.md)

## 开发说明

请遵循项目规则与需求文档（`.cursor/rules/`）。功能分支开发；提交前由开发者本地运行检查后再 `git commit`。
