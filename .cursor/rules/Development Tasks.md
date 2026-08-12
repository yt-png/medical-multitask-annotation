# 开发任务

## 一、开发分期总览



|阶段|目标|对应模块|
|---|---|---|
|P0|工程骨架、数据契约、配置约定|公共层|
|P1|预处理 \+ 任务包拆分|M1、M2|
|P2|预标注统一格式 \+ 转换框架（算法暂不接）|M5|
|P3|Label Studio 三任务工作台与导入|M6|
|P4|导出、返工分类、返工覆盖|M7、M9|
|P5|三任务最终合并|M10|
|暂缓|预标注算法/大模型、网盘传输|M4、M3、M8|



---



## 二、开发任务拆分（可直接当看板用）



### P0｜工程基础（先做）



|ID|任务|交付物|依赖|
|---|---|---|---|
|T0\.1|初始化 Python 项目（依赖、README、`.gitignore`）|可安装的本地工程|\-|
|T0\.2|定义核心数据契约（图像 ID、任务包 ID、任务类型、样本/结果 schema）|`schemas/` 或 `models/`|T0\.1|
|T0\.3|约定批次/任务包/结果包目录命名与落盘规范|`docs/data_layout.md`|T0\.2|
|T0\.4|统一 CLI 入口（子命令对接各模块）|`cli.py` 或 `main.py`|T0\.1|



### P1｜预处理与任务包



|ID|任务|交付物|依赖|
|---|---|---|---|
|T1\.1|读取 jpg \+ Excel，建立图文一一对应|预处理脚本|T0\.2|
|T1\.2|为每张图生成并绑定唯一 `image_id`|ID 生成与清单输出|T1\.1|
|T1\.3|输出标准化预处理批次目录|`data/processed/<batch_id>/`|T1\.2|
|T1\.4|按 SEG/DET/CAP 生成三类全量任务包（各含 N 张图\+诊断文本）|`data/task_packages/<batch_id>/{seg,det,cap}/`|T1\.3|
|T1\.5|为每个任务包生成并绑定 `package_id`，写 `manifest.json`|任务包元数据|T1\.4|



### P2｜预标注格式统一（不含算法）



|ID|任务|交付物|依赖|
|---|---|---|---|
|T2\.1|定义 SEG/DET/CAP 的 Label Studio 预标注统一导入格式|`formats/*.json` \+ 说明|T0\.2|
|T2\.2|实现「统一中间格式 → Label Studio import JSON」转换|`converters/to_labelstudio.py`|T2\.1|
|T2\.3|预留「算法原始输出 → 统一中间格式」适配器接口（空实现/示例）|`adapters/{seg,det,cap}/`|T2\.1|
|T2\.4|提供样例预标注与转换单测/样例脚本|`examples/` \+ `tests/`|T2\.2|



> 说明：T2\.3 只做接口与目录占位，**不实现真实算法调用**。
>
> T2\.2 交付为 `converters/to_labelstudio.py` 库 API + 单测/示例；**本阶段不要求接线 `mma convert`，不以该子命令为验收项**。预标注进 Label Studio 的正式 CLI 为 **P3 `mma ls-import`**（读取 `prelabels.json` 并调用同一转换层）。`convert` 可保留为 CLI 骨架 stub。



### P3｜Label Studio 工作台与导入



|ID|任务|交付物|依赖|
|---|---|---|---|
|T3\.1|SEG 工作台 XML：原图 \+ mask \+ 原文 \+ 双 Choices（human_confirmed / needs_rework，yes\|no）|`labelstudio/configs/seg.xml`|T2\.1|
|T3\.2|DET 工作台 XML：原图 \+ bbox \+ 原文 \+ 双 Choices（human_confirmed / needs_rework，yes\|no）|`labelstudio/configs/det.xml`|T2\.1|
|T3\.3|CAP 工作台 XML：原图 \+ 预标注文本 \+ 原文 \+ 双 Choices（human_confirmed / needs_rework，yes\|no）|`labelstudio/configs/cap.xml`|T2\.1|
|T3\.4|生成可导入任务（图像路径/URL 策略按本地文件约定）|`importers/build_ls_tasks.py`|T2\.2、T3\.1–T3\.3|
|T3\.5|编写三任务导入操作说明（Label Studio 本地使用步骤）|`docs/labelstudio_usage.md`|T3\.4|



### P4｜导出、分类、返工覆盖



|ID|任务|交付物|依赖|
|---|---|---|---|
|T4\.1|解析 Label Studio 导出 JSON，提取标注与双勾选|`exporters/parse_ls_export.py`|T3\.x|
|T4\.2|按「是否返工」拆成正常包 / 返工包|`exporters/split_by_rework.py`|T4\.1|
|T4\.3|返工包再导入：保留并展示上一轮标注结果|`importers/build_rework_tasks.py`|T4\.2|
|T4\.4|**返工导出覆盖**：同 `image_id`\+任务只保留当前轮标注与当前勾选|`exporters/overwrite_current.py`|T4\.1|
|T4\.5|输出各任务当前有效结果清单（供合并使用）|`data/results/<batch_id>/<task>/current/`|T4\.4|



### P5｜最终合并



|ID|任务|交付物|依赖|
|---|---|---|---|
|T5\.1|校验三任务均无返工残留|`merge/validate_ready.py`|T4\.5|
|T5\.2|按 `image_id` 合并 SEG/DET/CAP 最终结果|`merge/merge_multitask.py`|T5\.1|
|T5\.3|缺任务阻断并报错（禁止静默缺字段）|合并校验逻辑|T5\.2|
|T5\.4|输出最终多任务数据集目录/清单|`data/final/<batch_id>/`|T5\.2|



### 明确不做（本阶段）



|ID|内容|
|---|---|
|X1|SEG/DET/CAP 真实预标注算法与大模型调用|
|X2|网盘自动上传/下载|
|X3|在线任务管理、质检看板等文档外功能|



---



## 三、推荐目录结构



```Plain Text
多任务标注平台/
├── README.md
├── requirements.txt
├── pyproject.toml                 # 可选
├── .gitignore
│
├── docs/
│   ├── requirements.md            # 已确认的需求文档
│   ├── data_layout.md             # 批次/任务包/结果包落盘规范
│   ├── formats.md                 # 统一中间格式 + LS 导入格式说明
│   └── labelstudio_usage.md       # Label Studio 操作说明
│
├── configs/
│   └── default.yaml               # 路径、批次、Excel 列名等配置
│
├── src/
│   └── mma/                       # medical multitask annotation
│       ├── __init__.py
│       ├── cli.py                 # 统一命令行入口
│       ├── common/
│       │   ├── ids.py             # image_id / package_id 生成
│       │   ├── models.py          # 数据模型/契约
│       │   ├── io.py              # 读写 json/excel/路径工具
│       │   └── paths.py           # 目录约定
│       ├── preprocess/
│       │   └── build_processed.py # M1
│       ├── packaging/
│       │   └── split_task_packages.py  # M2
│       ├── formats/
│       │   ├── intermediate.py    # 统一中间格式定义
│       │   └── labelstudio_schema.py
│       ├── adapters/              # 仅接口/示例，暂不接真实算法
│       │   ├── seg/
│       │   │   └── base.py
│       │   ├── det/
│       │   │   └── base.py
│       │   └── cap/
│       │       └── base.py
│       ├── converters/
│       │   └── to_labelstudio.py  # M5
│       ├── labelstudio/
│       │   ├── configs/
│       │   │   ├── seg.xml        # M6
│       │   │   ├── det.xml
│       │   │   └── cap.xml
│       │   └── build_tasks.py
│       ├── exporters/
│       │   ├── parse_ls_export.py # M7
│       │   ├── split_by_rework.py
│       │   └── overwrite_current.py  # M9 覆盖策略
│       ├── rework/
│       │   └── build_rework_import.py
│       └── merge/
│           ├── validate_ready.py  # M10
│           └── merge_multitask.py
│
├── examples/                      # 小样例：假数据跑通链路
│   ├── raw/
│   ├── prelabels/                 # 模拟三类预标注输入
│   └── README.md
│
├── tests/
│   ├── test_preprocess.py
│   ├── test_packaging.py
│   ├── test_convert.py
│   ├── test_split_rework.py
│   ├── test_overwrite.py
│   └── test_merge.py
│
└── data/                          # 运行时数据（gitignore）
    ├── raw/<batch_id>/
    ├── processed/<batch_id>/
    ├── task_packages/<batch_id>/{seg,det,cap}/
    ├── prelabels/<batch_id>/{seg,det,cap}/          # 人工放入算法输出
    ├── ls_import/<batch_id>/{seg,det,cap}/
    ├── ls_export/<batch_id>/{seg,det,cap}/
    ├── results/<batch_id>/{seg,det,cap}/
    │   ├── normal/
    │   ├── rework/
    │   └── current/               # 覆盖后的当前有效结果
    └── final/<batch_id>/
```



---



## 四、建议 CLI 子命令（与任务对齐）



```Plain Text
mma preprocess   --batch <id> --images <dir> --excel <file>
mma package      --batch <id>
mma convert      --batch <id> --task {seg|det|cap}   # 可选骨架；本阶段可不接线（非验收）
mma ls-import    --batch <id> --task {seg|det|cap}   # 预标注 → LS 导入任务（正式入口）
mma export-split --batch <id> --task {seg|det|cap} --export <ls_json>
mma rework-import--batch <id> --task {seg|det|cap}   # 返工再导入（带上轮结果）
mma apply-current--batch <id> --task {seg|det|cap}   # 覆盖写入 current/
mma merge        --batch <id>                        # 三任务合并
```



---



## 五、推荐开发顺序（落地顺序）



1. **P0 → P1**：先能从原始数据生成三类任务包  

2. **P2**：定死统一格式，用假预标注跑通转换  

3. **P3**：三套 Label Studio 配置可用  

4. **P4**：导出分类 \+ 返工覆盖（重点测「只保留当前轮」）  

5. **P5**：合并与缺任务校验  

6. 算法确定后，再只填 `adapters/`，不改主链路



