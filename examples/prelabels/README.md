# LEGACY — 预标注中间格式样例

> **非 V1 主流程必做。** 本目录模拟历史运行时 `data/prelabels/<batch_id>/{seg,det,cap}/` 布局，供冻结 V2 对照、既有单测与本地 Legacy 演示。  
> V1 目标：纯人工金标准，**不要求**准备本目录即可完成目标主流程（代码改造见 CHANGELOG Planned / M4）。  
> **〔现状〕**：当前 `mma ls-import` 仍可能依赖此类文件。

**主文件名：`prelabels.json`。**

契约说明见 [docs/formats.md](../../docs/formats.md)（已标 Legacy）。  
包内同构样例：`src/mma/formats/{seg,det,cap}.json`。

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

Legacy 端到端「假 raw → Example adapter → LS JSON」演示见上级 [examples/README.md](../README.md) 与 `examples/scripts/run_p2_demo.py`。
