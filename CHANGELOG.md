# Changelog

## 2026-08-09

### Added

- 初始化可安装 Python 工程（`pyproject.toml`、`src/mma` 包骨架）
- 添加 `README.md`、`requirements.txt`（暂无第三方依赖）、`.gitignore`
- 定义核心数据契约（`src/mma/common/models.py`）：任务类型、图像/样本/任务包、标注载荷、结果包、合并记录

### Tests

- 本任务为工程脚手架，无业务逻辑；以 `pip install -e .` 与 `import mma` 作为安装验收
- 新增 `tests/test_models.py`：覆盖契约构造、任务-标注匹配、结果包一致性、不可变与覆盖语义
