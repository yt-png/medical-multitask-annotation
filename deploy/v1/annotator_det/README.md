# DET 标注员包（annotator_det）

只负责 **DET** 本机标注闭环。入口强制 `--task det`；传入其他任务会失败。

禁止：`preprocess`、`package`、`merge`；禁止 SEG/CAP 配置与数据混用。  
**不**包含 `manual_masks/`（仅 SEG）。

## 环境

```bash
pip install -e .   # 仓库根
mma -h
```

Label Studio：将 [`configs/det.xml`](configs/det.xml) 粘贴到项目 Labeling Interface。  
权威配置源：`src/mma/labelstudio/configs/det.xml`。

## 流程

```text
接收 task_packages/<batch>/det/
  ↓
ls-import
  ↓
Label Studio 标注
  ↓
export-split
  ↓
rework 闭环（按需 rework-import）
  ↓
回传 current/
```

### 命令示例

```bash
python bin/ls_import.py --batch <batch> --data-root <root>
python bin/export_split.py --batch <batch> --export <export.json> --data-root <root>
python bin/rework_import.py --batch <batch> --data-root <root>
```

## 回传与交接

| 模式 | 内容 |
|---|---|
| 未完成 / 质检 | `results/<batch>/det/rework/` |
| 完成态 | `results/<batch>/det/current/` |

换人交接：`current/` + `rework/` + `task_packages/<batch>/det/`。

## 语义提醒

首轮无 prediction；返工预填 = 人工 `previous_annotations`（≠ 模型预测）。
