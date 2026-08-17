# LEGACY — 预标注中间格式样例

> **非 V1 主流程。** 本目录模拟历史运行时 `data/prelabels/<batch_id>/{seg,det,cap}/` 布局，供冻结 V2 对照、既有单测与本地 Legacy 演示。  
> **not part of V1 runtime.** V1 首轮导入使用 `task_packages` + `mma ls-import`，**不要求**准备本目录。

**主文件名：`prelabels.json`。**

契约说明见 [docs/formats.md](../../docs/formats.md)（已标 Legacy）。  
包内同构样例：`src/mma/formats/legacy_prelabel/{seg,det,cap}.json`。

## `demo_batch/`

```text
demo_batch/
├── seg/
│   ├── prelabels.json
│   └── masks/                 # mask_ref 指向的占位文件
│       ├── demo_batch__000001.png
│       └── demo_batch__000002.png
├── det/
│   └── prelabels.json
└── cap/
    └── prelabels.json
```

关联键为 `image_id`；`image_path` 仅为可选辅助字段，不绑定 `task_packages` 路径。

历史运行时对应位置（不入库）：

```text
data/prelabels/demo_batch/{seg,det,cap}/prelabels.json
```

Legacy 端到端演示见上级 [examples/README.md](../README.md) § Legacy Examples 与 `examples/scripts/run_p2_demo.py`。
