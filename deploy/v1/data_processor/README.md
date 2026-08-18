# 数据处理者包（data_processor）

职责：**准备任务、分发任务、收集结果、执行 merge**。

本包为薄入口，全部调用已安装的 `mma` CLI。不创建 `prelabels/`，不发送 prediction。

## 环境

```bash
# 在仓库根
pip install -e .
mma -h
```

数据根默认 `./data`（可用 `--data-root`）。目录约定见仓库 `docs/data_layout.md`。

## A. 协作主流程

```text
preprocess
  ↓
package
  ↓
网盘分发 task_packages/<batch>/{seg,det,cap}/
  ↓
收集回传：rework/（质检归档）或完成态 current/（SEG 含 manual_masks/）
  ↓
merge → final/<batch>/
```

协作时标注员日常执行 `ls-import` / `export-split` / `rework-import`；本包仍保留这些入口，供本机测试与纠错。

## B. 本机测试流程

```text
preprocess
  ↓
package
  ↓
ls-import
  ↓
（Label Studio 标注 / 或使用测试导出）
  ↓
export-split
  ↓
（有 rework 时）rework-import → 再标注 → 再 export-split
  ↓
merge
```

用于验收、纠错、单人模拟全链路。**不替代**标注员在协作中的职责。

## 命令入口

在 `data_processor/` 下：

```bash
python bin/preprocess.py --batch <batch> --images <dir> --excel <file> [--data-root data]
python bin/package.py --batch <batch> [--data-root data]
python bin/ls_import.py --batch <batch> --task seg|det|cap [--data-root data]
python bin/export_split.py --batch <batch> --task seg|det|cap --export <export.json> [--data-root data]
python bin/rework_import.py --batch <batch> --task seg|det|cap [--data-root data]
python bin/merge.py --batch <batch> [--data-root data]
```

等价于直接执行 `mma <command> ...` / `python -m mma <command> ...`。

## 禁止与边界

- **不要**准备或分发 `prelabels/`
- **不要**用 `mma convert`（V1 legacy stub，非主流程）
- 本包允许完整六命令；标注员包禁止 preprocess / package / merge
