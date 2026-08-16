# V1Requirement Specifications

# 数据流 V1 需求说明

## 一句话目标

基于已冻结的 V2 半自动标注数据流版本，重新构建一套 **V1 纯人工金标准注数据流系统**：

去除预标注、模型预测等半自动流程，让医生直接在 Label Studio 上对原始医学图像进行人工标注，生成后续模型训练所需的高质量金标准数据。

V2 已冻结，仅作为历史版本和业务流程参考，V1 为独立开发版本。

---

# 一、业务背景（为什么需要 V1）

当前医学图像标注流程分为两个阶段：

V1 的核心任务：

建立一套稳定、可重复部署的人工金标准生产流程，为后续模型训练和半自动标注提供高质量数据基础。

---

# 二、V1 与 V2 的关系

## 2\.1 版本关系

V1 基于冻结版本 V2 的业务流程和设计经验重新构建。

关系如下：

```Plain Text
V2冻结版本
    |
    |
    ↓
复制基础代码与业务逻辑
    |
    |
    ↓
独立开发 V1
```

V2：

- 已冻结；

- 不参与 V1 运行；

- 不作为 V1 依赖；

- 不进行修改。

V1：

- 独立项目；

- 独立目录；

- 根据纯人工标注需求进行优化和调整。

---

# 三、V1 核心目标

V1 面向第一阶段医学图像金标准生产。

目标：

实现：

```Plain Text
医学图像输入

↓

数据预处理

↓

任务拆分

↓

Label Studio人工标注

↓

结果导出

↓

质量检查

↓

normal/rework分类

↓

返工闭环

↓

多任务结果合并

↓

最终金标准数据
```

---

# 四、V1 与 V2 的核心差异

V1 与 V2 的主要区别包括：

## 删除预标注流程

V1 不包含：

- 模型预测；

- 大模型推理；

- prediction结果；

- prelabels文件；

- 自动生成标注。

任务包生成后：

直接生成 Label Studio 导入文件。

流程：

```Plain Text
任务包

↓

ls_import

↓

人工标注
```

不经过任何算法预标注。

---

## 增加空标注返工规则

在原有：

```Plain Text
normal/
rework/
```

分类基础上增加规则：

如果 Label Studio 导出结果：

- 没有任何人工标注；

- result为空；

- 缺少对应任务结果；

统一进入：

```Plain Text
rework/
```

视为必须返工。

---

# 五、端到端业务流程

## 5.1 协作主路径

完整 V1 协作流程：

```Plain Text
数据预处理

↓

按照 SEG / DET / CAP 分别生成任务包

↓

网盘只分发 task_packages/<batch>/<task>/

↓

标注员本机 ls-import

↓

配置 Label Studio → 导入 → 工作台人工标注 → 导出

↓

标注员本机 export-split

↓

若存在 rework 样本：rework-import → 再导入 LS → …（标注员本机闭环至 rework 为空）

↓

网盘回传：
  · 进行中 / 换人交接：仅 results/<batch>/<task>/rework/
  · 本任务完成：current/（SEG 另含 manual_masks/）

↓

数据处理者收齐三任务「已无需返工」的最新 current/

↓

SEG + DET + CAP 结果合并

↓

生成最终金标准数据
```

回传约定：

- 完成包：merge 以标注员回传的 `current/` 为准；`normal/` 不要求回传；SEG 完成包 = `current/` + `manual_masks/`。
- `rework/` 回传用于换人交接或质检归档；协作主路径下数据处理者不介入标注员中间轮次返工编排。

## 5.2 本机全流程测试（数据处理者）

数据处理者可在本机独立跑通整套项目完整运行流程（不依赖三名标注员在场），用于测试 / 验收 / 纠错：

```Plain Text
preprocess → package → ls-import → export-split
  →（按需）rework-import → … → merge
```

本路径与协作主路径并行存在，**不替代**标注员职责。

---

# 六、角色划分

V1 共包含四类角色。

## 数据处理者

### 协作主路径

- 数据预处理；
- 任务包生成；
- 网盘分发（仅 `task_packages/<batch>/<task>/`）；
- 收集回传：`rework/` 仅质检归档；完成态收集三任务 `current/`（SEG 含随附 `manual_masks/`）；
- 三任务 current 就绪后最终合并（merge）。

### 本机全流程测试

- 须能在本地执行整套项目完整运行流程（含：`preprocess`、`package`、`ls-import`、`export-split`、`rework-import`、`merge`）；
- 用于测试 / 验收 / 纠错；可单人模拟标注前后数据步骤。
- 协作主路径中部分步骤由标注员日常执行，但数据处理者包**不得因此删减**上述完整 CLI 能力。

---

## SEG标注员

负责：

- 下载 SEG `task_packages/`；
- 本机执行本任务 `ls-import`；
- 配置 Label Studio、导入、人工分割标注、导出；
- 本机 `export-split`；仅当存在 rework 样本时再执行 `rework-import`，本机闭环直至 rework 为空；
- 网盘回传：`rework/`（交接/未完成）或完成态 `current/` + `manual_masks/`；
- 换人须交接：`current/` + `rework/` + 任务包。

禁止：

- `preprocess`、`package`、`merge`；
- 其他任务（DET/CAP）配置与数据。

---

## DET标注员

负责：

- 下载 DET `task_packages/`；
- 本机执行本任务 `ls-import`；
- 配置 Label Studio、导入、目标检测标注、导出；
- 本机 `export-split`；仅当存在 rework 样本时再执行 `rework-import`，本机闭环直至 rework 为空；
- 网盘回传：`rework/`（交接/未完成）或完成态 `current/`；
- 换人须交接：`current/` + `rework/` + 任务包。

禁止：

- `preprocess`、`package`、`merge`；
- 其他任务（SEG/CAP）配置与数据。

---

## CAP标注员

负责：

- 下载 CAP `task_packages/`；
- 本机执行本任务 `ls-import`；
- 配置 Label Studio、导入、文本描述标注、导出；
- 本机 `export-split`；仅当存在 rework 样本时再执行 `rework-import`，本机闭环直至 rework 为空；
- 网盘回传：`rework/`（交接/未完成）或完成态 `current/`；
- 换人须交接：`current/` + `rework/` + 任务包。

禁止：

- `preprocess`、`package`、`merge`；
- 其他任务（SEG/DET）配置与数据。

---

# 七、多任务拆分规则

每张医学图像对应三个独立任务：

```Plain Text
SEG

DET

CAP
```

要求：

- 三个任务独立生成；

- 三个任务独立分发；

- 三类标注员互不混用。

---

# 八、V1 功能模块设计

---

# 九、V1 开发约束

## 独立开发

V1 为独立项目。

允许：

- 调整目录结构；

- 优化代码组织；

- 删除无用模块；

- 重构内部实现。

不要求：

保持 V2 代码接口兼容。

---

## 保持业务逻辑一致

虽然代码可以优化，但必须保持核心数据流程：

```Plain Text
预处理

↓

任务生成

↓

人工标注

↓

结果检查

↓

返工

↓

合并
```

---

## 开发过程必须可追溯

所有功能修改必须同步维护：

- README\.md

- CHANGELOG\.md

- tests/

每一次重要修改必须记录：

- 修改原因；

- 修改内容；

- 影响范围；

- 测试结果。

---

# 十、交付物要求

V1 最终需要提供：

## V1完整数据流代码

包含：

- 数据处理流程；

- Label Studio交互；

- 导出处理；

- 返工闭环；

- 数据合并。

---

## 四角色部署包

目录：

```Plain Text
deploy/v1/

├── data_processor/

├── annotator_seg/

├── annotator_det/

└── annotator_cap/
```

要求：

每个角色：

- 独立运行；

- 只包含自身需要内容；

- 有独立README和操作说明。

部署边界：

- `data_processor`：须具备完整运行流程所需入口与说明（本机全流程测试可单包跑通）；文档区分协作主路径与本机测试路径。
- `annotator_seg` / `annotator_det` / `annotator_cap`：裁剪入口，仅暴露本任务允许子命令（`ls-import`、`export-split`、`rework-import`）+ 本任务 LS 配置与操作说明；禁止 `preprocess` / `package` / `merge` 与他任务。

---

## 操作流程文档

包含：

- 环境部署；

- 数据目录说明；

- 命令使用方式；

- 常见问题。

---

# 十一、V1最终验收标准

满足以下条件：

1. 可以完成纯人工医学图像标注流程；

2. Label Studio无需任何prediction或prelabel输入；

3. SEG/DET/CAP三个任务独立运行；

4. 空标注自动进入rework；

5. 返工流程完整闭环；

6. 最终可以生成多任务金标准数据；

7. README完整；

8. CHANGELOG完整；

9. 测试通过。

最终状态：

```Plain Text
Medical Image Multi-task Annotation Dataflow V1 Frozen
```

