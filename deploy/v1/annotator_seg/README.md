# SEG 标注员包（annotator_seg）

只负责 **SEG** 本机标注闭环。入口强制 `--task seg`；传入其他任务（如 `--task det`）会失败。

禁止：`preprocess`、`package`、`merge`；禁止 DET/CAP 配置与数据混用。

## 环境

```bash
pip install -e .   # 仓库根
mma -h
```

Label Studio：将 [`configs/seg.xml`](configs/seg.xml) 粘贴到项目 Labeling Interface。  
Local Files 存储根建议与 `--data-root` 一致。

权威配置源：`src/mma/labelstudio/configs/seg.xml`（改配置后请同步本包副本）。

## 流程

```text
接收 task_packages/<batch>/seg/
  ↓
ls-import          # 生成空任务（无 predictions / prelabels）
  ↓
Label Studio 标注
  ↓
export-split       # 更新 current/，重建 normal/ + rework/
  ↓
rework 闭环        # 若 rework 非空：rework-import → 再标 → 再 export-split
  ↓
回传 current/
  ↓
额外回传 manual_masks/
```

### 命令示例

```bash
python bin/ls_import.py --batch <batch> --data-root <root>
python bin/export_split.py --batch <batch> --export <export.json> --data-root <root>
python bin/rework_import.py --batch <batch> --data-root <root>
```

无需手写 `--task seg`（脚本自动注入）；若显式传入且不是 `seg`，退出码 2。

## 回传与交接

| 模式 | 内容 |
|---|---|
| 未完成 / 质检 | `results/<batch>/seg/rework/` |
| 完成态 | `results/<batch>/seg/current/` **+** `manual_masks/` |

换人交接三件套：`current/` + `rework/` + `task_packages/<batch>/seg/`。

## 语义提醒

- 首轮 `tasks.json` **无**模型 prediction
- `rework-import` 预填来自 `previous_annotations`（人工历史）；LS 字段名可能仍叫 `predictions`，**业务上不是模型预测**
