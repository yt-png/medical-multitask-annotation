# V1 Development Tasks



> **定位**：V1 是基于 **V2 冻结版本复制** 后的**独立项目**。允许内部重构与目录调整，**不要求**与 V2 代码兼容；**必须**保持端到端业务流程一致，并用 README / CHANGELOG / tests 保持可追溯。  
> 
> **目标**：纯人工金标准注（无模型预标注 / 无 prediction 回退为金标准）\+ 空标注进 rework \+ 四角色交付。  
> 
> **用法**：可直接按 Phase 交给 Cursor Agent 逐条执行；每条完成后同步文档与测试。
> 
> 



---



## 0\. 开发原则（Agent 必读）



|原则|含义|
|---|---|
|独立重构|可删改 V1 内实现、接口、目录；不讨论「保护 V2 / 分支兼容」|
|流程不变|预处理 → 拆包 → LS 导入 → 人工标注 → 导出 → normal/rework → 返工 → 合并|
|可追溯|每个 Phase 结束更新 README \+ CHANGELOG \+ 对应 tests|
|扩展友好|预标注能力**隔离为 legacy**，不从主链路硬删历史参考（见 M1/M2）|
|语义分离|`previous_annotations`（人工历史）≠ 模型 / prelabel `prediction`|



---



## 1\. Phase 总览与推荐执行顺序



```Plain Text
Phase A  核心数据流改造     ← 先做（阻塞 V1 成立）
Phase B  数据结构与路径清理
Phase C  返工闭环验证
Phase D  交付工程化（含 deploy 提前穿插）
```



|Phase|目标|主要任务 ID|建议 Agent 顺序|
|---|---|---|---|
|**A**|空任务导入 \+ 去 prelabel 主依赖 \+ 去 prediction\_fallback \+ 空标注→rework|M4\.1–M4\.4, M3\.1, M6\.1–M6\.3, M5\.1–M5\.2, M10\.1|M4 → M3\.1 → M6 → M5 → 单测|
|**B**|运行时零依赖 `prelabels/`；formats/adapters 隔离|M1\.\*, M2\.\*, M5\.3–M5\.6, M3\.2–M3\.4, M7\.\*, M10\.2|M1/M2 → M5 路径 → M3 收尾 → M7|
|**C**|返工语义正确；merge 无隐式预标注依赖|M4\.3, M6\.4–M6\.5, M8\.\*, M12\.1–M12\.5|rework → merge → 端到端|
|**D**|四角色包 \+ 文档冻结 \+ 全量测试|M11\.\*, M0\.\*, M12\.6, M9\.\*|**M11 可与 C 并行提前**；最后 M0 \+ 冻结|



**风险提示（全局）**



- 先改 `build_ls_tasks` 再改判定规则，避免「空任务已导入但仍用 prediction 填金标准」。

- 返工仍可能向 LS 写入 `predictions` 字段承载**上一轮人工结果**：导出侧**禁止**再走 `prediction_fallback` 当最终结果。

- 隔离 legacy 时保留 import 边界清晰，避免 `cli` / `importers` 误引用。

- 每 Phase 未更新 CHANGELOG/README 不得进入下一 Phase。

    

---



## 2\. 模块任务明细（保留 M0–M12）



---



### M0 · 项目定位与文档（横切，主要落在 Phase D；A/B 可写草稿条目）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M0\.1**|README 改为 V1 独立项目叙述：纯人工流程；去掉「外部写 prelabels / 半自动」操作步骤|`README.md`|可追溯与上手路径必须与代码一致|快速开始可从 preprocess→package→ls\-import（无 prelabels）跑通；写明与冻结 V2 的差异（业务层，非代码兼容）|
|**M0\.2**|CHANGELOG 增加 V1 版本段：Added/Changed/Removed/Tests|`CHANGELOG.md`|规范要求每次重要修改可追溯|含空任务导入、去 fallback、空标注 rework、legacy 隔离说明|
|**M0\.3**|`docs/data_layout.md`：运行时目录不再依赖 `prelabels/`；标注 legacy 目录（若保留）|`docs/data_layout.md`|路径约定与 Phase B 一致|文档中主流程图无 prelabel 步骤|
|**M0\.4**|`docs/labelstudio_usage.md`：首轮空任务导入；返工「人工历史预填」说明|`docs/labelstudio_usage.md`|角色操作正确|明确：首轮无 predictions；返工预填≠模型预测|
|**M0\.5**|`docs/formats.md` / `examples/prelabels/`：迁入 legacy 说明或标历史参考，不作为主流程|`docs/`、`examples/`|避免新人误用|主 README 不链到「必须准备 prelabels」|



---



### M1 · `adapters/`（Phase B｜隔离，不硬删）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M1\.1**|**隔离**预标注 adapter：停止 V1 主流程调用；移出运行时路径（如 `src/mma/legacy/adapters/` 或同等）；代码/包级标记 **legacy**|`src/mma/adapters/**` → legacy 落点；`adapters/__init__.py` 导出策略|当前服务预标注，但未来可能复用任务抽象 / LS 转换 / 返工；硬删损害扩展|`mma` CLI 与 `importers`/`exporters`/`merge` **不 import** 运行时 adapters；grep 主链路无引用|
|**M1\.2**|测试：主流程测试不依赖 adapter；legacy 测试可迁到 `tests/legacy/` 或标记 skip/optional|`tests/test_adapters.py`|主 CI 验证 V1 路径|默认 `pytest` 不因 legacy adapter 失败；文档注明历史参考用途|
|**M1\.3**|CHANGELOG 记录「隔离预标注 adapter，不参与 V1 运行链路」|`CHANGELOG.md`|可追溯|Removed/Changed 写清「隔离」而非「业务能力永久废弃」|



**任务一句话**：隔离预标注 adapter，不参与 V1 运行链路。



---



### M2 · `formats/`（Phase B｜拆分，不整包删除）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M2\.1**|拆分 formats 职责，推荐结构：`task_schema` / `annotation_schema` / `legacy_prelabel`（目录名可微调，语义必须三分）|`src/mma/formats/**`|整删会丢掉 task/annotation schema；只需去掉运行时 prelabel 依赖|新代码按三分组织；`PrelabelDocument` 等仅在 `legacy_prelabel`|
|**M2\.2**|运行时路径（`ls-import`、export、merge）**零依赖** `legacy_prelabel`|`importers`、`cli`、`formats/__init__.py`|V1 禁止 prelabels\.json|主流程 import 图不含 legacy\_prelabel|
|**M2\.3**|保留历史格式定义与简短 README/注释：用途=历史参考|`formats/legacy_prelabel/`|长期维护与对照 V2 设计|文件仍可读；非安装必需依赖|
|**M2\.4**|更新 `tests/test_formats.py`：主测 schema；prelabel 用例迁 legacy|`tests/`|与拆分一致|默认测试覆盖 V1 schema；legacy 可选|



---



### M3 · `converters/`（Phase A 核心 \+ Phase B 收尾）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M3\.1**|首轮 LS 任务构建**不再**走「prelabel → predictions」转换；与 M4\.1 对接（空 `data` only）|`converters/to_labelstudio.py`、调用方|V1 不需要模型/prelabel prediction|首轮 tasks\.json **无** `predictions` 键（或恒为空且不被写入）|
|**M3\.2**|**保留**几何/控件编码能力，供 **previous\_annotations → 返工预填** 使用；文档与函数命名区分「人工历史预填」vs「模型预测」|`seg_brush.py`、`seg_polygon.py`、`to_labelstudio.py`、`previous_annotations.py`|返工需展示上一轮人工结果；**previous\_annotations ≠ prediction（业务语义）**|返工可预填；注释/README 明确语义；导出金标准不依赖该预填|
|**M3\.3**|CLI `convert`：移除或改为明确失败（V1 已移除 prelabel 转换）|`cli.py`|避免误导|`mma convert` 不再暗示可生成 prelabel 导入|
|**M3\.4**|清理/改写依赖 prelabel 转换的演示与测试|`tests/test_convert.py`、`test_p2_*`、`examples/scripts/run_p2_demo.py`|与 Phase A/B 一致|无「必须先写 prelabels」的默认演示|



**禁止**：model prediction / prelabel prediction 进入首轮与金标准路径。  

**可保留**：基于 `previous_annotations` 的返工预填编码。



---



### M4 · `importers/`（Phase A 最大改动点 \+ Phase C 返工）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M4\.1**|**重写** `build_ls_import_tasks`：输入仅 `task_packages/`；输出每条任务**仅**含 `data`：`image`、`image_id`、`package_id`、`diagnosis_text`；**禁止** `predictions`|`importers/build_ls_tasks.py`|V1 最大改动点；纯人工首轮|无 `prelabels.json` 仍成功；tasks 无 predictions；字段齐全|
|**M4\.2**|**删除运行时使用** `validate_prelabel_coverage`（实现可迁 legacy 或删除调用链）|`importers/validate_prelabel_coverage.py`、`importers/__init__.py`|V1 无 prelabel 覆盖校验|主链路无该函数调用|
|**M4\.3**|`build_rework_tasks`：预填源仅 `previous_annotations`（人工历史）；禁止依赖 model/prelabel；文档写明 LS 字段名可能仍叫 predictions，**业务上是人工历史**|`importers/build_rework_tasks.py`、`rework_import_from_export.py`|Phase C：区分模型 prediction 与人工历史|返工包可生成；不读 `prelabels/`；与 M6\.1 联调通过|
|**M4\.4**|更新 importer 相关测试|`tests/test_build_ls_tasks.py`、`test_build_rework_tasks.py`、`test_rework_*`|锁定行为|覆盖：无 prelabel 导入成功；含 predictions 的首轮产物判定失败（若做断言）|



---



### M5 · `common/`（Phase A 规则 \+ Phase B 路径）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M5\.1**|扩展 rework 判定：在现有 `human_confirmed` / `needs_rework` 之外，**空标注 / 缺任务结果 → 必须 rework**|`common/models.py`（`should_rework` 或并列 API）|需求明确的空标注规则|API/文档写出完整布尔规则；单测覆盖|
|**M5\.2**|解析/落盘结果能表达「无有效人工载荷」，并驱动 M6\.3|`models.py` \+ exporters 契约|空 result 与缺 mask/bbox/text 可判定|空样本不会进 normal|
|**M5\.3**|`paths.prelabels_task_dir`：废弃或迁 legacy；主流程不用|`common/paths.py`|Phase B 运行时无 prelabels|主流程无调用|
|**M5\.4**|`seg_mask_paths`：不再解析到 `prelabels/.../masks`；仅 manual/final 等 V1 路径|`common/seg_mask_paths.py`|去掉隐式 prelabel|单测无 prelabels 根依赖|
|**M5\.5**|清理 models 中「Prelabel 阶段」误导注释；保留业务模型清晰|`common/models.py`|架构清晰|注释与 V1 语义一致|
|**M5\.6**|更新 `tests/test_models.py`、`test_seg_mask_paths.py`|`tests/`|锁定规则|空标注→rework 用例通过|



**空标注 / 缺结果规则（写入实现与测试）**



- `annotation.result == []`（或等价空）→ `rework/`

- SEG 无有效 mask；DET 无 bbox；CAP 无 text → `rework/`

- 另：人工勾选需返工 / 未确认等原有规则仍生效

    

---



### M6 · `exporters/`（Phase A 核心 \+ Phase C）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M6\.1**|**重写** `resolve_effective_result`：有效结果**仅**来自 `annotation.result`；**禁止** `prediction_fallback` 作为最终结果来源|`exporters/effective_result.py`|V1 金标准只认人工|无 `prediction_fallback` 源；confirm\-only 且无人工载荷 → 空/需 rework，不回填 pred|
|**M6\.2**|`parse_ls_export`：SEG/DET/CAP 只消费人工 effective；不读 `task["predictions"]` 填金标准|`exporters/parse_ls_export.py`|与 M6\.1 一致|相关单测改写并通过|
|**M6\.3**|`split_by_rework` / `refresh_normal_rework`：接入 M5\.1 空/缺结果规则|`split_by_rework.py`、`refresh_normal_rework.py`|分类落地|`result==[]` 或缺 mask/bbox/text → 进入 `rework/`|
|**M6\.4**|`previous_annotations`：命名/文档强调「上一轮人工快照」；可继续生成返工预填结构，但**不得**被 M6\.1 当作模型预测回退|`previous_annotations.py`|Phase C 语义分离|README/注释含 `previous_annotations ≠ prediction`|
|**M6\.5**|更新 effective/parse/split/export\-split 测试|`tests/test_effective_result.py`、`test_parse_ls_export.py`、`test_split_by_rework.py`、`test_export_split_*`|去掉 fallback 用例，换成 V1 用例|场景：正常→normal；空→rework；无 pred 文件可解析|



---



### M7 · `preprocess/` / `packaging/`（Phase B｜轻量）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M7\.1**|**保持**预处理与 SEG/DET/CAP 拆包主逻辑，不大改|`preprocess/**`、`packaging/**`|已符合多任务拆分|现有核心测试通过|
|**M7\.2**|**检查并清除**隐含 prelabel 依赖（import、路径、文档字符串、示例假设）|同上 \+ 相关 docs/examples|防隐式耦合|grep 无运行时 prelabels 依赖|
|**M7\.3**|回归 `tests/test_preprocess.py`、`test_packaging.py`|`tests/`|防回归|全绿|



---



### M8 · `merge/`（Phase C｜轻量）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M8\.1**|**保持**三任务 current 合并与 final 自包含|`merge/**`|金标准交付已基本具备|merge 冒烟通过|
|**M8\.2**|检查 `validate_ready` / merge 路径**无**「必须有 prelabel」隐含条件|`validate_ready.py`、`merge_to_final.py` 等|Phase C|仅依赖 V1 current/rework 就绪语义|
|**M8\.3**|回归 `tests/test_merge_*.py`、`test_validate_ready.py`|`tests/`|防回归|全绿|



---



### M9 · `labelstudio/`（Phase D｜配置与角色包配合）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M9\.1**|复核 seg/det/cap XML：无 prediction 导入时可用|`labelstudio/configs/*.xml`|空任务导入兼容|配置测试通过；文档说明首轮无 pred|
|**M9\.2**|配置按角色进入 `deploy/v1/annotator_*`（与 M11 联动）；随包提供本任务允许的 CLI 入口|configs \+ deploy|标注员包最小化且可本机闭环|每包仅本任务配置；另含本任务 `ls-import` / `export-split` / `rework-import` 裁剪入口（与 M11 一致）|
|**M9\.3**|回归 `tests/test_labelstudio_*_config.py`|`tests/`|防回归|全绿|



---



### M10 · CLI / 示例（Phase A 文案 \+ Phase B 清理）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M10\.1**|CLI help：`ls-import`=从任务包生成空任务；去掉 prelabel 暗示|`cli.py`|Agent/用户不误用|`-h` 文案符合 V1|
|**M10\.2**|示例脚本去 prelabel 步骤或标 legacy|`examples/**`|演示=真路径|新演示无 prelabels 目录要求|
|**M10\.3**|更新 `tests/test_cli.py` 及流水线演示测试|`tests/test_cli.py`、`test_p4_*`、`test_docs_*` 等|锁定 CLI|与 Phase A/B 行为一致|



---



### M11 · `deploy/v1/`（Phase D｜**提高优先级**，可与 Phase C 并行）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M11\.1**|新建 `deploy/v1/data_processor/`：完整 CLI（preprocess/package/ls\-import/export\-split/rework\-import/merge）入口与说明；**README 区分协作主路径与本机全流程测试**；环境 \+ 命令 \+ 数据目录约定|`deploy/v1/data_processor/`|协作交付 \+ 处理者本机测试须可跑通全流程|目录存在；四类文档要素齐全；单包可按测试路径跑通说明操作|
|**M11\.2**|`annotator_seg/`：SEG LS 配置 \+ 裁剪入口（ls\-import/export\-split/rework\-import）\+ 本机闭环与双模式回传说明；禁止 preprocess/package/merge/他任务|`deploy/v1/annotator_seg/`|角色隔离|包内无他任务；无 preprocess/package/merge|
|**M11\.3**|`annotator_det/`：同 SEG 原则（仅 DET）|`deploy/v1/annotator_det/`|同上|同上|
|**M11\.4**|`annotator_cap/`：同 SEG 原则（仅 CAP）|`deploy/v1/annotator_cap/`|同上|同上|
|**M11\.5**|根级 `deploy/v1/README.md`（可选但推荐）：四角色关系；分发仅 task_packages；回传 rework/ vs 完成态 current/（SEG+manual_masks）；换人交接三件套；处理者本机全流程测试见 data_processor README|`deploy/v1/`|交付可读性|指向四子包并写清进出约定|



**必须结构**：



```Plain Text
deploy/v1/
├── data_processor/
├── annotator_seg/
├── annotator_det/
└── annotator_cap/
```



每目录至少：`README`、环境说明、命令说明、数据目录约定。



---



### M12 · 测试与验收门禁（贯穿；冻结在 Phase D）



|ID|修改目标|涉及模块|修改原因|验收标准|
|---|---|---|---|---|
|**M12\.1**|场景：正常人工标注 → `normal/`|`tests/`|验收标准|自动化或可脚本复现|
|**M12\.2**|场景：空标注 / 空 result / 缺任务字段 → `rework/`|`tests/`|V1 新增规则|断言进入 rework|
|**M12\.3**|场景：无 prelabels、无 prediction 文件，主流程可运行|`tests/` \+ 示例数据|必测场景 3|CI/本地通过|
|**M12\.4**|场景：SEG/DET/CAP 独立运行|`tests/`|多任务隔离|分任务用例通过|
|**M12\.5**|场景：返工闭环 → 全通过 → merge 出 final|`tests/` / 手工 runbook|闭环|final 自包含金标准|
|**M12\.6**|全量 `pytest` \+ README/CHANGELOG 完整 → 可宣布冻结|全仓|冻结条件|CHANGELOG 记测试结果；状态可达 *Medical Image Multi\-task Annotation Dataflow V1 Frozen*|



---



## 3\. Agent 推荐执行顺序（可复制为 sprint）



### Sprint A1 — 空任务导入（阻塞项）



1. M4\.1 → M4\.2 → M4\.4（先测首轮）  

2. M3\.1 → M10\.1  

3. 最小 CHANGELOG 草稿条目（完整润色可留 D）

    

### Sprint A2 — 金标准只认人工 \+ 空进 rework



1. M6\.1 → M6\.2 → M5\.1 → M5\.2 → M6\.3  

2. M6\.5 / M5\.6  

3. M12\.1 / M12\.2 / M12\.3（至少单测级）

    

### Sprint B — 清理与隔离



1. M1\.1–M1\.3  

2. M2\.1–M2\.4  

3. M5\.3–M5\.5  

4. M3\.2–M3\.4、M7\.\*、M10\.2–M10\.3  

    

### Sprint C — 返工与合并



1. M4\.3、M6\.4  

2. M8\.\*  

3. M12\.4–M12\.5  

    

### Sprint D — 交付与冻结（M11 **尽早开工**，勿压到最后一天）



1. M11\.1–M11\.5（可与 C 并行）  

2. M9\.\*  

3. M0\.\* 定稿  

4. M12\.6 冻结  

    

---



## 4\. 风险提示（执行时注意）



|风险|表现|缓解|
|---|---|---|
|半改状态|已空任务导入，仍 `prediction_fallback`|严格 A1→A2；同一 PR/提交尽量成对|
|字段名混淆|LS JSON 里仍有 `predictions` 键|代码注释 \+ README：返工预填=人工历史；M6\.1 禁止作最终来源|
|误删扩展点|直接删 adapters/formats|只做 **legacy 隔离 / 三分拆分**|
|隐式路径|`seg_mask_paths` / merge 仍指 prelabels|Phase B grep \+ M7\.2/M8\.2|
|文档滞后|代码已 V1，README 仍写 prelabels|每 Sprint 至少一条 CHANGELOG；D 阶段 README 定稿|
|部署滞后|功能完成但无四角色包|M11 与 C 并行，作为 D 入口条件|



---



## 5\. 与旧清单的关键修正对照



|旧做法|修订后|
|---|---|
|强调不改 V2 / 兼容|V1 独立重构；强调流程一致 \+ 可追溯|
|直接删除 `adapters/`|**隔离 legacy**，移出运行时，主流程不调用|
|删除整个 `formats` / PrelabelDocument|**三分拆分**；legacy\_prelabel 保留历史定义|
|P0 先文档 / 先删模块|**Phase A 先核心数据流**（ls\-import → 去依赖 → 去 fallback → 空 rework）|
|converter 可能被整删|禁模型/prelabel 转换；**保留** previous\_annotations 编码|
|deploy 靠后|**提高优先级**，可与 Phase C 并行|
|prediction 与 previous 易混|清单强制写清：**previous\_annotations ≠ prediction**|



---



## 6\. 单任务完成定义（DoD，Agent 通用）



每个 `Mx.y` 完成时至少满足：



1. 代码改动范围与「涉及模块」一致，无无关大重构；  

2. 对应 tests 更新且本地相关用例通过；  

3. CHANGELOG 有对应条目（可与同 Phase 合并提交，但不可缺）；  

4. 若改变用户操作路径，README 或 `deploy/*/README` 有同步（Phase A 允许简记，Phase D 必须完备）。

    

