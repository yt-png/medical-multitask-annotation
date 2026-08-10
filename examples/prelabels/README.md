# 预标注中间格式样例（T2.1）

本目录模拟运行时 `data/prelabels/<batch_id>/{seg,det,cap}/` 布局，供测试与本地演示。  
**主文件名：`prelabels.json`。**

契约说明见 [docs/formats.md](../../docs/formats.md)。  
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

运行时对应位置（不入库）：

```text
data/prelabels/demo_batch/{seg,det,cap}/prelabels.json
```

端到端「假 raw → Example adapter → LS JSON」演示见上级 [examples/README.md](../README.md) 与 `examples/scripts/run_p2_demo.py`（T2.4）。
