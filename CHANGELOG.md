# Changelog

## 2026-08-09

### Added

- 初始化可安装 Python 工程（`pyproject.toml`、`src/mma` 包骨架）
- 添加 `README.md`、`requirements.txt`（暂无第三方依赖）、`.gitignore`
- 定义核心数据契约（`src/mma/common/models.py`）：任务类型、图像/样本/任务包、标注载荷、结果包、合并记录
- 约定批次/任务包/结果包落盘规范（`docs/data_layout.md`）
- 统一 CLI 入口（`src/mma/cli.py`、`python -m mma`、控制台脚本 `mma`）：八个子命令骨架，业务暂为 stub
- T1.1：新增 `ImageTextPair`（无 `image_id`）；`common/io.py` 列目录与读 Excel；`preprocess/pair_images_excel.py` 图文一一配对 API
- 依赖 `openpyxl`；`examples/raw/demo_batch` 假数据样例
- T1.2：新增 `common/ids.py`（确定性 `image_id`：`{batch_id}__{seq:06d}`）；`preprocess/assign_image_ids.py` 将配对结果绑定为 `ImageRecord`（内存清单，不落盘）

### Changed

- 明确 `processed/` 以标准化索引与图文绑定为主；是否复制图像文件留给 P1 按规模与部署决定

### Tests

- 本任务为工程脚手架，无业务逻辑；以 `pip install -e .` 与 `import mma` 作为安装验收
- 新增 `tests/test_models.py`：覆盖契约构造、任务-标注匹配、结果包一致性、不可变与覆盖语义
- T0.3 为目录规范文档，无新增可执行业务逻辑测试
- 新增 `tests/test_cli.py`：子命令注册、帮助、参数校验与 stub 退出码
- 新增 `tests/test_preprocess.py`：T1.1 正常配对与整批失败边界用例
- 扩展 `tests/test_preprocess.py`：T1.2 赋 ID、确定性、空输入与重复源名、多批次前缀隔离等用例
