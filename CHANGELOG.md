# Changelog

## 2026-08-15

### Changed

- final 数据集改为完全自包含：`final/<batch>/{images,masks,manifest.json}`；merge 复制原图为 `images/{image_id}.jpg`（源 jpg/jpeg 统一目标名），SEG mask 物化到 `masks/{image_id}.png`；manifest 仅存相对路径，禁止绝对路径与 `final_assets/` / `manual_masks/` / `prelabels/` 根
- `paths.final_masks_dir` / `final_images_dir`；`final_assets_masks_dir` 保留为 `final_masks_dir` 别名

### Tests

- `tests/test_merge_to_final.py`：相对路径断言；`.jpeg` 源 → `.jpg` 目标名；自包含用例（删除 raw/processed/prelabels/manual_masks 后 manifest 路径仍有效）

### Docs

- `docs/data_layout.md` / `README.md`：同步 final 自包含布局

### Fixed

- `parse_ls_export`：以 `resolve_effective_result` 为唯一 human/prediction 决策入口；CAP/DET/SEG parser 只消费 `EffectiveLsResult`，不再自行读取 `task["predictions"]` / `annotation["prediction"]`
- `resolve_effective_result`：prediction 回退改为倒序查找**第一个含当前任务控件**（`det_bbox` / `cap_text` / `seg_mask`）的版本，禁止多版本 concat
- CAP Accept 后清空（`annotation.prediction` 有值且无 `cap_text`）不再错误回退 prediction 文本

### Tests

- `tests/test_parse_ls_export.py`：CAP confirm-only 回退 prediction；CAP human-cleared 为空 caption
- `tests/test_effective_result.py`：latest 含任务控件的 prediction；parse confirm-only / human-cleared DET

### Fixed

- DET 导出解析：`predictions` 按版本历史回退，仅取**最后一个**含有效 `det_bbox` 的 prediction；禁止把多个 prediction 的框 concat（避免重复框）。新增 `_get_latest_det_prediction_boxes`；人工框优先与 Accept 后清空为空框的逻辑不变

### Tests

- `tests/test_parse_ls_export.py`：`test_parse_det_falls_back_to_latest_prediction_only`（prediction A + B、无人工框 → 仅 B）

### Fixed

- `read_diagnosis_excel`：显式校验诊断表后缀仅为 `.xlsx`（大小写不敏感），非 xlsx 在 openpyxl 前以统一 `ValueError` 失败

### Tests

- `tests/test_preprocess.py`：拒绝 `.xls`；接受 `.XLSX` 大小写变体

### Changed

- 将 `load_processed_items` 从 `packaging/split_task_packages` 下沉到 `preprocess/load_processed.py`；`merge` / `packaging` 改为从 preprocess 导入，解除 merge → packaging 反向依赖；`mma.packaging` 不再导出该符号

### Tests

- `tests/test_preprocess.py`：迁入缺 manifest 用例；新增 load 往返用例
- `tests/test_packaging.py`：改为从 preprocess 导入 `load_processed_items`

### Fixed

- `package` / `split_task_packages`：重跑时按 processed 期望文件名差集清理各任务 `images/` 清单外文件（含旧后缀与杂文件）；`images/` 下出现子目录则失败

### Tests

- `tests/test_packaging.py`：缩样孤儿删除、扩展名变更、杂文件清理、子目录报错、`build_task_packages` 端到端孤儿清理

### Docs

- `docs/data_layout.md` §4.3：补充 `mma package` 重跑 `images/` 对齐语义

### Added

- `parse_export_round_from_path`（`common/paths.py`）：从 export 父目录解析 `round_001` → `1`；非轮次目录返回 `None`
- `parse_ls_export` / `parse_ls_export_data` 支持可选参数 `export_round`，写入 `TaskAnnotationResult.export_round`（追溯字段，不改分类/合并）
- `apply-current` / `export-split`（经 `apply_current_from_export`）自动从 `--export` 路径填充 `export_round` 并落入 `current/annotations.json`

### Tests

- 新增 `tests/test_parse_export_round.py`：路径解析、`parse_ls_export_data` 含 `export_round`、文件路径接线
- `tests/test_apply_current_from_export.py`：`round_003/export.json` 写入 `export_round=3`；无 round 目录仍为 `null`

### Docs

- `README.md`：示例改用 `round_001/export.json`，说明 `export_round` 追溯语义
- `docs/data_layout.md`：同步「已从轮次目录填充」说明

## 2026-08-14

### Changed

- `apply-current`（SEG）：refresh normal/rework 后按 `current/` 引用清理未使用的 `manual_masks/*_manual.png`，避免回退 prelabel 后磁盘残留
- 将 `resolve_task_image_path` 下沉到 `common/task_image_paths.py`；`exporters/apply_current_from_export` 与 importers 改为依赖 common，解除 exporters → importers 反向依赖
- 将 `resolve_current_seg_mask_path` 与 `MANUAL_MASK_REL_DIR` 下沉到 `common/seg_mask_paths.py`；`exporters/previous_annotations` 与 `merge/materialize_final_seg` 改为依赖 common，解除 P4 exporters → P5 merge 反向依赖
- 文档继续对齐：`docs/real_batch_local_test_runbook.md`（SEG 多边形；previous 不含原图；`should_rework` 表述）、`docs/data_layout.md`（推荐 `export-split`、自包含边界、`export_round` 未接线）、`docs/labelstudio_usage.md` / `README.md` / `docs/formats.md` 交叉说明；Requirement 流程第 8 步与 SEG 工作台 PolygonLabels；Development Tasks T4.2 用语
- 文档对齐代码（优先 4 份）：`docs/labelstudio_usage.md`（SEG 多边形操作/FAQ）、`docs/data_layout.md`（polygon 预填、`manual_masks` brush|polygon、legacy rework 用 effective result）、`.cursor/rules/Requirement Specification.md`（§7.8.3–§7.8.4 / §8.4 与 §7.7 `should_rework` 一致）、`.cursor/rules/Development Tasks.md`（目录/`importers`/CLI 与仓库现状对齐）
- 文档/注释澄清 `apply-current` 与 `export-split` 职责：前者为 export→current 底层同步；后者为其高级封装并返回 normal/rework 路径。**勿对同一 export 连续执行两条命令**（README / CHANGELOG / 模块 docstring / CLI help）

### Tests

- 新增 `tests/test_cleanup_manual_masks.py`：引用保留/回退删除/orphan 删除/缺目录与缺 current no-op/非 manual 文件忽略/apply 链路清理
- 新增 `tests/test_task_image_paths.py`：jpg/jpeg 解析；缺目录/缺文件/多匹配拒绝
- 新增 `tests/test_seg_mask_paths.py`：manual/prelabel 路径解析；空串/绝对路径/`..` 前缀/逃逸拒绝

### Added

- `exporters/cleanup_manual_masks.py`：`cleanup_unreferenced_manual_masks`
- `exporters/effective_result.py`：`resolve_effective_result` 统一 annotation / prediction fallback（保留人工清空：`annotation.prediction` 有值且无任务控件时不回退）
- `extract_ls_raw_results` 改为返回 **effective** result，legacy `rework-import --export` 在仅勾选 `human_confirmed` 时仍能带上预标注几何/文本
- 测试：`tests/test_effective_result.py`（人工覆盖、仅确认 fallback + warning、人工清空不回退、legacy 三任务 rework 预填）

### Changed (effective result)

- `parse_ls_export` 调用 `resolve_effective_result`（共享策略与 warning；payload 仍走原有 SEG/DET/CAP 三态，**不改** `current/annotations.json` 字段）
- 文档：`README.md`

### Notes

- 未改 CLI 参数、目录结构、current JSON schema、测试行为

### Added (earlier same day — rework self-contained)

- `exporters/previous_annotations.py`：rework 包自包含快照 `previous_annotations/<task>.json`（SEG 另拷贝 `masks/`）
- `rework-import` 优先读 previous_annotations 生成 LS predictions（DET rectanglelabels / SEG polygonlabels / CAP textarea）
- 测试：`tests/test_previous_annotations.py`（无 export 导入、预测控件断言、旧 export 兼容、apply-current 覆盖不受影响）
- `converters/seg_polygon.py`：SEG polygonlabels 百分比点 ↔ `numpy.uint8` mask（`cv2.fillPoly` / 连通域 + `approxPolyDP`）→ PNG
- `SEG_PREFILL_MODE`（默认 `polygon`；可选 `brush`）与 `build_seg_polygon_results`
- 依赖：`numpy>=1.26.0`、`opencv-python-headless>=4.8.0`
- 测试：`tests/test_seg_polygon.py`（polygon→mask、mask→polygon、round-trip IoU）；`parse_ls_export` polygon 落盘用例
- CAP human-over-prelabel：`annotation.cap_text` 优先于 `predictions[-1].cap_text`；人工空文本表示清空
- `current_annotations`：允许 CAP `caption=""`（human clear），不再把空串当缺失
- `models.should_rework(human_confirmed, needs_rework)`：统一返工判定 `(not human_confirmed) or needs_rework`
- Requirement Spec 7.7 / `docs/data_layout.md`：明确 `rework = 未达最终确认状态`（非仅 `needs_rework=True`）

### Changed (earlier same day)

- `write_normal_rework_bundles`：刷新 normal/rework 时同步写出 previous_annotations（来源 `TaskAnnotationResult.annotation`，不依赖 LS raw export）
- `build_rework_ls_tasks`：新增 `prediction_source="previous"|"raw"`
- `mma rework-import --export` 改为可选；无 previous 快照时仍要求 `--export`
- SEG 工作台 `seg.xml`：`BrushLabels` → `PolygonLabels`（`name=seg_mask` 不变）
- `DEFAULT_LS_RESULT_SPECS[SEG].type` → `polygonlabels`；预填默认发百分比 `points`
- `parse_ls_export`：同时接受历史 `brushlabels`+`rle` 与 `polygonlabels`+`points`，统一写出 `manual_masks/{image_id}_manual.png`
- `parse_ls_export` CAP：无 annotation `cap_text` 时回退 `task.predictions[-1].result`；两边皆无仍报错
- `split_by_rework` / `ResultBundle` / `validate_ready`：一律经 `should_rework`；无直接用 `needs_rework` 单独做 normal/rework 目录分类；REWORK bundle 允许 `human_confirmed=False` 且 `needs_rework=False`
- 下游 `mask_ref` / `apply-current` / `export-split` / final 物化契约不变
- 文档：`README.md` / `docs/formats.md` / `docs/labelstudio_usage.md` / `docs/data_layout.md`

### Notes (earlier same day)

- DET `BBox` 无 label 字段：previous 快照不伪造 label；导入时由 `DEFAULT_LS_RESULT_SPECS` 写入 `rectanglelabels=["object"]`
- **不删除** `seg_brush.py`；brush 编解码与 `seg_prefill_mode="brush"` 仍可用

## 2026-08-13

### Added

- `importers/validate_prelabel_coverage.py`：`ls-import` 前校验任务包 `image_id` 集合 ≡ `prelabels.json`；缺样本报 `Missing prelabels`，多余报 `Unknown prelabels`（禁止静默跳过/补齐/删除）
- `merge/materialize_final_seg.py`：merge 写盘前将 SEG mask 物化到 `final/<batch>/final_assets/masks/{image_id}.png`
- `paths.final_assets_masks_dir`；`assert_final_seg_mask_contract` 禁止 final 中出现 `masks/` / `manual_masks/` / `prelabels/` 根
- `seg_brush.write_empty_manual_mask`：按给定宽高写出全背景人工 mask PNG

### Changed

- `build_ls_import_tasks`：生成 tasks 前读取任务包 `manifest.json` 并调用 coverage 校验
- **取消 `pending/` 三态**：`split_by_rework` 恢复为 `(normal, rework)`；仅 `human_confirmed and not needs_rework` → normal；未确认（无论 `needs_rework`）与确认需返工 → rework
- 删除 `paths.results_pending_dir`；不再创建 pending
- **`current/` 为唯一真实源**：新增 `refresh_normal_rework_from_current`；`apply-current` 合并写入 current 后自动全量重建 normal/rework；`export-split` 先 apply 再返回两路路径（禁止按本轮 export 子集追加/覆盖导致首轮 normal 僵死）
- `rework-import` 解包适配两元组；未确认样本进入 rework 后可走返工再导入
- `merge_to_final`：enrich 后、写 `manifest.json` 前执行 SEG materialize；清单中 `seg.mask_ref` 统一为 `final_assets/masks/{image_id}.png`（空 mask 只复制不重生成）
- 不改动 merge 门禁 / Label Studio XML / `prelabels` / `manual_masks` / `current` JSON schema

### Fixed

- SEG 导出解析：区分「无 annotation SEG 操作 → 回退预标注 `data.mask_ref`」与「有 SEG 操作但 brush 为空 → 写空人工 mask」，不再把人工清空病灶误恢复为 AI 预标注
- 操作信号：`from_name=seg_mask`（含空 `rle`）或 `annotation.prediction` 非空（从 prediction 接受后删光 brush）
- DET 导出解析三态：`annotation` 有 `det_bbox` → 用人框；无框但 `annotation.prediction` 非空 → 空框（接受预标注后删光）；无框且无 prediction 链接 → 回退 `task.predictions` 预标注框（未操作不再静默丢预标注）
- final `mask_ref` 双根路径（`manual_masks/` vs `masks/`）导致下游无法统一读取
- `export-split`：`human_confirmed=no` 进入 rework（不再单独 pending）
- `ls-import`：预标注未覆盖任务包全量样本时延后到 merge 才失败

### Tests

- `tests/test_parse_ls_export.py`：Case1 无 SEG 操作回退预标注；Case2 `prediction` 链接删光 / 空 rle 标记写空 mask；Case3 有 brush 写人工 mask
- `tests/test_parse_ls_export.py`：DET Case1 未操作回退 predictions；Case2 annotation 框优先；Case3 `prediction` 链接删光 → 空框
- `tests/test_merge_to_final.py`：Case1 人工 mask / Case2 预标注 / Case3 空 mask 物化；Case4 全量 `final_assets/masks/` 前缀校验
- `tests/test_split_by_rework.py` / `test_export_split_from_export.py` / `test_cli.py`：两态分类；未确认 → rework；无 pending 目录
- `tests/test_apply_current_from_export.py` / `test_export_split_from_export.py`：多轮返工子集 apply 后 normal 全量含已修好样本；export-split 同步写 current
- `tests/test_build_ls_tasks.py`：prelabel coverage Case1–4（相等 / 缺 / 多 / 顺序无关）

### Docs

- 新增 `docs/real_batch_local_test_runbook.md`（`real_batch` 本地 P1–P5 全链路 SOP，主流程含至少两轮返工）
- `README.md` / `docs/data_layout.md` / `docs/labelstudio_usage.md`：取消 pending；`current` 权威 + apply/export-split 全量刷新 normal/rework；SEG 人工优先；final 自包含 `final_assets/masks/`；ls-import coverage；DET 三态解析
## 2026-08-12

### Added

- SEG 人工 brush 持久化：`seg_brush.decode_rle` / `ls_rle_to_binary_mask` / `union_binary_masks` / `write_manual_mask_from_brush_results`（纯 Python + Pillow，无 numpy）
- `paths.results_manual_masks_dir` → `results/<batch>/seg/manual_masks/`
- `parse_ls_export` / `parse_ls_export_data` 可选参数 `seg_manual_mask_dir`：有 brush 时写出 `{image_id}_manual.png`，`mask_ref` 为 `manual_masks/{image_id}_manual.png`
- T5.4：新增 `src/mma/merge/write_final.py`（`write_final_manifest` 原子写出 `final/<batch>/manifest.json`）
- T5.4：新增 `src/mma/merge/merge_to_final.py`（`merge_multitask` → processed 回填图文 → 写盘）
- `paths.py`：新增 `final_batch_dir`
- CLI：接线 `mma merge --batch [--data-root]`
- `merge/__init__.py` 导出 `merge_to_final` / `write_final_manifest` / `FINAL_MANIFEST_NAME`
- T5.3：`assert_no_missing_tasks`（合并缺任务阻断：缺 DET/CAP 即 `ValueError`；禁止静默缺字段；不写 `final/`）
- `merge/__init__.py` 导出 `assert_no_missing_tasks`

### Changed

- `apply_current_from_export` / `export_split_from_export`：SEG 任务传入 `results/.../seg/manual_masks`，保证 current 与 normal/rework 的 `mask_ref` 一致
- 未传 `seg_manual_mask_dir` 时 SEG 仍只用 `data.mask_ref`（兼容单测与旧调用）
- 不覆盖 `prelabels/.../masks/` 原始预标注文件
- `merge_multitask` 改为调用 `assert_no_missing_tasks`（保留 `validate_ready` 后的二次校验）
- `docs/data_layout.md`：钉死 `final/<batch_id>/manifest.json` 对齐 `MergedMultitaskRecord`；补充 SEG `manual_masks/`

### Docs

- 对齐审查问题 1/2/3/6/8：任务书/需求与实现一致（`convert` 非验收、仅 `.xlsx`、Choices yes/no、processed 绝对路径例外、LS 文档范围）
- `docs/data_layout.md`：final 前置明确三路 current `image_id` 须与 processed 全量集合一致
- 明确 `apply-current` / `current/` 为按 `image_id` 合并写入；文档区分全量轮与返工轮导出范围（审查问题5方案A）
- 声明本阶段配置内嵌：不采用根目录 `configs/default.yaml`；约定见 `paths`/`io`/CLI/`data_layout`（审查问题7方案α）

### Fixed

- `validate_ready`：三路 current 的 `image_id` 须与 `processed/manifest.json` 全量集合相等（禁止子集静默合并）

### Tests

- 扩展 `tests/test_seg_brush.py`：encode↔decode 往返、多 brush OR 并集
- 扩展 `tests/test_parse_ls_export.py`：无目录兼容、无 brush、有 brush 写 manual
- 扩展 `tests/test_apply_current_from_export.py` / `test_export_split_from_export.py`：SEG `mask_ref` 指向 manual
- 扩展 `tests/test_merge_to_final.py`：final 保留人工 `mask_ref`；current 多 id 时改断言门禁前移
- 新增 `tests/test_merge_to_final.py`：写盘形状、成功回填、覆盖、未就绪保旧、缺任务/缺 processed 不写、非法 batch
- 扩展 `tests/test_cli.py`：`merge` 成功/失败（原 merge stub 改为 convert stub）
- 扩展 `tests/test_merge_multitask.py`：缺 DET/CAP（旁路门禁）、直接测 `assert_no_missing_tasks`、类型不符阻断；成功路径补 processed
- 扩展 `tests/test_validate_ready.py`：与 processed 集合相等；子集/超集/缺 manifest 阻断

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
