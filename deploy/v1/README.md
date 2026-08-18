# V1 四角色部署包（deploy/v1）

本目录是 **Sprint D / M11** 交付的薄包装层：不复制 `src/mma` 业务代码，所有命令通过已安装的 **`mma` CLI**（或 `python -m mma`）调用。

V1 **不使用** `prelabels/`、model prediction、legacy adapter。首轮导入为空任务；返工预填来自人工 `previous_annotations`（业务上 ≠ 模型预测）。

## 角色一览

| 角色目录 | 职责 | 允许的 CLI |
|---|---|---|
| [`data_processor/`](data_processor/) | 准备 / 分发 / 收集 / 合并；本机可跑全流程 | preprocess, package, ls-import, export-split, rework-import, merge |
| [`annotator_seg/`](annotator_seg/) | SEG 本机标注闭环 | ls-import, export-split, rework-import（强制 `--task seg`） |
| [`annotator_det/`](annotator_det/) | DET 本机标注闭环 | 同上（强制 `--task det`） |
| [`annotator_cap/`](annotator_cap/) | CAP 本机标注闭环 | 同上（强制 `--task cap`） |

## 环境前置

在仓库根目录：

```bash
pip install -e .
mma -h
```

角色包本身不含业务实现，依赖上述已安装的 `mma`。

## 分发约定

- 只向标注员分发：`task_packages/<batch>/<task>/`（含 `manifest.json` 与 `images/`）
- **不**分发 `prelabels/`、**不**发送 prediction / 模型预标注

## 回传约定（双模式）

| 模式 | 回传内容 |
|---|---|
| 未完成 / 交接质检 | `results/<batch>/<task>/rework/` |
| 完成态 | `results/<batch>/<task>/current/`；SEG 另附 `manual_masks/` |

数据处理者收集三路完成态 `current/`（及 SEG masks）后执行 `merge`。

## 换人交接三件套

1. `results/.../current/`
2. `results/.../rework/`
3. 对应 `task_packages/<batch>/<task>/`

## 处理者本机全流程测试

见 [`data_processor/README.md`](data_processor/README.md) 路径 B（本机测试流程）。协作主路径中部分步骤由标注员日常执行，但处理者包仍保留完整六命令入口。

## 清单

见同目录 [`manifest.json`](manifest.json)（sprint=D，M11.1–M11.5）。
