# V1Development Specifications

# 医学图像多任务标注数据流 V1 独立版本开发规范

## 1\. 项目定位

本项目为医学图像多任务标注数据流系统 V1 独立开发版本。

V1 基于已经冻结的 V2 数据流版本进行重新构建。

V2 已完成冻结，不参与后续开发。

V2 的作用：

- 作为业务流程参考；

- 作为历史实现参考；

- 用于理解原有数据流设计。

V1 的目标：

构建一套：

> 面向医学图像金标准生产的纯人工标注数据流。
> 
> 

V1 不再依赖模型预测、预标注或自动生成结果。

---

# 2\. V1 核心目标

V1 服务于第一阶段医学图像数据生产：

医生直接对原始医学图像进行人工标注，生成高质量金标准数据。

完整流程：

```Plain Text
医学图像
 ↓
数据预处理
 ↓
任务拆包
 ↓
Label Studio人工标注
 ↓
导出标注结果
 ↓
质量检查
 ↓
normal / rework分类
 ↓
返工闭环
 ↓
多任务结果合并
 ↓
最终金标准数据
```

V1 不负责：

- 模型训练；

- 大模型推理；

- 自动预标注；

- 半自动辅助标注。

---

# 3\. V1 与 V2 的关系

## 3\.1 版本关系

V1：

```Plain Text
V2冻结版本
       |
       |
       ↓
独立复制
       |
       |
       ↓
V1重新开发
```

V2 不作为代码依赖。

禁止：

- 运行时调用 V2 文件；

- 修改 V2 文件；

- 创建 V2/V1 混合流程。

---

## 3\.2 V1 与 V2 差异

---

# 4\. V1 开发原则

## 4\.1 独立开发原则

V1 是独立项目。

允许：

- 重构目录；

- 删除无用模块；

- 简化代码；

- 优化接口；

- 调整数据结构。

不要求：

保持 V2 代码兼容。

---

## 4\.2 保持业务流程一致

虽然代码可以重构，但以下业务流程必须保持：

```Plain Text
预处理

↓

任务拆分

↓

Label Studio

↓

人工标注

↓

导出

↓

质量判断

↓

返工

↓

合并
```

---

## 4\.3 修改必须可追溯

任何功能修改必须同步更新：

```Plain Text
README.md

CHANGELOG.md

tests/
```

禁止：

只修改代码，不更新文档。

---

# 5\. V1 核心功能要求

## 5\.1 删除预标注流程

V1 不存在：

```Plain Text
prediction

prelabels

model output

adapter conversion
```

代码中禁止依赖：

```Plain Text
prelabels.json
```

或者类似预测结果文件。

---

## 5\.2 Label Studio导入

V1任务生成：

输入：

```Plain Text
task_packages/
```

输出：

```Plain Text
ls_import/
```

每个任务只包含：

```JSON
{
    "data": {
        "image": "",
        "image_id": "",
        "package_id": "",
        "diagnosis_text": ""
    }
}
```

禁止生成：

```JSON
{
    "predictions": []
}
```

---

## 5\.3 多任务拆分

每张医学图像需要生成三个独立任务：

```Plain Text
SEG

DET

CAP
```

三个任务：

- 独立任务包；

- 独立标注员；

- 独立 Label Studio 配置。

禁止：

不同任务混合。

---

# 6\. 标注结果质量规则

## 6\.1 normal规则

只有满足：

- 存在人工标注；

- 标注格式正确；

- 不需要返工；

才能进入：

```Plain Text
normal/
```

---

## 6\.2 rework规则

以下情况必须进入：

```Plain Text
rework/
```

### 情况1

Label Studio：

```Plain Text
annotation.result为空
```

### 情况2

没有对应任务标注。

例如：

SEG：

没有：

```Plain Text
seg_mask
```

DET：

没有：

```Plain Text
bbox
```

CAP：

没有：

```Plain Text
text
```

### 情况3

人工审核认为需要修改。

---

# 7\. 目录设计规范

V1 推荐结构：

```Plain Text
project_v1/

├── src/

├── configs/

├── tests/

├── docs/

├── deploy/

├── README.md

├── CHANGELOG.md

└── requirements.txt
```

---

# 8\. 角色部署规范

V1 必须提供四类部署包。

目录：

```Plain Text
deploy/v1/
```

结构：

```Plain Text
deploy/v1/

├── data_processor/

├── annotator_seg/

├── annotator_det/

└── annotator_cap/
```

---

# 9\. 数据处理者包

负责：

```Plain Text
数据准备

↓

任务生成

↓

LS导入

↓

结果下载

↓

质量检查

↓

返工处理

↓

最终合并
```

包含：

- preprocess

- package

- ls\-import

- export\-split

- rework\-import

- merge

---

# 10\. 标注员包

## SEG标注员

只包含：

- SEG Label Studio配置；

- SEG导入命令；

- SEG导出说明。

禁止包含：

- 数据预处理；

- merge；

- 其他任务配置。

---

## DET标注员

同SEG原则。

---

## CAP标注员

同SEG原则。

---

# 11\. README维护规范

README必须包含：

## 项目介绍

说明：

- V1是什么；

- 为什么开发；

- 与V2区别。

---

## 快速开始

必须提供：

安装：

```Plain Text
pip install
```

运行：

```Plain Text
python xxx
```

验证：

```Plain Text
pytest
```

---

## 数据流程说明

必须描述：

```Plain Text
input

↓

process

↓

output
```

---

## 角色说明

说明：

谁负责什么。

---

# 12\. CHANGELOG维护规范

所有版本修改必须记录。

格式：

```Plain Text
## Version X.X.X


### Added

新增功能


### Changed

修改逻辑


### Removed

删除内容


### Fixed

修复问题


### Tests

测试记录
```

---

示例：

```Plain Text
## 0.1.0

### Added

- 创建V1纯人工标注流程

### Removed

- 删除prediction依赖

### Changed

- Label Studio改为空任务导入

### Tests

- 完成SEG/DET/CAP导入测试
```

---

# 13\. Cursor代码修改流程

Cursor 在修改任何代码前必须：

## Step 1

阅读：

```Plain Text
README.md

CHANGELOG.md

相关模块代码
```

---

## Step 2

说明：

- 当前代码作用；

- 修改目标；

- 影响范围。

---

## Step 3

执行修改。

---

## Step 4

同步更新：

```Plain Text
README.md

CHANGELOG.md

tests
```

---

# 14\. 测试要求

V1发布前必须完成：

## 基础流程测试

```Plain Text
图片输入

↓

预处理

↓

任务生成

↓

LS导入

↓

人工标注

↓

导出

↓

分类

↓

返工

↓

合并
```

---

## 必测场景

### 场景1

正常标注：

结果：

```Plain Text
normal
```

---

### 场景2

空标注：

结果：

```Plain Text
rework
```

---

### 场景3

无预测文件：

系统正常运行。

---

### 场景4

SEG/DET/CAP独立运行。

---

# 15\. Cursor禁止行为

禁止：

1. 未阅读代码直接重构；

2. 修改业务流程但不说明；

3. 删除重要模块但不记录；

4. 添加无必要依赖；

5. 修改数据格式但不更新文档；

6. 只实现代码，不补README和CHANGELOG。

---

# 16\. V1冻结标准

V1达到以下条件后冻结：

- 完成纯人工标注流程；

- 无预标注依赖；

- LS空任务导入正常；

- SEG/DET/CAP三任务独立运行；

- 空标注自动进入rework；

- 返工闭环完成；

- README完整；

- CHANGELOG完整；

- 测试通过。

最终状态：

```Plain Text
Medical Annotation Dataflow V1 Frozen
```

---



