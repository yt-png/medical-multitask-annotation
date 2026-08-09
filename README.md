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

当前阶段无第三方运行时依赖；见 `requirements.txt`。

## 当前进度

- 已完成：P0 / T0.1 工程初始化（可安装本地工程）
- 已完成：P0 / T0.2 核心数据契约（`src/mma/common/models.py`）
- 后续：目录规范、CLI 与业务模块（见 `.cursor/rules/Development Tasks.md`）

## 开发说明

请遵循项目规则与需求文档（`.cursor/rules/`）。功能分支开发；提交前由开发者本地运行检查后再 `git commit`。
