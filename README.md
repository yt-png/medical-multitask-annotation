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

已注册子命令（T0.4 仅为入口骨架，业务逻辑后续阶段实现）：

`preprocess` · `package` · `convert` · `ls-import` · `export-split` · `rework-import` · `apply-current` · `merge`

## 当前进度

- 已完成：P0 / T0.1 工程初始化（可安装本地工程）
- 已完成：P0 / T0.2 核心数据契约（`src/mma/common/models.py`）
- 已完成：P0 / T0.3 落盘规范（`docs/data_layout.md`）
- 已完成：P0 / T0.4 统一 CLI 入口（骨架 / stub）
- 已完成：P1 / T1.1 图文配对 API（`mma.preprocess.pair_images_with_excel`；CLI `preprocess` 仍为 stub，接线留待 T1.3）
- 后续：P1 / T1.2+（`image_id`、processed 落盘、任务包等，见 `.cursor/rules/Development Tasks.md`）

## 文档

- 数据目录与落盘约定：[docs/data_layout.md](docs/data_layout.md)

## 开发说明

请遵循项目规则与需求文档（`.cursor/rules/`）。功能分支开发；提交前由开发者本地运行检查后再 `git commit`。
