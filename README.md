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

运行时依赖见 `requirements.txt`（`openpyxl` 读诊断 Excel；`Pillow` / `numpy` / `opencv-python-headless` 用于 SEG mask 叠图预填与人工 brush/polygon 解码落盘）。

**运行约定（配置内嵌）**：无根目录 `configs/default.yaml`。默认数据根为 `./data`（可用 `--data-root`）；诊断 Excel 为 `.xlsx`，首表列名 `image_name` / `diagnosis_text`（见 `mma.common.io`）。目录规范见 [docs/data_layout.md](docs/data_layout.md)。

## CLI

安装后可使用：

```bash
mma -h
python -m mma -h
```

已注册子命令：`preprocess`、`package`、`ls-import`、`export-split`、`rework-import`、`apply-current`、`merge` 已接线；`convert` 仍为骨架 stub。**正式入口为 `mma ls-import`；`convert` 非本阶段验收项。**

`preprocess` · `package` · `convert` · `ls-import` · `export-split` · `rework-import` · `apply-current` · `merge`

预处理与任务包示例：

```bash
mma preprocess --batch demo_batch --images examples/raw/demo_batch/images --excel examples/raw/demo_batch/diagnoses.xlsx --data-root data
mma package --batch demo_batch --data-root data
```

- `preprocess`：写出 `data/processed/<batch_id>/manifest.json`（引用原图，不复制）
- `package`：复制三类全量图像并写出各任务包 `manifest.json`（含 `package_id`）

生成 Label Studio 导入任务（需已有 `prelabels/` 与 `task_packages/` 图像）：

```bash
mma ls-import --batch demo_batch --task seg --data-root data
```

- 写出 `data/ls_import/<batch>/<task>/tasks.json`
- `data.image` 使用 `/data/local-files/?d=task_packages/...`（可用 `--local-root` 覆盖相对根）
- SEG 默认启用 prelabels 目录为 `mask_root` 以叠图预填（默认 **polygonlabels**；可选 brush RLE）
- **覆盖校验**：任务包 `manifest.json` 的 `image_id` 集合必须与 `prelabels.json` 完全一致；缺样本报 `Missing prelabels`，多余报 `Unknown prelabels`（不静默跳过）

覆盖写入当前有效结果（P4）。**职责澄清（二选一，勿对同一 export 连跑两条）**：

| 命令 | 角色 |
|------|------|
| `apply-current` | **底层**：export → merge `current/`（实现上也会刷新 normal/rework） |
| `export-split` | **高级封装**：内部调用 apply-current，并打印/返回 `normal/`、`rework/` 路径 |

日常「导出后分类落盘」用 `export-split` 即可；仅在只要同步 `current/`、不关心命令行打印的两路路径时用 `apply-current`。

```bash
# 推荐：一条命令完成 current 同步 + normal/rework 重建
# 建议按轮次目录存放：.../round_001/export.json（export_round 会写入 current）
mma export-split --batch demo_batch --task cap --export data/ls_export/demo_batch/cap/round_001/export.json --data-root data
```

```bash
# 底层等价入口（勿再紧跟 export-split）
mma apply-current --batch demo_batch --task cap --export data/ls_export/demo_batch/cap/round_001/export.json --data-root data
```

- 解析导出（含仍需返工样本）并覆盖写入 `data/results/<batch>/<task>/current/annotations.json`
- 若 `--export` 父目录为 `round_NNN`（如 `round_001`），则 `TaskAnnotationResult.export_round` 记为整数轮次（`1`）；非轮次目录仍为 `null`（仅追溯，不影响分类/合并）
- 按 `image_id` **合并**写入：命中则覆盖；**未出现在本轮 export 中的样本保留**（非整表清空）
- 写入后**自动全量重建**同任务 `normal/` 与 `rework/`（以 `current/` 为唯一真实源，禁止按本轮 export 子集追加历史）
- 首轮/全量刷新：请导出该任务本批全部样本后再 apply / export-split；返工轮允许子集 export（详见 `docs/data_layout.md`、`docs/labelstudio_usage.md`）
- DET 从 `task_packages/.../images/` 读取图像尺寸做百分比→像素换算
- **DET**：三态解析（与 SEG 的 `annotation.prediction` 语义对齐）。`annotation` 有 `det_bbox` → 用人框；无框但 `annotation.prediction` 非空 → 空框（接受预标注后删光）；无框且无 prediction 链接 → 回退 `task.predictions` 预标注框（未操作不丢预标注）
- **SEG**：人工结果优先。若 annotation 有 SEG 操作记录（`from_name=seg_mask` 条目，或 `annotation.prediction` 表明从预标注接受过），则写出 `data/results/<batch>/seg/manual_masks/<image_id>_manual.png`（支持 **polygonlabels 百分比点** 与历史 **brushlabels RLE**；**删光几何则写全空 mask**），`mask_ref` 为 `manual_masks/<image_id>_manual.png`。若无 SEG 操作记录，才回退导出里的 `data.mask_ref`（预标注）。不覆盖 `prelabels/.../masks/`。
- **CAP**：人工结果优先。`annotation.result` 有 `cap_text` → 用人改文本（**空串表示人工清空**）；无 `cap_text` → 回退 `task.predictions[-1].result` 预标注；两边皆无则报错。`current/` 允许持久化空 caption。
- **分类**（相对最新 current）：`should_rework = (not human_confirmed) or needs_rework`；仅确认且不需返工进 normal；**rework = 未达最终确认状态**
- **SEG** normal/rework 与 current 的 `mask_ref` 一致（含 `manual_masks/`）

生成返工再导入任务（P4，可见上一轮标注、不预填双勾选）：

```bash
# 推荐：rework 包已含 previous_annotations 时无需 --export
mma rework-import --batch demo_batch --task cap --data-root data

# 旧包兼容：无 previous_annotations 时仍可用 --export
mma rework-import --batch demo_batch --task cap --export data/ls_export/demo_batch/cap/export.json --data-root data
```

- 写出 `data/ls_import/<batch>/<task>/rework_tasks.json`（不覆盖首轮 `tasks.json`；无返工样本时为 `[]`）
- **优先**读 `results/.../rework/previous_annotations/<task>.json`（及 SEG `masks/`）构造 LS `predictions`；该快照由 `apply-current` / `export-split` 与 rework 包一并生成
- 「自包含」仅指标注快照可脱离原始 LS export；**原图仍取自** `task_packages/<batch>/<task>/images/`（与首轮 `ls-import` 相同）
- 无快照时回退 `--export`：**effective result** 旁路（`resolve_effective_result`）。仅勾选 `human_confirmed`、未 Accept 预标注时，仍从 `task.predictions` 带回几何/文本；人工清空（`annotation.prediction` 有值且无任务控件）不回退

三任务合并写出最终集（P5，需三路 `current/` 就绪且 `processed` 可回填图文）：

```bash
mma merge --batch demo_batch --data-root data
```

- 写出 `data/final/<batch>/manifest.json`（`{batch_id, items}`，每条含 SEG+DET+CAP 与 `image_path`/`diagnosis_text`）
- 写盘前将 SEG mask **复制**到 `final/<batch>/final_assets/masks/{image_id}.png`；清单中 `seg.mask_ref` 统一为 `final_assets/masks/{image_id}.png`（相对该 final 批次目录；空 mask 只复制不重生成）
- 未就绪或缺任务时失败且不改写已有 final

预标注 → Label Studio import（T2.2 / T3.1b，Python API，CLI `convert` 仍为 stub）：

```python
from pathlib import Path
from mma.converters import ImageMetadata, document_to_ls_tasks
from mma.formats import load_prelabel_document

doc = load_prelabel_document("examples/prelabels/demo_batch/seg/prelabels.json")
tasks = document_to_ls_tasks(doc)  # 无 mask_root：result 为空（兼容 T2.2）
# SEG 叠图预填（默认 polygonlabels）：传入含 masks/ 的 prelabels 任务目录
# tasks = document_to_ls_tasks(doc, mask_root=Path("data/prelabels/demo_batch/seg"))
# 历史 brush RLE：document_to_ls_tasks(..., mask_root=..., seg_prefill_mode="brush")
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
- 已完成：T3.1 SEG Label Studio 工作台 XML（`src/mma/labelstudio/configs/seg.xml`，`PolygonLabels`）
- 已完成：T3.1b SEG 叠图预填（`mask_root` → 默认 polygonlabels；`SEG_PREFILL_MODE=brush` 保留 RLE；无 `mask_root` 仍空 result）
- 已完成：T3.2 DET Label Studio 工作台 XML（`src/mma/labelstudio/configs/det.xml`）
- 已完成：T3.3 CAP Label Studio 工作台 XML（`src/mma/labelstudio/configs/cap.xml`）
- 已完成：T3.4 生成 LS 导入任务（`importers/build_ls_tasks.py`、`mma ls-import`、local-files URL）
- 已完成：T3.5 Label Studio 本地使用说明（`docs/labelstudio_usage.md`）
- 已完成：T4.1 LS 导出解析 → `TaskAnnotationResult`（`exporters/parse_ls_export.py`）
- 已完成：T4.2 按 `should_rework` 拆分 normal/rework（`exporters/split_by_rework.py`；统一函数 `models.should_rework`；与 Requirement Spec 7.7 / `data_layout` 对齐：rework=未达最终确认）
- 已完成：T4.3 返工再导入（优先 `rework/previous_annotations/` 标注快照；旧模式 `--export` 经 `resolve_effective_result` / `extract_ls_raw_results` → `importers/build_rework_tasks.py`；原图仍依赖 `task_packages`）
- 已完成：`resolve_effective_result`（人工 payload 优先；仅 Choices 时 prediction fallback；人工清空不回退；confirm-only 打 warning）
- 已完成：接线 `mma apply-current`（底层：export → current）与 `mma export-split`（高级封装：调用 apply-current 并返回 normal/rework；**勿对同一 export 连跑两条**）
- 已完成：`export_round` 追溯字段接线（`parse_export_round_from_path`：`round_001`→`1`；`apply-current`/`export-split` 写入 `current/`；不改分类/合并逻辑）
- 已完成：接线 `mma rework-import --batch --task [--export] [--data-root] [--local-root]`（`importers/rework_import_from_export.py` → `rework_tasks.json`）
- 已完成：rework 包标注快照 `previous_annotations/<task>.json`（+ SEG `masks/`；`write_normal_rework_bundles`；不含原图）
- 已完成：T4.5 读取 current 清单（`exporters/load_current.py` + `current_annotations` 序列化；供 P5 merge）
- 已完成：T5.1 合并就绪校验（`merge/validate_ready.py`：无返工、全确认、三路 `image_id` 一致）
- 已完成：T5.2 按 `image_id` 合并（`merge/merge_multitask.py` → `MergedMultitaskRecord`；含缺任务防御）
- 已完成：T5.3 缺任务阻断（`assert_no_missing_tasks`：禁止静默缺字段；合并二次校验）
- 已完成：T5.4 输出 `final/` 与接线 `mma merge --batch [--data-root]`（`merge/merge_to_final.py` + `write_final.py`）
- 已完成：final SEG mask 统一物化到 `final/<batch>/final_assets/masks/`（`merge/materialize_final_seg.py`；contract 禁止 `masks/`/`manual_masks/`/`prelabels/`）
- 已完成：SEG 人工几何 → `results/.../seg/manual_masks/` 持久化（polygon + 历史 brush；删光写空 mask；无 SEG 操作才回退 `data.mask_ref`；`apply-current` / `export-split`）
- 已完成：CAP 导出三态解析（人改文本 / 人工清空为空串 / 无 cap_text 回退 `predictions[-1]`；`current` 允许空 caption）
- 已完成：DET 导出三态解析（人框 / 接受后删光为空 / 未操作回退 `predictions`；`parse_ls_export`）
- 已完成：`apply-current` / `export-split` 以 `current/` 为源全量刷新 normal/rework（多轮返工后 normal 反映最新无需返工全集）

## 文档

- 数据目录与落盘约定：[docs/data_layout.md](docs/data_layout.md)
- 预标注统一中间格式与 SEG/DET/CAP 工作台控制名对齐：[docs/formats.md](docs/formats.md)
- Label Studio 本地导入与标注操作：[docs/labelstudio_usage.md](docs/labelstudio_usage.md)
- real_batch 本地真实数据全链路测试手册：[docs/real_batch_local_test_runbook.md](docs/real_batch_local_test_runbook.md)

## 开发说明

请遵循项目规则与需求文档（`.cursor/rules/`）。功能分支开发；提交前由开发者本地运行检查后再 `git commit`。
