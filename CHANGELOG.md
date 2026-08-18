# Changelog

## V1 — R3 删除返工 raw 预填旁路（2026-08-19）

### Changed

- `build_rework_ls_tasks` 只读 `previous_annotations`；去掉 `prediction_source` / `raw_results_by_image_id`
- `rework_import_from_export` 删除未调用的 `_build_from_export`；CLI `--export` 仍保留、deprecated、不用于预填

### Tests

- 新增 `tests/test_r3_rework_no_raw_prefill.py`：源码禁词、raw 关键字必须 `TypeError`
- 删除 `test_build_rework_tasks.py` 中 raw 预填成功用例

### Docs

- SOP §6.8 / `docs/real_batch_local_test_runbook.md` / `docs/formats.md`：去掉「无快照仍可用 `--export` 预填」


## V1 — R2 隔离 prelabel→LS 转换 API（2026-08-19）

### Changed

- `mma.converters` 不再导出 `document_to_ls_tasks` / `item_to_ls_task` / `MODEL_VERSION` / `SEG_PREFILL_MODE` / `build_seg_*_results`
- prelabel 中间格式 → LS import 迁至 `mma.legacy.converters`；V1 converters 仅保留返工/导出几何与字段名
- `mma convert` stub 文案改为指向 `mma.legacy.converters.document_to_ls_tasks`

### Tests

- 新增 `tests/test_r2_converters_no_prelabel_api.py`：禁止从 `mma.converters` / `to_labelstudio` 旧路径导入；主路径 import 图不含 `mma.legacy.converters`
- Prelabel SEG 叠图用例迁至 `tests/legacy/test_seg_prelabel_geometry.py`；默认套件保留 mask ↔ LS 几何

### Docs

- `docs/formats.md`：T2.2 公开 API 指向 `mma.legacy.converters`
- `docs/V1_LOCAL_FULL_CHAIN_TEST_REPORT.md`：路径说明同步


## V1 — R1 缺任务结果补进 rework（2026-08-19）

### Changed

- `export-split` / `apply-current`：对照任务包 `manifest.json`。任务包有、本轮 export 与 `current/` 都没有的 `image_id` 写入空结果（未确认、无有效载荷），经 `should_rework_result` 进入 `rework/`
- export 含任务包没有的 `image_id`、或缺少任务包 manifest：整批失败
- current 已有且本轮未出现的 id 仍保留（返工子集导出语义不变）
- SEG 缺失样本写空 `manual_masks/`（`has_foreground=False`），保证后续 `rework-import` 能读到 mask

### Tests

- 新增 `tests/test_fill_missing_from_package.py`：缺样本进 rework、第二轮子集不冲掉 normal、空 export 补全、无包失败、多余 id 失败、DET/SEG 缺样本；SEG 空 mask 后 `rework-import` 成功
- 现有 apply-current / export-split 用例补与 export 一致的最小任务包 manifest

### Docs

- README / `docs/data_layout.md` / `docs/labelstudio_usage.md` / `docs/V1_LOCAL_FULL_CHAIN_TEST_REPORT.md`：补洞规则与「未出现保留」拆开写清

## V1 — P10 冻结声明对齐 M2.2 B2 已完成（2026-08-19）

### Docs

- `docs/M12.6_FINAL_FREEZE_REPORT.md`：Non-blocking 第 1 条由「B2 未做且不阻塞」改为 **DONE（P2）**——返工预填不再构造 `PrelabelItem`，主路径 import 图不含 `legacy_prelabel`

### Verified

- 代码事实见文首 P2；无生产代码变更

## V1 — P9 rework-import 无快照不再用 --export 预填（2026-08-19）

### Changed

- `rework-import`：无 `previous_annotations` 时一律失败（即使传了 `--export`）；提示先 `export-split` / `apply-current`
- CLI `--export` 仍保留、deprecated，不用于预填

### Tests

- 无快照 + `--export` 期望失败；CLI 成功路径先落盘快照

### Docs

- README / `labelstudio_usage` / `data_layout`：去掉无快照回退 `--export`

## V1 — P8 删除未用 prelabels_task_dir（2026-08-18）

### Changed

- `common/paths.py`：删除未用的 `prelabels_task_dir`（M5.3）；主流程本无调用

## V1 — P7 README 补 pytest 验证步骤（2026-08-18）

### Docs

- README「环境与安装」：安装后增加 `pytest`；注明默认排除 `legacy`

## V1 — P6 prelabel 覆盖校验迁出主 importers（2026-08-18）

### Changed

- `validate_prelabel_coverage` 从 `mma.importers` 迁至 `mma.legacy`；V1 `ls-import` 仍不调用
- `tests/test_build_ls_tasks.py` 不再测该 helper；用例迁 `tests/legacy/`（`pytest -m legacy`）

### Tests

- `tests/legacy/test_validate_prelabel_coverage.py`：集合相等 / Missing / Unknown

## V1 — P5 文档分类公式对齐 should_rework_result（2026-08-18）

### Docs

- `docs/data_layout.md` §4.7 / §7.5、`docs/labelstudio_usage.md`：运行时分类改为 `should_rework_result` 三支路（含空载荷）
- 旧 `should_rework` 仅作勾选辅助说明；不写「未提交会解析失败」（P1 已覆盖）
- `docs/V1_LOCAL_FULL_CHAIN_TEST_REPORT.md` 附录：§4.7 不再标过时

### Changed

- 无生产代码变更

## V1 — P4 CAP 界面标题去掉预标注语义（2026-08-18）

### Changed

- `cap.xml`（src 与 `deploy/v1/annotator_cap`）：Header「预标注文本」改为「人工描述」；`cap_text` 控件名未改

### Tests

- `tests/test_labelstudio_cap_config.py`：配置不含「预标注」，且存在 Header「人工描述」

### Docs

- `docs/V1_LOCAL_FULL_CHAIN_TEST_REPORT.md`、`docs/M12.6_FINAL_FREEZE_REPORT.md` 过时「预标注文本」说明已对齐

## V1 — P3 M12.2 场景2门禁收口（2026-08-18）

### Verified

- M12.2 / 规格场景 2「没有任何人工标注 → rework/」已由 P1 覆盖：`annotations: []` / 空 `result` 解析为空载荷并进 `rework/`，`export-split` 不整批失败
- 原有三条「已确认 + 空载荷」M12.2 用例保留（空 caption / 空框 / SEG 无前景）
- parse 对缺 `human_confirmed`、空/未提交标注保持正向可解析；非法结构仍 fail-closed

### Tests

- 无新增用例；覆盖见 P1：`tests/test_m12_2_empty_to_rework.py`、`tests/test_parse_ls_export.py`

### Docs

- README 分类规则已含未提交/空 result，本任务不改 README

## V1 — P2 返工编码脱离 PrelabelItem（2026-08-18）

### Changed

- 返工预填（`previous_annotations`）直接用 V1 `BBox` / caption / mask 文件编 LS result，不再构造 `PrelabelItem`
- `to_labelstudio` / `seg_polygon` / `seg_brush` 对 legacy prelabel 类型改为函数内懒加载；V1 主路径 import 不再加载 `legacy_prelabel`
- 保留 `item_to_ls_task` / `document_to_ls_tasks` / `build_seg_polygon_results` / `build_seg_brush_results` 作为 legacy 入口

### Tests

- `tests/test_m2_2_runtime_no_legacy_prelabel.py`：子进程 import 验收 + `previous_annotations.py` 源码 grep
- `tests/test_previous_annotations.py`：空 / 空白 caption 预填为空 textarea

### Docs

- README：返工预填编码走 V1 类型；Sprint D 状态注明 P2 / B2 已完成

## V1 — P1 空/未提交标注进 rework（2026-08-18）

### Changed

- `parse_ls_export` / `resolve_effective_result`：无 annotations、全 cancelled、`result` 为空/`null`、或缺少 `human_confirmed` 时，解析为空载荷（未确认默认 `false`），经 `should_rework_result` 进入 `rework/`，**不再整批失败**
- 未提交 SEG 仍写空 `manual_masks/`（非空 `mask_ref`）；无法确定尺寸时仍报错
- `extract_ls_raw_results`：空/未提交样本保留 `image_id` 键，值为空 tuple
- `human_confirmed` 非法值 / 重复控件 / 非 list 的脏 `annotations`/`result`：仍 fail-closed

### Tests

- `tests/test_parse_ls_export.py`：空 annotations / null result / 缺 confirmed / 混合批次 / 非法结构
- `tests/test_m12_2_empty_to_rework.py`：无 annotations 的 CAP/DET/SEG export-split；空 result；缺 confirmed 保留 caption；混合批次
- `tests/test_extract_ls_raw_results.py`、`tests/test_effective_result.py`：空样本不 raise、predictions 不进 effective

### Docs

- README 分类规则：未提交/空 result 不中断整批
- `docs/V1_LOCAL_FULL_CHAIN_TEST_REPORT.md` §6.7 与实现对齐

## V1 — M12.6 Final Freeze（2026-08-18）

### Added

- `docs/M12.6_FINAL_FREEZE_REPORT.md`：冻结审计报告（架构 / 数据流 / LS / 部署 / 测试 / 非阻塞项）

### Verified

- **未修改** `src/mma` 核心逻辑、`deploy/v1` 结构、Label Studio XML、测试体系
- M9 / M11 / M0 已完成；主流程无 prelabels / model prediction 输入；无运行时 legacy adapter
- `git diff -- src/mma` 为空

### Tests

- 全量 `pytest`（`PYTHONPATH` 指向本仓 `src`）：**408 passed**, 2 skipped, 0 failed, 44 deselected（legacy marker）

### Docs

- README 状态：**Medical Image Multi-task Annotation Dataflow V1 Frozen**
- **未**写「最终发布完成」/ Final Release Completed

### Planned（不阻塞冻结）

- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem` → **已完成，见文首 P2 节**

## V1 — M0 文档定稿（2026-08-18）

### Changed

- README：Sprint D 勾选 M11 / M9 / M0；补充 `src/mma` → `mma` CLI → `deploy/v1` 调用关系；**未**宣布最终发布
- `docs/formats.md`：纠正「`ls-import` 仍可能读取 prelabels」的过时〔现状〕表述（改为 Legacy only）
- `docs/data_layout.md`：主路径现状同步至 M0；Planned 仅余 M12.6
- `docs/labelstudio_usage.md`：标注员包 XML 副本路径；四角色文档交叉引用
- `docs/real_batch_local_test_runbook.md`：现行 V1 主流程去掉「必须放置 prelabels」；历史半自动步骤保留并标 Legacy

### Verified

- **未修改** `src/mma/**`、`deploy/v1/**`、`tests/**`、XML
- 角色文档（deploy README）审计一致：处理者六命令 / 标注员三命令；未改 deploy 文件
- M9 DONE、M11 DONE；**M12.6 Final Freeze 仍为 pending**

### Tests

- 全量 `pytest`（文档改动后，`PYTHONPATH` 指向本仓 `src`）：**408 passed**, 2 skipped, 44 deselected

### Docs

- M0.1 需求叙述与实现一致（主 README 快速开始无 prelabels）
- M0.2 架构叙述冻结为现有三层调用，无新概念
- M0.3 四角色职责与 deploy 包一致（审计，未改 deploy）
- M0.4 / M0.5 发布状态与 legacy 文档边界

### Planned（仍未完成）

- ~~**M12.6 Final Freeze**~~ → 见文首 M12.6 节
- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem`

## V1 — M9.1–M9.3 Label Studio 配置验收收口（2026-08-18）

### Added

- `tests/test_labelstudio_empty_task.py`：SEG/DET/CAP 无 `predictions` / 无 `prelabels` 时仍可 `build_ls_import_tasks`，任务仅含 `data`
- `tests/test_labelstudio_deploy_sync.py`：源 XML 与 `deploy/v1/annotator_*/configs/` 换行 + 首尾空白归一化后一致
- `tests/test_labelstudio_*_config.py`：配置文本不包含 `prediction` / `prelabel`（大小写不敏感）

### Verified

- **未修改** `src/mma` 核心业务逻辑与 Label Studio XML；未改 deploy 架构
- M9.1：空任务导入兼容已由既有 `ls-import` + 本专项测试锁定
- M9.2：角色包配置与 `src/mma/labelstudio/configs/` 同步
- M9.3：既有 config 回归保留，并补无 pred/prelabel 断言

### Tests

- `pytest tests/test_labelstudio_*`：**27 passed**
- 全量 `pytest`（`PYTHONPATH` 指向本仓 `src`）：**408 passed**, 2 skipped, 44 deselected（legacy marker）

### Docs

- README 实现状态勾选 M9；Sprint D 余项：~~M0~~（见文首 M0 节）、M12.6

### Planned（仍未完成）

- ~~**Sprint D 余项**：文档冻结（M0）~~ → 见文首 M0 节
- **M12.6 Final Freeze**
- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem`

## V1 — M11.1–M11.5 deploy/v1 四角色部署包（2026-08-18）

### Added

- `deploy/v1/`：四角色薄包装包 `data_processor` / `annotator_seg` / `annotator_det` / `annotator_cap`
- `deploy/v1/_lib/role_cli.py`：查找 `mma`、allowlist、强制 `--task`、构造 subprocess（无业务逻辑）
- 各角色 `README.md`：环境、命令、数据目录；处理者区分协作主路径与本机全流程测试
- 标注员包：本任务 LS 配置副本（`configs/*.xml`）+ 裁剪入口（ls-import / export-split / rework-import）
- `deploy/v1/manifest.json`（sprint=D，M11.1–M11.5）与根 `deploy/v1/README.md`（分发 / 回传 / 交接）
- `tests/test_m11_deploy.py`：目录结构、禁止项、XML 换行归一化一致性、`role_cli` 白名单

### Verified

- **未修改** `src/mma` 核心业务逻辑（preprocess / importer / exporter / merge / cli / 格式定义）
- 入口仅调用已有 `mma` CLI（或 `python -m mma`）；不 import 内部业务模块
- 无 `prelabels/`、无 prediction 相关部署物、无 legacy adapter 拷贝
- 验收加固：多 `--task` 拒绝绕过；清理项目内 `__pycache__` / `*.pyc`；`.gitignore` 显式补充 `*.pyc`

### Changed

- `role_cli.inject_task`：出现多个 `--task` / `--task=` 时直接失败（禁止先匹配后忽略）
- `tests/test_m11_deploy.py`：补充多 task、`__pycache__` 禁止、role_cli 无业务 import 扫描

### Tests

- `tests/test_m11_deploy.py`：**15 passed**（含多 `--task`、未跟踪 `__pycache__`、无业务 import 扫描）
- 全量 `pytest`（`PYTHONPATH` 指向本仓 `src`）：**403 passed**, 2 skipped, 44 deselected（legacy marker）

### Docs

- 根 `README.md`：实现状态勾选 M11；指向 `deploy/v1/`
- Sprint D 余项：~~M9~~（见文首 M9 节）、M0 文档定稿、M12.6 冻结

### Planned（仍未完成）

- **Sprint D 余项**：文档冻结（M0）、M12.6
- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem`

## V1 — M12.5 场景门禁：返工闭环 → merge 出 final（2026-08-17）

### Added

- `tests/test_m12_5_rework_loop_to_final.py`：CAP 空标注进 rework 时 merge 失败；`rework-import` 仅 `previous_annotations` → 修好 → merge 出自包含 final。

### Verified

- **`src/` 运行时未改**；DET/SEG 预置就绪，只让 CAP 走闭环；不改 runbook、不测第二轮仍留返工。

### Tests

- 门禁 **2 passed**（`PYTHONPATH` 指向本仓 `src`）：`tests/test_m12_5_rework_loop_to_final.py`。

### Docs

- README 关闭 M12.5；Sprint C 必做项收口。余项为可选 B2 / Sprint D。

### Planned（仍未完成）

- ~~**Sprint D：`deploy/v1`（M11）**~~ → 见文首 M11 节
- **Sprint D 余项**：文档冻结（M0）、M12.6
- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem`

## V1 — M12.4 场景门禁：SEG/DET/CAP 独立运行（2026-08-17）

### Added

- `tests/test_m12_4_independent_tasks.py`：只种本任务包即可 `ls-import`；`export-split` 只写本任务 `results/`；CAP 分类不改写已有 DET `current/`。

### Verified

- **`src/` 运行时未改**（`--task` 子树隔离已具备）；不测 merge 单任务、不测 `rework-import`（M12.5）。

### Tests

- 门禁 **7 passed**（`PYTHONPATH` 指向本仓 `src`）：`tests/test_m12_4_independent_tasks.py`。

### Docs

- README 实现状态关闭 M12.4；Sprint C 余项仅 M12.5。

### Planned（仍未完成）

- ~~**M12.5**~~ → 见文首 M12.5 节
- **Sprint D**：`deploy/v1`（M11）、文档冻结（M0）、M12.6
- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem`

## V1 — M8.3 merge 回归（2026-08-17）

### Verified

- 回归范围仅为既有：`tests/test_merge_to_final.py`、`tests/test_merge_multitask.py`、`tests/test_validate_ready.py`（合计 41 条）。
- **`src/mma/merge/` 运行时未改**（M8.1/M8.2 已核实三任务合并、final 自包含、就绪不要求 `prelabels/`）。
- 不新增用例；CLI merge 两条不计入本任务验收（M8.1 已过）。

### Tests

- 回归 **41 passed**（`PYTHONPATH` 指向本仓 `src`）：`tests/test_merge_to_final.py`（16）、`tests/test_merge_multitask.py`（10）、`tests/test_validate_ready.py`（15）。

### Docs

- README 实现状态关闭 M8.3；Sprint C 余项仅 M12.4–M12.5。

### Planned（仍未完成）

- ~~**M12.4**~~ → 见文首 M12.4 节
- **M12.5**：返工闭环 → merge 出 final
- **Sprint D**：`deploy/v1`（M11）、文档冻结（M0）、M12.6
- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem`

## V1 — M8.2 merge 就绪不依赖 prelabels（2026-08-17）

### Verified

- `merge/` 运行时不读 `prelabels/`；`prelabels` 仅出现在 final mask 契约的**禁止根**校验（非「必须有」）。
- 就绪语义仅为三路 `current/` + processed + `should_rework_result`。

### Changed

- `validate_ready` docstring：第 3 条改为 `should_rework_result`（含空载荷）；写明不要求 `prelabels/`。

### Tests

- 冒烟 **16 passed**（`PYTHONPATH` 指向本仓 `src`）：`tests/test_validate_ready.py`（15，含 `test_validate_ready_succeeds_without_prelabels_dir`）+ `tests/test_merge_to_final.py::test_case2_legacy_prelabel_mask_ref_rejected`。

### Docs

- README 实现状态关闭 M8.2；M8.3 仍待做。

### Planned（仍未完成）

- ~~**M8.3**~~ → 见文首 M8.3 节
- **M12.4–M12.5**：独立运行 / 返工闭环门禁
- **Sprint D**：`deploy/v1`（M11）、文档冻结（M0）、M12.6
- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem`

## V1 — M8.1 三任务 merge + final 自包含核实（2026-08-17）

### Verified

- 保持现有 `merge/**`：`validate_ready` → `merge_multitask` → `merge_to_final`（复制 `images/{image_id}.jpg`、物化 `masks/{image_id}.png`、相对路径 `manifest.json`）。
- **代码未改**（三任务 current 合并与 final 自包含已具备）。
- 冒烟：**28 passed**（`PYTHONPATH` 指向本仓 `src`）：`tests/test_merge_to_final.py`（16）、`tests/test_merge_multitask.py`（10）、`tests/test_cli.py::test_merge_success` / `test_merge_failure_not_ready`。

### Tests

- 冒烟 28 passed：见上文 Verified。

### Docs

- README 实现状态关闭 M8.1；M8.2 / M8.3 仍待做。

### Planned（仍未完成）

- ~~**M8.2**~~ → 见文首 M8.2 节
- **M8.3**：回归 `test_merge_*.py`、`test_validate_ready.py`
- **M12.4–M12.5**：独立运行 / 返工闭环门禁
- **Sprint D**：`deploy/v1`（M11）、文档冻结（M0）、M12.6
- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem`

## V1 — M6.4 previous_annotations 语义文档收口（2026-08-17）

### Changed

- `exporters/previous_annotations.py`：公开 API / `build_ls_prediction_results_from_previous` docstring 钉死「上一轮人工快照」；`previous_annotations` ≠ prediction（LS `predictions` 仅为预填槽）；`PrelabelItem` 标注为 legacy 编码复用、不读 `prelabels/`。
- `docs/data_layout.md`：清理过时 〔现状〕（ls-import/prelabels、prediction fallback、空载荷 rework）为已落地口径。

### Tests

- `test_previous_annotations.py`：轻量门禁 `test_module_doc_states_previous_ne_prediction`（模块 docstring 含人工快照 ≠ prediction）。

### Docs

- README 实现状态关闭 M6.4；`labelstudio_usage` §8.1 已对齐，未改。

### Planned（仍未完成）

- ~~**M8.1**~~ → 见文首 M8.1 节
- **M8.2**：merge 隐式 prelabel 依赖检查
- **M8.3**：`test_merge_*` / `test_validate_ready` 回归
- **M12.4–M12.5**：独立运行 / 返工闭环门禁
- **Sprint D**：`deploy/v1`（M11）、文档冻结（M0）、M12.6
- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem`

## V1 — M4.3 返工预填源仅 previous_annotations（2026-08-17）

### Changed

- `build_rework_ls_tasks`：默认 `prediction_source` 改为 `"previous"`（V1 主路径）；`raw` 须显式传入（legacy `--export`）。
- previous 路径 SEG `data.mask_ref` 只用来自快照的 `mask_file`；不再回退 `item.annotation.mask_ref`。
- 注释 / CLI help：LS `predictions` / `model_version` 为人工历史预填槽；`rework-import` 不读 `prelabels/`。

### Tests

- `test_build_rework_tasks.py`：previous 默认源、CAP/DET 快照预填、忽略 orphan `prelabels.json`、空 CAP 载荷仍出任务、SEG `mask_ref` 仅来自快照；现有 raw 用例显式 `prediction_source="raw"`。
- `test_effective_result.py`：返工形态 `predictions` + confirm-only annotation → `source="empty"`（M6.1 联调）。
- `test_cli.py`：`rework-import -h` 含 `previous_annotations` 且声明不读 prelabels。

### Docs

- README 实现状态关闭 M4.3；`docs/labelstudio_usage.md` 补「不读 prelabels/」。

### Planned（仍未完成）

- ~~**M6.4**~~ → 见文首 M6.4 节
- **M8**：merge 隐式 prelabel 依赖检查
- **M12.4–M12.5**：独立运行 / 返工闭环门禁
- **Sprint D**：`deploy/v1`（M11）、文档冻结（M0）、M12.6
- **M2.2 B2**（可选）：返工路径脱离 `PrelabelItem`

## V1 — Sprint B 完成：清理与隔离（2026-08-17）

### Summary

Sprint B（运行时零依赖 `prelabels/` 主路径；formats / adapters 隔离；CLI / examples / converter 语义收口）**已完成**。详见下列分条（同日落地的 M1–M3 / M5 / M7 / M10）。

### Done（Sprint B）

| 范围 | 内容 |
|---|---|
| **M1.1–M1.3** | `adapters` → `mma.legacy.adapters`；legacy 测试隔离；无 runtime shim |
| **M2.1–M2.4** | `formats` 三分 `task_schema` / `annotation_schema` / `legacy_prelabel`；根包不再导出 Prelabel* |
| **M5.3–M5.5** | `prelabels_task_dir` deprecated；`seg_mask_paths` 仅 `manual_masks/`（无 prelabels fallback）；models 注释收口 |
| **M3.2–M3.4** | converter / `previous_annotations` 语义：LS `predictions` ≠ 模型推理；`test_convert` 标 `legacy` |
| **M3.3 / M10.2** | `mma convert` 明确 V1 不支持 prelabel conversion；`examples/` 默认 preprocess→package→ls-import |
| **M7.1–M7.3** | 确认 `preprocess` / `packaging` 无 legacy/prelabel 依赖（代码未改；单测全绿） |

### Docs / Tests

- 默认 `pytest` 排除 `legacy` marker；`pytest -m legacy` 仍可跑历史套件。
- `docs/labelstudio_usage.md`、`docs/formats.md`、`examples/**` 与 V1 主路径对齐。

### Planned（Sprint C / D 及遗留）

- **M2.2 B2**（可选后续）：返工路径彻底脱离 `PrelabelItem` 构造——**未纳入本次 Sprint B 必做**（Phase A 仅 namespace 拆分）
- **Sprint C**：~~M4.3~~ / ~~M6.4~~ / ~~M8.1~~ / ~~M8.2~~ / ~~M8.3~~ / ~~M12.4~~ / ~~M12.5~~ → 见文首
- **Sprint D**：`deploy/v1`（M11）、文档冻结（M0）、M12.6

## V1 — M3.2–M3.4 converter 语义 + legacy 测试标记（2026-08-17）

### Changed

- M3.2 converter semantics clarified: Label Studio ``predictions`` field is not
  treated as model inference (rework / ``previous_annotations`` = historical
  human annotation prefill).
- Module docs updated: ``converters/__init__.py``, ``to_labelstudio.py``,
  ``seg_brush.py``, ``seg_polygon.py``, ``exporters/previous_annotations.py``.

### Tests

- `tests/test_convert.py`: ``pytestmark = pytest.mark.legacy``（逻辑未改）.

### Docs

- `docs/labelstudio_usage.md`: 修正过时「ls-import 仍依赖 prelabels / prediction fallback」描述.

### Planned（仍未完成）

- ~~**Sprint B**~~ → 见上一节；遗留见 Sprint B「Planned」

## V1 — M7.1–M7.3 preprocess / packaging 无 legacy 依赖（2026-08-17）

### Verified

- `src/mma/preprocess/**`、`src/mma/packaging/**`：无 `prelabel` / `Prelabel` / `prediction` / `adapter` / `legacy_prelabel` 运行时或注释依赖；**代码未改**。
- 回归：`tests/test_preprocess.py`、`tests/test_packaging.py` 全绿。

### Planned（仍未完成）

- ~~**Sprint B**~~ → 见文首 Sprint B 完成节

## V1 — M3.3 / M10.2 CLI convert + examples 默认 V1（2026-08-17）

### Changed

- `mma convert`：help/stderr 明确 **V1 does not support prelabel conversion**；legacy stub only；推荐 `ls-import`（exit 2 不变）。
- `examples/README.md`：默认展示 V1（preprocess → package → ls-import）；prelabel/adapter/`run_p2_demo` 收入 Legacy 专节。

### Docs

- `examples/raw/README.md` 补充 `ls-import`；`run_p2_demo.py` / `prelabels/README` 强化 LEGACY 标记。

### Tests

- `tests/test_cli.py`：convert stub/help 断言含 v1 / does not support / ls-import。

### Planned（仍未完成）

- ~~**Sprint B**~~ → 见文首 Sprint B 完成节

## V1 — M5.3–M5.5 paths / seg_mask / models 注释（2026-08-17）

### Changed

- `paths.prelabels_task_dir`: marked **deprecated / legacy-only** (API retained; no runtime warning).
- `seg_mask_paths.resolve_current_seg_mask_path`: V1 resolves only `manual_masks/` under `results/`; **no** `prelabels/` fallback.
- `common/models.py`: comments clarify V1 annotation schema vs `formats.legacy_prelabel`.

### Tests

- `test_seg_mask_paths.py`: legacy `masks/` ref rejected; manual path still resolves.
- Merge/CLI fixtures that previously staged prelabel masks now use `manual_masks/`.

### Docs

- README 实现状态同步.

### Planned（仍未完成）

- ~~**Sprint B**~~ → 见文首 Sprint B 完成节

## V1 — M2.1–M2.4 formats 三分拆分（Phase A｜2026-08-17）

### Changed

- Split `mma.formats` into `task_schema` / `annotation_schema` / `legacy_prelabel` (Prelabel types retained, not deleted).
- `formats/__init__.py` now exports only V1 schema re-exports from `common.models`; prelabel APIs move to `mma.formats.legacy_prelabel`.
- Call sites (legacy adapters, converters, `previous_annotations`) import `legacy_prelabel` explicitly (no B2 runtime decoupling).

### Tests

- Prelabel format suite → `tests/legacy/test_formats_prelabel.py` (`pytest -m legacy`).
- `tests/test_formats.py` covers V1 schema re-exports only.

### Docs

- `formats/legacy_prelabel/README.md`；`docs/formats.md` 路径更新；README 实现状态同步.

### Planned（仍未完成）

- ~~**Sprint B**~~ → 见文首 Sprint B 完成节；可选 B2 见该节 Planned

## V1 — M1.1–M1.3 隔离 prelabel adapters（2026-08-17）

### Changed

- Isolated prelabel adapters under legacy namespace (`src/mma/legacy/adapters/`).
- Removed adapters from V1 runtime dependency graph（无 shim；CLI / importers / exporters / merge 不引用）.
- Legacy adapter 单测迁至 `tests/legacy/`；默认 `pytest` 排除 `legacy` marker；`pytest -m legacy` 仍可跑.

### Docs

- `docs/formats.md` §10：路径改为 `mma.legacy.adapters`，标明非 V1 runtime.
- README：adapters 隔离状态更新.

### Planned（仍未完成）

- ~~**Sprint B**~~ → 见文首 Sprint B 完成节

## V1 — M12.3 场景门禁：无 prelabels / 无 prediction 主流程（2026-08-16）

### Tests

- 新增 `tests/test_m12_3_no_prelabel_main_path.py`：无 `prelabels/` 下 CAP/DET/SEG 空 `ls-import`；无 `predictions` 键 export-split 三任务可进 `normal/`
- Sprint A2 场景门禁 M12.1–M12.3 齐套

### Docs

- 正式关闭 M12.3

### Planned（仍未完成）

- **adapters / formats legacy 隔离**（M1 / M2 / M5.3）
- **`seg_mask_paths` 去 prelabels**（M5.4）及 models 注释清理（M5.5）
- 返工语义收紧（M4.3 / M6.4）
- **M12.4–M12.6**：独立运行 / 返工闭环 / 冻结门禁

## V1 — M12.2 场景门禁：空标注 → rework/（2026-08-16）

### Tests

- 新增 `tests/test_m12_2_empty_to_rework.py`：CAP/DET/SEG 各 1 条（确认 + 空载荷 → 仅 `rework/`）

### Docs

- 正式关闭 M12.2；~~M12.3 仍待做~~ → 见上一节

### Planned（仍未完成）

- **adapters / formats legacy 隔离**（M1 / M2 / M5.3）
- **`seg_mask_paths` 去 prelabels**（M5.4）及 models 注释清理（M5.5）
- 返工语义收紧（M4.3 / M6.4）
- ~~**M12.3**：无 prelabels/prediction 主流程门禁~~ → 见上一节

## V1 — M12.1 场景门禁：正常人工 → normal/（2026-08-16）

### Tests

- 新增 `tests/test_m12_1_normal_path.py`：CAP/DET/SEG 各 1 条（确认 + 有效载荷 → `normal/` 且 `rework==[]`）

### Docs

- 正式关闭 M12.1；~~M12.2 / M12.3 仍待做~~ → M12.2 见上一节；**M12.3** 仍待做

### Planned（仍未完成）

- **adapters / formats legacy 隔离**（M1 / M2 / M5.3）
- **`seg_mask_paths` 去 prelabels**（M5.4）及 models 注释清理（M5.5）
- 返工语义收紧（M4.3 / M6.4）
- ~~**M12.2 / M12.3**：空→rework；无 prelabels/prediction 主流程门禁~~ → M12.2 见上一节；**M12.3** 仍待做

## V1 — M5.6 common 空标注规则测试锁定（2026-08-16）

### Tests

- `tests/test_models.py`：补 SEG 空白 `mask_ref`、NORMAL 拒 `has_foreground=False`；锁定空标注→rework
- `tests/test_seg_mask_paths.py`：文档标明 manual 为主路径；`masks/→prelabels` 为历史兼容（清理属 **M5.4**，本任务不改解析行为）

### Docs

- 正式关闭 M5.6；去 prelabels 路径解析仍见 Planned（M5.4）

### Planned（仍未完成）

- **adapters / formats legacy 隔离**（M1 / M2 / M5.3）
- **`seg_mask_paths` 去 prelabels**（M5.4）及 models 注释清理（M5.5）
- 返工语义收紧（M4.3 / M6.4）
- ~~**M12.1–M12.3**：场景门禁收口~~ → M12.1 见上一节；**M12.2 / M12.3** 仍待做

## V1 — M6.5 exporters 测试场景收口（2026-08-16）

### Tests

- `test_export_split_from_export.py`：SEG 有几何 → normal（含 `has_foreground`）；SEG 空几何 → rework；无 `predictions` 键 CAP → normal
- `test_effective_result.py`：confirm-only DET 空框经 `split_by_rework` → rework
- `test_parse_ls_export.py`：去掉误导性 `img-fallback` 命名；保留「有 pred 但不进金标准」负向用例

### Docs

- 正式关闭 M6.5；README 实现状态与空标注→rework 已落地对齐

### Planned（仍未完成）

- **adapters / formats legacy 隔离**（M1 / M2 / M5.3）
- 返工语义收紧（M4.3 / M6.4）
- ~~**M5.6 / M12.1–M12.3**：common 规则锁定与场景门禁收口~~ → M5.6 见上一节；**M12.1–M12.3** 仍待做

## V1 — M6.3 空标注分类验收闭环（2026-08-16）

### Changed

- 分类逻辑已在 M5.2 接入 `should_rework_result`；本任务收口文档与落盘验收
- `export_split_from_export` / `refresh_normal_rework`：文档与运行时规则对齐（含空载荷 → rework）

### Tests

- `tests/test_export_split_from_export.py`：已确认空 CAP / 空 DET → 写入 `rework/`、不进 `normal/`

### Docs

- `CHANGELOG.md`：正式关闭 M6.3；README 运行时规则已与 `should_rework_result` 一致

### Planned（仍未完成）

- **adapters / formats legacy 隔离**（M1 / M2 / M5.3）
- 返工语义收紧（M4.3 / M6.4）
- ~~**M6.5**：effective/parse/split/export-split 测试场景扩写~~ → 见上一节

## V1 — M5.2 SEG 空 mask 载荷 + rework 接入（2026-08-16）

### Added

- `SegAnnotation.has_foreground`（默认 `True`；legacy `current/` 缺字段加载为 `True`）
- parse：有几何 → `True`；写空 `manual_masks/` → `False`
- `has_effective_task_payload(SEG)`：非空 `mask_ref` **且** `has_foreground`

### Changed

- `split_by_rework` / `assert_result_bundle_consistent` / `validate_ready` 改用 `should_rework_result`（空 DET/CAP/SEG 载荷 → rework；合并就绪报 `empty task payload`）
- `materialize_final_seg`：最终 `SegAnnotation` 带 `has_foreground=True`
- `rework_import_from_export` legacy export 路径：SEG 传入 `seg_manual_mask_dir` + 包图 metadata（与 M6.2 parse 要求对齐）
- 保留旧 `should_rework`（仅勾选）供对照

### Tests

- `tests/test_models.py` / `test_split_by_rework.py` / `test_parse_ls_export.py` / `test_load_current.py` / `test_validate_ready.py` / `test_apply_current_from_export.py` / `test_merge_to_final.py`

### Docs

- `README.md`：运行时分类改为 `should_rework_result`；SEG 空 mask 经 `has_foreground`

### Planned（仍未完成）

- **adapters / formats legacy 隔离**（M1 / M2 / M5.3）
- 返工语义收紧（M4.3 / M6.4）

## V1 — M5.1 空标注 rework 判定 API（2026-08-16）

### Added

- `common/models.py`：`has_effective_task_payload`（DET 非空框；CAP strip 非空文案；SEG 仅非空 `mask_ref`，空 mask 文件判定属 M5.2）
- `should_rework_result`：V1 完整规则 `(not human_confirmed) or needs_rework or (not effective_payload)`；支持 `has_task_payload` 覆盖

### Changed

- 保留旧 `should_rework`（仅勾选），供现有 `split_by_rework` 等调用至 M6.3

### Tests

- `tests/test_models.py`：载荷判定与 `should_rework_result` 用例

### Docs

- `README.md`：空标注规则 API 已落地；运行时分类仍用勾选规则（待 M6.3）

### Planned（仍未完成）

- ~~**M5.2**：SEG 空 mask 文件可表达「无有效载荷」~~ → 见上一节
- ~~**M6.3**：`split_by_rework` / refresh 接入 `should_rework_result`~~ → 见上一节（随 M5.2 一并落地）
- **adapters / formats legacy 隔离**（M1 / M2 / M5.3）
- 返工语义收紧（M4.3 / M6.4）

## V1 — M6.2 parse 只消费人工 effective（2026-08-16）

### Changed

- `exporters/parse_ls_export.py`：SEG/DET/CAP 只消费 annotation-only `EffectiveLsResult`；删除 `prediction_fallback` / `data.mask_ref` 金标准回退
- CAP 缺 `cap_text`（confirm-only）→ 空 caption；SEG 无几何 → 写空 `manual_masks/`（须 `seg_manual_mask_dir`）；空 mask 尺寸来自控件 `original_*` 或 `image_metadata_by_id`
- `apply_current_from_export`：SEG 同步传入图像 metadata（供空 mask 定尺寸）
- `extract_ls_raw_results`：文档与 annotation-only 对齐

### Tests

- `tests/test_parse_ls_export.py`：去掉 CAP/DET/SEG prediction / mask_ref 回填用例，改为 V1 空结果 / 无 predictions 可解析

### Docs

- `README.md`：parse〔现状〕与 M6.1/M6.2 对齐

### Planned（仍未完成）

- ~~**空标注 / 缺结果 → `rework/`**（M5.1 API）~~ → 见上一节；**M5.2 / M6.3** 仍待做
- **adapters / formats legacy 隔离**（M1 / M2 / M5.3）
- 返工语义收紧（M4.3 / M6.4）

## V1 — M6.1 去 prediction_fallback（2026-08-16）

### Changed

- `exporters/effective_result.py`：`resolve_effective_result` 有效结果**仅**来自 `annotation.result`；`EffectiveSource` 改为 `"annotation" | "empty"`（删除 `"prediction_fallback"`）
- confirm-only / 无任务载荷（含 `human_cleared`）→ `source="empty"`，不回填 `task["predictions"]`
- `prediction_result` 仍可追踪最新含任务控件的 prediction，但**不得**写入 `effective_result`

### Tests

- `tests/test_effective_result.py`：改写为 V1 用例（confirm-only / human-cleared / 追踪-only / parse·extract·legacy raw 均不回填 pred）

### Docs

- `README.md`：金标准来源〔现状〕改为 M6.1 已去掉 fallback；M6.2（parse 收口）等仍见 Planned

### Planned（仍未完成）

- ~~**M6.2**：`parse_ls_export` 去掉对旧 `prediction_fallback` 源分支 / SEG `mask_ref` 收口~~ → 见上一节（已落地）
- **空标注 / 缺结果 → `rework/`**（M5.1 / M6.3）
- **adapters / formats legacy 隔离**（M1 / M2 / M5.3）
- 返工语义收紧（M4.3 / M6.4）

## V1 — M3.1 / M10.1 legacy converter + CLI 语义（2026-08-16）

### Changed

- `converters/to_labelstudio.py` / `converters/__init__.py`：标记 **LEGACY**（prelabel intermediate → Label Studio，含 `predictions`；历史/对照用途）；明确**不参与** V1 首轮 `ls-import`
- 保留旧 API，未删除：`document_to_ls_tasks`、`item_to_ls_task`、`ImageMetadata`、`DEFAULT_LS_RESULT_SPECS` 等
- `cli.py`：
  - `mma convert`：help 标明 **LEGACY / not V1 main workflow**；执行失败（exit **2**）说明为 legacy stub，并提示使用 `mma ls-import`
  - `mma ls-import`：help 改为从 `task_packages` 生成 **empty** Label Studio annotation tasks（V1 manual；**no predictions**）

### Tests

- `tests/test_convert.py`：仅增加 LEGACY 文件头说明；历史 prelabel→LS API 用例逻辑不变且仍通过
- `tests/test_cli.py`：convert stub/help 断言含 `legacy` + 指向 `ls-import`；ls-import help 断言含 `empty` / `task_packages` / `prediction`，且不要求准备 prelabels

### Docs

- 本 CHANGELOG 节记录 Sprint A1 收尾（converter 定位 + CLI 文案）；业务导入逻辑未再改动（已由 M4 落地）

### Planned（仍未完成；本轮无关）

- ~~**去 `prediction_fallback`（M6.1）**~~ → 见上一节（已落地）；**M6.2** parse 收口仍待做
- **空标注 / 缺结果 → `rework/`**（M5.1 / M6.3）
- **adapters / formats legacy 隔离**；`paths.prelabels_task_dir` 主流程废弃（M1 / M2 / M5.3）
- 返工语义收紧（M4.3 / M6.4）

## V1 — M4.1 / M4.2 / M4.4 空任务导入（2026-08-16）

### Changed

- `build_ls_import_tasks`：首轮仅读 `task_packages/<batch>/<task>/manifest.json` + 包内图像；写出空 `tasks.json`（每条仅 `data.image` / `image_id` / `package_id` / `diagnosis_text`）
- 首轮导入链路**不再**调用 `load_prelabel_document`、`document_to_ls_tasks`、`validate_prelabel_coverage`；不读 `prelabels.json`
- `mma.importers` 包导出去掉 `validate_prelabel_coverage`（`validate_prelabel_coverage.py` 文件保留作 legacy 助手）

### Removed（首轮导入路径）

- 对 `prelabels/`、`predictions`、`mask_ref`、DET/SEG 预填几何的运行时依赖（转换 API 与 `ImageMetadata` 等公共工具**未删除**，仅解除首轮调用）

### Tests

- `tests/test_build_ls_tasks.py`：改写为 V1 空任务行为（无 prelabels 成功；三任务无 predictions；orphan prelabels 目录被忽略；coverage 助手保留为 legacy 单测）

### Docs

- `README.md`：首轮 `ls-import` 标为已落地；常用命令去掉「仍需 prelabels」脚注

### Planned（部分已由后续节覆盖）

- **去 `prediction_fallback`**（M6.1–M6.2）— **未删除**
- **空标注 / 缺结果 → `rework/`**（M5.1 / M6.3）— **未完成**
- **adapters / formats legacy 隔离**；`paths.prelabels_task_dir` 主流程废弃（M1 / M2 / M5.3）— **未完成**（导出/merge/mask 路径仍可能引用 prelabels）
- ~~CLI `ls-import` / `convert` 文案与 V1 对齐（M10.1 / M3.3）~~ → 见上一节（已落地）
- 返工语义收紧 M4.3 / M6.4 — **未完成**

## V1 — 文档定位草稿（2026-08-16）

本段仅记录 **V1 项目定位与文档** 变更。下列 **Planned** 中「空任务 ls-import / 覆盖校验 / CLI 文案」已由后续节落地；其余仍有效。

### Added（文档）

- README：V1 独立项目定位；纯人工金标准目标流程；与冻结 V2 的业务层差异表；〔现状〕脚注区分目标与当前实现
- `docs/data_layout.md` / `docs/labelstudio_usage.md`：主流程按 V1 目标叙述，并标明当前仍依赖 prelabels / prediction fallback 之处
- Legacy 说明：`docs/formats.md`、`examples/prelabels/`、`examples/README.md` 标为历史参考，非 V1 主流程必做

### Changed（文档）

- 主 README 快速开始不再要求「必须外部写入 prelabels」作为目标步骤；改为目标空任务导入 + 〔现状〕仍需 prelabels 的说明
- 返工预填语义在文档中强调：`previous_annotations`（人工历史）≠ 模型 / prelabel prediction（LS 字段名可能仍为 `predictions`）

### Removed（文档主路径）

- 从主流程操作说明中移除「半自动 / 外部写 prelabels 为必做」的表述（代码路径尚未移除，见 Planned）

### Tests

- 本轮**无**新增或改写业务测试；不虚构空任务导入、去 fallback、空标注 rework 等已通过的用例

### Planned（代码改造；部分已由后续节覆盖）

- ~~**空任务 `ls-import`**~~ → 见 M4 节（已落地）
- ~~**删除运行时 prelabel 覆盖校验（首轮）**~~ → 见 M4 节（已落地；文件保留）
- ~~CLI `ls-import` / `convert` 文案与 V1 对齐（M10.1 / M3.3）~~ → 见 M3.1 / M10.1 节（已落地）
- **去 `prediction_fallback`**：金标准仅来自人工 annotation（M6.1–M6.2）— **未删除**
- **空标注 / 缺结果 → `rework/`**（M5.1 / M6.3）— **未完成**
- **adapters / formats legacy 隔离**，运行时零依赖 `legacy_prelabel`（M1 / M2）— **未完成**

历史条目（2026-08-15 及更早）描述的是复制自冻结 V2 的实现演进，其中含 prelabel / prediction 行为；V1 改造落地后应在新日期段用 Added/Changed/Removed/Tests 记录真实代码变更。

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
