# Changelog

## 2026-08-12

### Added

- T5.4：新增 `src/mma/merge/write_final.py`（`write_final_manifest` 原子写出 `final/<batch>/manifest.json`）
- T5.4：新增 `src/mma/merge/merge_to_final.py`（`merge_multitask` → processed 回填图文 → 写盘）
- `paths.py`：新增 `final_batch_dir`
- CLI：接线 `mma merge --batch [--data-root]`
- `merge/__init__.py` 导出 `merge_to_final` / `write_final_manifest` / `FINAL_MANIFEST_NAME`
- T5.3：`assert_no_missing_tasks`（合并缺任务阻断：缺 DET/CAP 即 `ValueError`；禁止静默缺字段；不写 `final/`）
- `merge/__init__.py` 导出 `assert_no_missing_tasks`

### Changed

- `merge_multitask` 改为调用 `assert_no_missing_tasks`（保留 `validate_ready` 后的二次校验）
- `docs/data_layout.md`：钉死 `final/<batch_id>/manifest.json` 对齐 `MergedMultitaskRecord`

### Tests

- 新增 `tests/test_merge_to_final.py`：写盘形状、成功回填、覆盖、未就绪保旧、缺任务/缺 processed 不写、非法 batch
- 扩展 `tests/test_cli.py`：`merge` 成功/失败（原 merge stub 改为 convert stub）
- 扩展 `tests/test_merge_multitask.py`：缺 DET/CAP（旁路门禁）、直接测 `assert_no_missing_tasks`、类型不符阻断

## 2026-08-11

### Added

- T5.2：新增 `src/mma/merge/merge_multitask.py`（`validate_ready` 后按 SEG 顺序合并为 `MergedMultitaskRecord`；缺任务防御报错；不写 `final/`）
- `merge/__init__.py` 导出 `merge_multitask`
- T5.1：新增 `src/mma/merge/validate_ready.py`（三路 `current/` 就绪校验：可加载、非空、无返工、全人工确认、`image_id` 集合一致）
- `src/mma/merge/__init__.py` 导出 `validate_ready`
- P4 CLI：接线 `mma rework-import --batch --task --export [--data-root] [--local-root]`
- 新增 `src/mma/importers/rework_import_from_export.py`（parse → split → extract raw → `build_rework_ls_tasks` → `rework_tasks.json`）
- `importers/__init__.py` 导出 `rework_import_from_export` / `REWORK_TASKS_JSON_NAME`
- P4 CLI：接线 `mma export-split --batch --task --export [--data-root]`
- 新增 `src/mma/exporters/export_split_from_export.py`（parse → split → 写 normal/rework `annotations.json`；空侧 `[]`）
- `paths.py`：新增 `results_normal_dir` / `results_rework_dir`
- `exporters/__init__.py` 导出 `export_split_from_export`
- P4 CLI：接线 `mma apply-current --batch --task --export [--data-root]`
- 新增 `src/mma/exporters/apply_current_from_export.py`（parse LS 导出 → 全量 `overwrite_current`；DET 从任务包图像读尺寸）
- `exporters/__init__.py` 导出 `apply_current_from_export`
- T4.1：新增 `src/mma/exporters/parse_ls_export.py`（解析 LS 导出 JSON → `TaskAnnotationResult`；支持 SEG/DET/CAP）
- T4.1：新增 `src/mma/exporters/__init__.py` 导出 `parse_ls_export` / `parse_ls_export_data`
- SEG：`SegAnnotation.mask_ref` 取自 `data.mask_ref`（不把 brush RLE 写入契约）
- DET：百分比框转像素，尺寸由显式参数 `image_metadata_by_id` 提供（不从导出 JSON 猜测）
- 勾选：`human_confirmed` 缺失/非法报错；`needs_rework` 缺失默认 `False`；同文件重复 `image_id` 严格失败
- T4.2：新增 `src/mma/exporters/split_by_rework.py`（按 `needs_rework` 拆成 normal / rework，保序；不做落盘与 ResultBundle）
- T4.2：`exporters/__init__.py` 导出 `split_by_rework`
- T4.3 / S2：新增 `src/mma/exporters/extract_ls_raw_results.py`（旁路 `image_id →` 原始 LS `result`；不改 T4.1 返回接口）
- T4.3：新增 `src/mma/importers/build_rework_tasks.py`（返工导入 tasks；`predictions` 仅用旁路 raw；图文来自 task_packages manifest；不预填双勾选）
- T4.4：新增 `src/mma/exporters/overwrite_current.py`（按 `image_id` 覆盖写入 `results/.../current/annotations.json`；空输入 no-op；保序+新 id 追加）
- `paths.py`：新增 `results_task_dir` / `results_current_dir`
-新增examples/scripts/run_p4_current_demo.py用来生成annotation.json为后续T4.5提供前提数据
- T4.5：新增 `src/mma/exporters/current_annotations.py`（`TaskAnnotationResult` ↔ JSON 公共序列化，兼容 T4.4 格式）
- T4.5：新增 `src/mma/exporters/load_current.py`（`load_current` / `load_current_annotations_file`；缺文件 `FileNotFoundError`）

### Changed

- `overwrite_current` 改为复用 `current_annotations` 读写，避免重复定义落盘格式
- README / `docs/labelstudio_usage.md`：补充 `apply-current` / `export-split` / `rework-import` 用法

### Tests

- 新增 `tests/test_merge_multitask.py`：成功顺序与载荷、未就绪失败、patch 后门禁缺任务、非法 batch、不写 final
- 新增 `tests/test_validate_ready.py`：通过、缺文件、空列表、返工残留、未确认、多违规汇总、id 集合不一致、非法 batch、不写 final
- 新增 `tests/test_rework_import_from_export.py`：混合 CAP、空返工、SEG/DET、异常、不覆盖 `tasks.json`
- 扩展 `tests/test_cli.py`：`rework-import` 参数/成功/失败
- 新增 `tests/test_export_split_from_export.py`：混合/全 normal/全 rework、DET、异常、不写 current/无 round
- 扩展 `tests/test_cli.py`：`export-split` 成功/失败
- 新增 `tests/test_apply_current_from_export.py`：CAP/SEG 写入、DET 尺寸、缺图失败、覆盖、空导出 no-op、不写 normal/rework
- 扩展 `tests/test_cli.py`：`apply-current` 参数/成功/失败
- 新增 `tests/test_parse_ls_export.py`：三任务解析、勾选默认/非法、重复 ID、DET metadata、真实 demo 导出冒烟
- 新增 `tests/test_split_by_rework.py`：空输入、全正常、全返工、混合保序、非法类型
- 新增 `tests/test_extract_ls_raw_results.py`：旁路提取、深拷贝、取消标注跳过、重复 ID
- 新增 `tests/test_build_rework_tasks.py`：SEG RLE 回放、剥离勾选、CAP/DET 用 raw、缺旁路失败
- 新增 `tests/test_overwrite_current.py`：首次写入、同 id 覆盖勾选、子集合并保序、空输入 no-op、三任务形状
- 新增 `tests/test_load_current.py`：往返加载、缺文件、非法结构、重复 ID、task_type 不一致、可选 demo 冒烟

## 2026-08-10

### Added

- T3.5：新增 `docs/labelstudio_usage.md`（本地 LS：Local Files、三任务 XML、导入 `tasks.json`、标注勾选与导出落盘建议）
- T3.4：新增 `src/mma/importers/build_ls_tasks.py`（读 prelabels + task_packages 图像 → `ls_import/.../tasks.json`；`/data/local-files/?d=` URL；SEG 默认 `mask_root`）
- T3.4：接线 `mma ls-import --batch --task [--data-root] [--local-root]`；`paths.py` 增加 `prelabels_task_dir` / `ls_import_task_dir`
- T3.3：新增 CAP Label Studio 工作台配置 `src/mma/labelstudio/configs/cap.xml`（原图 + 可编辑 TextArea `cap_text`、只读原文与 ID、双 Choices）
- T3.3：新增 `mma.labelstudio.cap_config_path` / `load_cap_config_text`
- T3.2：新增 DET Label Studio 工作台配置 `src/mma/labelstudio/configs/det.xml`（原图 + RectangleLabels `det_bbox`/`object`、原文与 ID 只读、双 Choices；无 mask 侧栏）
- T3.2：新增 `mma.labelstudio.det_config_path` / `load_det_config_text`
- T3.1b：新增 `src/mma/converters/seg_brush.py`（Pillow 读 mask、8 连通拆分、LS 兼容 brush RLE）；`item_to_ls_task` / `document_to_ls_tasks` 支持可选 `mask_root`
- 依赖：`Pillow>=10.0.0`（`requirements.txt` / `pyproject.toml`）
- T3.1：新增 SEG Label Studio 工作台配置 `src/mma/labelstudio/configs/seg.xml`（原图 + BrushLabels `seg_mask`/`lesion`、原文与 ID 只读、双 Choices；`mask_ref` 仅路径追溯）
- T3.1：新增 `mma.labelstudio.seg_config_path` / `load_seg_config_text`；`pyproject.toml` 打包 `*.xml`
- T2.1：新增预标注统一中间格式层（`src/mma/formats/`）：`PrelabelDocument` / `PrelabelItem`、SEG/DET/CAP 载荷、`PrelabelBBox`（像素坐标）及校验/解析 API
- 包内样例 JSON：`src/mma/formats/{seg,det,cap}.json`；测试落盘样例：`examples/prelabels/demo_batch/{seg,det,cap}/prelabels.json`
- 文档：`docs/formats.md`（关联键 `image_id`；运行时主文件名 `prelabels.json`）
- T2.2：新增 `src/mma/converters/to_labelstudio.py`（`item_to_ls_task` / `document_to_ls_tasks`）；DET 经调用方 `ImageMetadata` 做像素→百分比；SEG 仅 `data.mask_ref` + 空 `result` 预留
- T2.3：新增 `src/mma/adapters/`（`AdapterContext`、三类 Base/`NotImplementedError`、Example 适配器）；raw 仅 Mapping，信封由调用方注入
- T2.4：新增 `examples/adapter_raw/` 假算法 raw + `contexts.json`；`examples/scripts/run_p2_demo.py`；`tests/test_p2_pipeline.py` 端到端链路

### Changed

- `docs/data_layout.md`：补充 `prelabels.json` 与中间格式约定
- `common/models.py`：仅注释指向 formats 层（字段与语义不变）
- `docs/formats.md` / `README.md` / `examples/README.md`：补充 T2.2–T2.4 说明（CLI `convert` 仍未接线）
- `docs/formats.md` / `README.md`：补充 T3.1 SEG 工作台控制名对齐说明（不含 T3.1b 叠图预填）
- `docs/formats.md` / `README.md`：补充 T3.1b `mask_root` 叠图预填与连通域规则
- `docs/formats.md` / `README.md`：补充 T3.2 DET 工作台控制名对齐说明
- `docs/formats.md` / `README.md`：补充 T3.3 CAP 工作台控制名对齐说明
- `docs/data_layout.md` / `docs/formats.md` / `README.md`：补充 T3.4 local-files 与 `ls-import` 约定

### Tests

- 新增 `tests/test_docs_labelstudio_usage.py`：操作说明文档存在性与关键主题标记
- 新增 `tests/test_build_ls_tasks.py`：三任务构建、local-files URL、缺文件失败、不复制图像、CLI 成功/失败
- 新增 `tests/test_labelstudio_cap_config.py`：CAP XML 打包可读、TextArea `cap_text`、原文只读分离、禁止 Brush/Rectangle/`$mask_ref`、双 Choices 契约
- 新增 `tests/test_labelstudio_det_config.py`：DET XML 打包可读、Rectangle 绑定、禁止 Brush/`$mask_ref`、只读字段与双 Choices 契约
- 新增 `tests/test_seg_brush.py`：mask 读取、8 连通、RLE、缺文件/尺寸不一致、converter 接线
- 扩展 `tests/test_convert.py`：`mask_root` 下 SEG 发射 brush results
- 新增 `tests/test_labelstudio_seg_config.py`：SEG XML 打包可读、结构、Brush 绑定、禁止 `$mask_ref` 作主图、只读字段与双 Choices 契约
- 新增 `tests/test_formats.py`：样例加载、往返序列化、任务/载荷匹配、bbox/空框/重复 `image_id` 等边界与异常用例
- 新增 `tests/test_convert.py`：SEG/DET/CAP 转换、百分比换算、缺 metadata、空框与 `image_path=None` 等
- 新增 `tests/test_adapters.py`：Base `NotImplementedError`、Example 映射、信封注入、与 T2.2 链路冒烟
- 新增 `tests/test_p2_pipeline.py`：raw → ExampleAdapter → PrelabelDocument → LS converter 三类任务

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
- T1.3：新增 `common/paths.py`、`preprocess/build_processed.py`；写出 `processed/<batch_id>/manifest.json`（引用原图绝对路径，不复制图像）；接线 `mma preprocess`（可选 `--data-root`）
- T1.4：新增 `packaging/split_task_packages.py`；将 processed 全量样本复制到 `task_packages/<batch_id>/{seg,det,cap}/images/`（文件名 `{image_id}{ext}`）；不写任务包 manifest、不赋 `package_id`、不接线 CLI
- T1.5：新增 `generate_package_id`（`{batch_id}__{seg|det|cap}`）、`packaging/build_task_packages.py`；写出三类任务包 `manifest.json`；接线 `mma package`（可选 `--data-root`）

### Changed

- 明确 `processed/` 以标准化索引与图文绑定为主；T1.3 采用引用原图、不复制图像策略
- 任务包阶段复制图像并写入含 `package_id` 的正式 `manifest.json`（T1.5）

### Tests

- 本任务为工程脚手架，无业务逻辑；以 `pip install -e .` 与 `import mma` 作为安装验收
- 新增 `tests/test_models.py`：覆盖契约构造、任务-标注匹配、结果包一致性、不可变与覆盖语义
- T0.3 为目录规范文档，无新增可执行业务逻辑测试
- 新增 `tests/test_cli.py`：子命令注册、帮助、参数校验与 stub 退出码
- 新增 `tests/test_preprocess.py`：T1.1 正常配对与整批失败边界用例
- 扩展 `tests/test_preprocess.py`：T1.2 赋 ID、确定性、空输入与重复源名、多批次前缀隔离等用例
- 扩展 `tests/test_preprocess.py` / `tests/test_cli.py`：T1.3 落盘、覆盖、非法 batch_id、端到端与 CLI preprocess
- 新增 `tests/test_packaging.py`：T1.4 三类全量复制、相对路径样本、缺图/缺 processed 失败等
- 扩展 `tests/test_packaging.py` / `tests/test_cli.py`：T1.5 package_id、manifest、CLI package 成功/失败
