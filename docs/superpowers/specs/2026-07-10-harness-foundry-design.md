# Harness Foundry 工作区设计规格

**状态：** 已批准  
**批准日期：** 2026-07-10  
**交付形态：** 文件为唯一事实源、Agent 原生引导、Python CLI 确定性校验与生成  
**界面决策：** 首版不建设交互式 UI

## 1. 设计依据

本规格将以下资料视为规范性输入：

- `PR/Harness Foundry PR.md`：五阶段方法、母工作区能力、子工作区结构与验收标准。
- `PR/supplements/Agent-Harness.md`：Harness 的定义、治理语义、可替换执行接口与六元组 `⟨E,T,C,S,L,V⟩`。
- `PR/supplements/Loop Engineering.md`：Automations、Worktrees、Skills、Connectors、Sub-agents、外部持久状态和 maker/checker 分离。
- `PR/supplements/know-your-unknowns-method-cards.md`：Unknown 的四象限、blindspot、逐题访谈、语义映射、可调整计划、实施偏差、buy-in 文档和理解测验。原始 HTML bundle 仅保留在本地，不进入公开仓库。

资料中的 Acme 路径、角色、百分比、吞吐量、TTL、超时、权限、限流参数和颜色公式都是方法演示，不构成 Harness Foundry 的产品默认值。

## 2. 目标

Harness Foundry 是一个用于孵化和认证子工作区的母工作区。它必须：

1. 允许从不完整的真实工作开始，并把不能确认的内容显式转为 Unknown。
2. 引导用户依次完成工作复现、任务契约与 Skill 原型、Skill 验证、Harness 组合和 Loop Readiness 认证。
3. 将任务事实、证据、规则、案例、评价、权限和运行历史保存为可审阅、可迁移、可版本化的文件。
4. 通过确定性校验阻止虚假晋级、无证据关闭 Unknown 和过早扩大自治权限。
5. 生成可由非创建者理解、运行、验证和维护的完整子工作区。
6. 同时提供 Codex 和 OpenCode 的薄适配入口，业务事实和方法定义只维护一份。
7. 提供一个基于本项目真实资料的完整参考试点，证明五阶段链路和生成链路可运行。

## 3. 非目标

首版明确不实现：

- 交互式 Web、桌面或终端 UI；
- 中央数据库、多人实时协作和企业级 RBAC；
- 生产级 Agent 运行平台或无人值守 Loop 执行器；
- SaaS 多租户、计费和商业化；
- 模型训练、微调或特定底层 Agent 框架绑定；
- 直接执行外部发送、删除、审批或其他高风险业务动作。

上述边界不删除相关领域模型。权限、Human Gate、Trigger、Budget、Recovery 等仍须可声明、校验和认证，以便未来运行时复用。

## 4. 术语边界

### 4.1 Harness Foundry 产品定义

在本产品中，Harness 指围绕业务目标组合起来的完整受控工作系统：

```text
Harness = Skills + Workflow + Context + State + Rules + Permissions
        + Evaluations + Human Gates + Exceptions + Run History
```

该定义比 Anthropic 四组件语义中的“instructions and guardrails”更宽。为避免概念混淆，内部运行时模型显式映射为：

- `E` — Execution Loop：行动选择、终止、重试和恢复；
- `T` — Tool Registry：工具能力、输入输出、权限和副作用；
- `C` — Context Manager：固定、任务级、历史和临时上下文；
- `S` — State Store：当前状态、检查点和会话外持久化；
- `L` — Lifecycle Hooks：认证、策略、日志、版本和观测钩子；
- `V` — Evaluation Interface：局部评价、最终评价和进展信号。

模型、工具和执行环境在适配器边界上保持独立；产品层再将它们聚合为可交付的完整工作系统。

### 4.2 Skill

Skill 是边界明确、可独立验证和复用的业务能力，不等同于 Prompt。每个 Skill 必须声明目标、输入、输出、前置条件、适用与不适用范围、依赖、评价、错误和停止条件。

### 4.3 Unknown

Unknown 是可能影响正确性、稳定性、安全性、自动化边界或可复用性的未决事项。Unknown 的存在不代表失败；隐藏 Unknown 或无证据关闭 Unknown 才是失败。

### 4.4 Loop-ready

Loop-ready 表示构建有界闭环所需的信息和控制已经存在，不表示必须开启无人自治。

## 5. 核心不变量

1. **源文件唯一权威。** Python CLI、生成目录、状态报告和适配器不得成为第二事实源。
2. **生成物只读。** `dist/` 内容不得被反向读取为业务事实；人工修改会在下一次构建时被覆盖并由校验器报告。
3. **确定性构建。** 相同源文件、Schema 版本、模板版本和 CLI 版本必须产生字节等价的规范化输出；时间戳和随机 ID 不得在构建阶段生成。
4. **先验证后修改。** 校验失败、证据门禁失败、迁移失败或策略失败不得推进阶段或留下部分状态。
5. **证据优先。** 事实、推断、假设和未验证陈述必须区分；重要结论必须能追溯到具体证据。
6. **Unknown 不可自动消失。** 自动化可以建议关闭，但只有满足证据要求并记录责任人或授权角色的决定后才可关闭。
7. **maker/checker 分离。** 产出者不得作为唯一评价者；阶段 3 以后必须有独立验证记录。
8. **会话外状态。** 事件和检查点位于 Agent 会话之外；Harness 可重启、替换和重放。
9. **权限不可绕过。** Agent 适配器不得绕过 Schema、Policy 或 Human Gate；首版不执行外部高风险动作。
10. **版本变化可见。** Schema、Skill、Harness、工具或模型假设变化会产生漂移并触发适用范围内的重认证。

## 6. 总体架构

系统分为五层，每层只有一个清晰责任：

### 6.1 资产层

Markdown、YAML 和 JSONL 保存母工作区配置、子工作区业务资产、证据、事件和运行记录。资产层不依赖 Codex、OpenCode 或 Python 进程。

### 6.2 领域层

Python 领域模型定义五阶段、Unknown 生命周期、成熟度门禁、自治等级、Loop Readiness、版本兼容和引用关系。领域层不直接读写磁盘。

### 6.3 服务层

应用服务组合领域规则和存储适配器，实现初始化、脚手架、校验、晋级、重开、迁移、差异预览、构建、事件校验、恢复和重认证。

### 6.4 入口层

- Python CLI 提供非交互、可脚本化、机器可读的确定性操作。
- Codex/OpenCode Skills 提供案例优先的引导、访谈、分析和资产编写。
- Codex/OpenCode Agents 提供实践者代理、业务评审、Skill/Harness 维护和独立验证角色。

入口层只调用公共领域和服务接口，不复制业务规则。

### 6.5 发布层

构建器从规范化源资产生成 `dist/<workspace-slug>/`。发布目录包含运行所需文档、Skills、案例、评价、工作流、策略、状态说明、Human Gates、异常、Unknown、Readiness 和变更记录。

## 7. 工作区目录设计

```text
Harness Foundry/
├── README.md
├── AGENTS.md
├── pyproject.toml
├── uv.lock
├── foundry.yaml
├── .gitignore
├── .editorconfig
├── .github/workflows/ci.yml
├── .codex/
│   ├── config.toml
│   ├── agents/
│   └── skills/
├── .opencode/
│   ├── agents/
│   ├── commands/
│   └── skills/
├── agents/                         # Agent 角色定义的真源
├── skills/                         # 方法 Skill 的真源
├── src/harness_foundry/
│   ├── cli/
│   ├── domain/
│   ├── repositories/
│   ├── services/
│   ├── validators/
│   ├── renderers/
│   └── adapters/
├── schemas/                        # 从规范领域模型生成并提交的 JSON Schema
├── templates/child-workspace/
├── state/
│   ├── registry.yaml
│   ├── events.jsonl
│   ├── runs/
│   ├── transactions/
│   └── locks/
├── workspaces/                     # 子工作区规范源资产
├── dist/                           # 可重建、不可反向编辑的发布产物
├── examples/
│   └── harness-foundry-pilot/
├── tests/
│   ├── unit/
│   ├── schema/
│   ├── contract/
│   ├── integration/
│   ├── e2e/
│   ├── fixtures/
│   └── golden/
└── docs/
    ├── architecture/
    ├── methodology/
    ├── operations/
    ├── traceability/
    ├── adr/
    └── superpowers/
```

`agents/` 和 `skills/` 是跨工具真源；`.codex/` 与 `.opencode/` 只包含薄适配入口。适配器由校验器检查，禁止包含未在真源中声明的业务规则。

根目录 `state/events.jsonl` 只记录母工作区登记、模板、Schema 和全局配置变化；各子工作区 `.foundry/events.jsonl` 记录该子工作区资产、阶段和运行变化。二者通过稳定 workspace ID 关联，不复制事件。

## 8. 子工作区规范源结构

每个 `workspaces/<slug>/` 包含：

```text
<slug>/
├── workspace.yaml
├── README.md
├── TASK-CONTRACT/
│   ├── contract.yaml
│   └── narrative.md
├── SKILLS/<skill-id>/
├── CASES/<case-id>/
├── EVALS/<eval-id>/
├── WORKFLOW/workflow.yaml
├── CONTEXT/
├── STATE/state-model.yaml
├── POLICIES/policies.yaml
├── HUMAN-GATES/human-gates.yaml
├── EXCEPTIONS/exceptions.yaml
├── UNKNOWNS/<unknown-id>.yaml
├── LOOP-READINESS/assessment.yaml
├── RUNS/<run-id>/
├── EVIDENCE/<evidence-id>.yaml
├── CHANGELOG.md
└── .foundry/
    ├── artifact-index.yaml
    ├── events.jsonl
    └── checkpoints/
```

该结构保留 PR §14.10 的所有逻辑资产，并补充证据、运行记录、索引和检查点。

## 9. 公共资产约定

所有结构化资产共享以下元数据：

- `schema_version`：解析该文件所需的 Schema 版本；
- `id`：创建时生成、之后不可变的带类型前缀标识；
- `workspace_id`：所属子工作区；
- `revision`：语义修订号；
- `status`：领域状态；
- `owners`：责任角色或人员标识；
- `created_at`、`updated_at`：UTC ISO-8601 时间；
- `provenance`：人工、Agent、导入或迁移来源；
- `links`：对其他资产稳定 ID 的引用；
- `evidence_refs`：支撑该资产关键结论的证据引用。

时间戳和 ID 只在创建或显式变更时写入源文件，不在重复构建时变化。

### 9.1 证据模型

每条证据记录：

- 类型：正式规则、真实案例、负责人确认、系统定义、历史数据、风险决定或可重复验证；
- 来源与精确定位；
- 捕获者和捕获时间；
- 内容摘要与完整性摘要；
- 支撑的 claim；
- 置信基础：`observed`、`inferred`、`assumption` 或 `unverified`；
- 适用范围和失效条件。

低置信结论必须带 cheapest probe，不能伪装为已确认事实。

## 10. Unknown 管理

Unknown 类型和状态采用 PR 的定义。每个 Unknown 额外保存：

- 影响维度和影响说明；
- 出现条件和影响资产；
- 当前证据与置信基础；
- 责任人和期望响应角色；
- cheapest probe；
- 推荐 prompt patch；
- 风险处置：解决、接受、转人工或缩小范围；
- 关闭结论、依据和验证记录；
- 关闭、重开和状态变更历史。

关闭门禁要求至少一个允许的证据类型，并记录结论如何固化到任务契约、Skill、评价、异常、策略或 Readiness。`accepted-risk`、`human-only` 和 `out-of-scope` 是显式处置，不等价于事实已知。

Unknown 发现支持以下方法卡：

1. 四象限盘点：known known、known unknown、unknown known、unknown unknown；
2. blindspot pass；
3. 领域词汇教学；
4. 多设计方向和低成本 mock；
5. 基于现有资产的干预空间；
6. 按 blast radius 排序、一次一问的访谈；
7. 参考实现语义映射；
8. 高判断项优先的可调整计划；
9. 实施偏差日志；
10. buy-in 文档；
11. 合并或交付前理解测验。

真实案例优先于抽象访谈；案例不足或答案会改变架构时，使用按 blast radius 排序的逐题访谈。

## 11. 五阶段状态机与门禁

阶段可以前进、回退或因新证据重开。任何阶段推进都通过 CLI 计算硬门禁并生成可解释报告，不使用单一总分替代业务判断。

### 11.1 阶段 1：工作复现

必需证据：

- 至少一个真实任务；
- 可定位的输入和最终输出；
- 人工原始做法、Agent 操作轨迹、失败尝试和人工修改；
- 人工耗时基线和初始成功标准；
- 初始 Unknown；
- 工作实践者或业务 Owner 的可用性确认。

### 11.2 阶段 2：任务契约与 Skill 原型

必需证据：

- 第三方可理解的任务目标、输入、输出、前置条件、边界和验收；
- 至少一个 Skill 原型；
- 原始案例可重跑并复现已确认结果；
- 人工修改点已关联规则、案例、判断节点或 Unknown；
- 下一阶段案例计划。

### 11.3 阶段 3：Skill 验证与边界完善

“多个案例”的最小可执行解释是三个不同案例：至少一个正常案例、一个边界案例和一个失败或异常案例。每个案例必须有预期结果和实际评价。

必需证据：

- 核心 Skill 在三个以上不同案例上运行；
- 正常路径稳定通过；
- 失败路径能被识别并产生预期处置；
- 适用与不适用边界明确；
- 独立于创建者的运行或评审记录；
- 关键 Unknown 已关闭或有明确的人工/范围处置。

### 11.4 阶段 4：Harness 组合与受控运行

必需证据：

- 端到端业务目标、流程、状态和完成条件；
- Skill 输入输出关系和组合顺序；
- 公共上下文、工具、权限、Human Gates 和异常分支；
- 至少一个端到端案例通过；
- 每一步可追踪，局部评价和最终业务评价同时存在；
- 当前自治等级及批准人；
- 高风险动作受控且不能绕过人工机制。

Harness 可以只有一个 Skill，但必须证明该 Skill 与流程、状态、权限、评价、异常和人工机制共同构成完整工作系统；不能把单一 Skill 文件夹误标为 Harness。

### 11.5 阶段 5：Loop Readiness 认证

保留 PR 的十项核心条件：Goal、State、Action、Evaluator、Stop、Budget、Retry、Escalation、Recovery、Observability。

补充六项运行能力：

1. Trigger/Cadence；
2. Discovery/Triage；
3. Concurrency/Isolation；
4. Tool/Connector Availability；
5. Independent Verifier；
6. Version Drift/Re-certification。

评估结果沿用：未准备、条件准备、受控准备、有界准备、生产候选。结果必须包含证据、不满足项、风险和允许的自治上限。Readiness 结果只给出自治建议，业务 Owner 对 H0–H5 的批准保持独立，不能由分数自动提升权限。

### 11.6 “完备”发布门禁

完整子工作区必须满足 PR §12.5 和 §18.3 的交付条件，包括独立人员复现，并取得至少“条件准备”的 Readiness 结论；“未准备”只能生成草稿或评审包，不能标记为完备。未关闭 Unknown 可以存在，但必须说明影响、责任、出现后的处置和对自动化范围的限制。

## 12. CLI 契约

安装后的命令名为 `hf`。所有命令默认非交互，支持 `--format text|json`；会修改状态的命令支持 `--dry-run`，并在应用前输出规范化差异。

核心命令：

- `hf init`：初始化母工作区配置、状态目录和模板版本；
- `hf workspace new|list|status`：管理子工作区登记和阶段视图；
- `hf capture record`：登记真实任务、输入、输出、轨迹和人工修改；
- `hf unknown add|update|close|reopen`：管理 Unknown 生命周期；
- `hf validate`：执行 Schema、引用、证据、策略和门禁校验；
- `hf stage assess|advance|reopen`：评估并变更阶段；
- `hf readiness assess`：生成十项核心与六项补充 Readiness 结果；
- `hf diff`：比较源资产、上次记录和候选发布物；
- `hf record-change`：将规范源变化和摘要写入事件链；
- `hf build --draft|--release`：生成带明显草稿标记或通过发布门禁的子工作区；
- `hf migrate`：执行可预览、可恢复的 Schema 迁移；
- `hf events verify|replay`：校验事件链并从检查点重放；
- `hf doctor`：检查环境、版本、锁、事务、Schema、适配器漂移和未记录变化。

稳定退出码：

| 退出码 | 含义 |
|---:|---|
| 0 | 成功 |
| 2 | 命令参数或根配置错误 |
| 3 | Schema 错误 |
| 4 | 跨资产引用错误 |
| 5 | 证据或阶段门禁失败 |
| 6 | Policy 或 Human Gate 违规 |
| 7 | 版本、迁移或适配器兼容错误 |
| 8 | 文件、锁或事务错误 |
| 9 | 事件完整性或重放错误 |

JSON 输出包含 `command`、`status`、`exit_code`、`diagnostics`、`changed_files` 和 `next_actions`，便于 Agent 和 CI 消费。

## 13. 一致性、事务和恢复

所有 CLI 状态变更遵循：

1. 获取子工作区级文件锁；
2. 读取并校验当前源树和事件链；
3. 在内存中计算候选状态；
4. 校验候选树；
5. 写入 `state/transactions/<transaction-id>/` 和 write-ahead journal；
6. 通过临时文件、`fsync` 和原子替换应用各文件，索引最后替换；
7. 追加带前序摘要的 commit 事件；
8. 清理事务目录并释放锁。

事件为 append-only JSONL，至少包含顺序号、事件 ID、UTC 时间、actor、命令、资产引用、前后摘要、结果、前序事件摘要和当前事件摘要。`hf events verify` 检测截断、篡改、缺号和摘要不一致。

若进程在步骤 5–7 中断，`hf doctor` 根据 journal 和摘要完成或回滚事务，恢复到全旧或全新状态；禁止把半应用状态当作成功。检查点用于加速重放，但事件日志仍是运行历史权威来源。

人工或 Agent 直接编辑规范源后，`artifact-index.yaml` 会显示未记录摘要变化；`hf record-change` 在校验通过后登记变化。发布构建拒绝未记录的规范性修改。

## 14. 构建与发布

`hf build --draft` 可在任意阶段生成带 `DRAFT` 标记的审阅包，不宣称完备。`hf build --release` 只有在完备发布门禁通过时成功。

发布物包含：

```text
README
TASK-CONTRACT
SKILLS
CASES
EVALS
WORKFLOW
CONTEXT
STATE
POLICIES
HUMAN-GATES
EXCEPTIONS
UNKNOWNS
LOOP-READINESS
RUNS
EVIDENCE
CHANGELOG
BUILD-MANIFEST.json
```

`BUILD-MANIFEST.json` 记录 CLI、Schema、模板、适配器和源树摘要，不写入构建时钟等非确定性字段。发布包可独立校验，但不得成为后续编辑源。

## 15. Agent 与 Skill 设计

### 15.1 方法 Skills

至少提供：

- 工作选择与复现；
- 任务契约；
- Unknown 发现与证据管理；
- Skill 候选识别；
- 案例设计与评价；
- Harness 组合；
- 阶段评审；
- Loop Readiness；
- 实施偏差记录；
- 独立复现与理解测验；
- 子工作区构建和维护。

每个 Skill 遵循一个公共模板，并将交互结果写入规范源，不把对话历史当作持久状态。

### 15.2 Agents

至少提供四个职责分离角色：

- `practitioner-guide`：引导实践者复现真实工作；
- `asset-maintainer`：维护契约、Skill、案例、评价和引用；
- `maturity-reviewer`：只读检查阶段门禁、风险和证据；
- `independent-verifier`：独立运行案例、挑战自我评价并出具复现记录。

实现者和独立验证者不得共享未写入规范源的隐性结论。

## 16. 权限与 Human Gate

Policy 对动作分为只读、内部写入、外部发送、不可逆和严禁。Tool Registry 为每个工具声明输入输出、所需权限、副作用、幂等性、重试能力和 Human Gate。

首版 CLI 不调用业务外部系统；外部发送和不可逆动作只能形成“拟执行动作包”，由 Human Gate 记录批准、拒绝或修改。发布检查确保：

- 高风险动作有明确批准角色；
- 未批准动作不能标记为已执行；
- 拒绝会进入运行记录和必要的 Unknown；
- Human Gate 后的恢复入口明确；
- 严禁动作没有运行时映射。

源文件和日志不得保存凭据。`hf doctor` 检查常见秘密文件和敏感值模式，并把问题作为阻塞诊断报告。

## 17. 版本、迁移和重认证

版本维度独立记录：

- CLI 版本；
- Schema 版本；
- 模板版本；
- Skill 版本；
- Harness 版本；
- 工具/连接器契约版本；
- 模型和环境假设版本。

迁移是显式、可预览、逐版本的纯变换。迁移前后均执行 Schema 和引用校验，并生成事件和差异。

以下变化触发重认证：

- Skill 的输入、输出、边界、评价或错误语义变化；
- Harness 流程、权限、状态或 Human Gate 变化；
- Tool Registry 副作用或权限变化；
- Schema 大版本变化；
- 模型或执行环境变化使已记录假设失效；
- 黄金案例或关键业务规则变化。

重认证只重跑受影响资产及其反向依赖，但阶段 4 端到端案例和阶段 5 Readiness 必须在核心 Harness 变化后重新评估。

## 18. 成熟度报告

首版以 Markdown 和 JSON 报告代替 UI。报告展示：

- 当前阶段及硬门禁；
- 已满足、未满足和因证据不足无法判断的条件；
- Skill 案例覆盖、评价结果和独立验证覆盖；
- Unknown 数量、风险、责任和阻塞关系；
- Harness 完整性、自治等级和 Readiness；
- 人工评审积压、版本漂移和重认证状态；
- 本轮关闭的 Unknown、新显化规则和受控风险；
- 推荐下一步及其依据。

文件数量和填写完整度可以作为提示指标，但不得单独推进阶段。

## 19. 参考试点

参考试点名为 `harness-foundry-pilot`，真实任务是：

> 将本仓库中的产品需求和三份理论补充转化为可执行、可验证、可移交的 Harness Foundry 工作区。

试点使用当前真实文件作为输入，以最终工作区、设计规格、实现计划、追踪矩阵、测试结果和发布包作为输出。它必须包含：

- 完整工作复现和人工/Agent 决策轨迹；
- 任务契约；
- 至少一个“来源到需求与验收映射”Skill；
- 至少三个案例：主 PR 正常案例、概念冲突边界案例、演示数据不可继承失败案例；
- 独立验证者评审；
- 从资料审阅到工作区发布的端到端 Harness；
- Unknown、Human Gates、异常、状态和评价；
- 完整 Loop Readiness 结果。

该试点是真实工程案例，不把 Acme 演示数据当作业务事实。用户对设计的批准作为业务 Owner 的设计确认，最终发布仍需独立验证证据。

## 20. 测试策略

实现采用测试驱动开发。每个行为先有失败测试，再写最小实现。

### 20.1 单元测试

- 领域值对象、状态迁移和门禁；
- Unknown 关闭与重开；
- 证据资格和引用；
- Readiness 和自治建议；
- 版本影响与重认证传播；
- 规范化、摘要和确定性排序。

### 20.2 Schema 与契约测试

- 每类有效、无效和边界 fixture；
- JSON Schema 与 Python 模型一致；
- Codex/OpenCode 薄适配器不包含额外业务规则；
- CLI JSON 输出和退出码稳定；
- 发布物结构覆盖 PR §14.10。

### 20.3 集成测试

- 文件锁和并发冲突；
- write-ahead transaction 的成功、回滚和崩溃恢复；
- 事件链篡改、截断和重放；
- Schema 迁移和回滚；
- 未记录修改检测；
- 草稿和发布构建；
- 权限、Human Gate 和严禁动作阻断。

### 20.4 端到端测试

- 从 `hf init` 到发布的完整五阶段流程；
- 阶段重开与新案例回流；
- 非创建者独立复现；
- Harness 变更后的重认证；
- Windows 和 Linux 路径语义；
- 参考试点的黄金输出。

真实模型输出不是确定性单元测试目标。适配器通过结构、上下文输入、预期资产和记录式评价验证；业务正确性由黄金案例和独立评价证明。

## 21. 需求追踪与完成审计

建立 `docs/traceability/pr-requirements.yaml` 和人类可读 Markdown 报告。每条 PR 要求至少链接：

- 规范条款；
- 实现文件；
- 测试或人工证据；
- 当前状态；
- 未满足原因和负责人。

完成审计逐条覆盖：母工作区功能、五阶段晋级、最终子工作区标准、方法论验收、试点验收和补充理论约束。测试通过只能证明被测试的行为；没有直接证据的条目保持未完成。

## 22. 工程基线

- Python 最低版本为 3.11。
- 使用 `uv` 管理虚拟环境、依赖解析和 `uv.lock`。
- 使用 `pyproject.toml` 管理构建、CLI、lint、类型检查和测试。
- 使用锁文件保证可复现开发依赖。
- CI 至少执行格式检查、lint、静态类型检查、单元/集成/端到端测试、Schema 生成漂移检查、确定性黄金构建和需求追踪完整性检查。
- 所有路径处理使用 `pathlib`，避免把 Windows 路径语义写入领域层。
- 运行时不依赖网络；连接器是显式可选适配器。

## 23. 演进路径

文件模型和 CLI 经真实试点稳定后，才考虑：

1. 只读或编辑型本地 UI；
2. 集中式协作服务和企业身份；
3. 共享 Skill 目录和 Harness 模板；
4. Automations、Connectors 和生产 Loop 运行时；
5. 部门级应用或 SaaS。

任何演进都必须继续使用稳定 Schema 和迁移机制，不能把现有文件资产变成不可审阅的数据库黑盒。

## 24. 已解决的关键设计决策

- 选择文件核心方案，不选择仅 Prompt/文档方案或完整 Web 应用。
- 首版没有交互 UI。
- Python CLI 是确定性编译器和校验器，不是第二状态源。
- Harness Foundry 的宽产品定义与外部三种 Harness 语义通过内部六元组映射兼容。
- PR 十项 Readiness 是核心，补充资料的六项运行能力单独评估。
- 真实案例优先，架构级未知通过逐题访谈补充。
- “多个案例”在阶段 3 解释为至少三个不同类型案例。
- Harness 允许单 Skill，但必须具备完整系统要素。
- 自治等级和 Readiness 结果相关但不自动绑定。
- 发布物不可反向编辑；源资产始终保持权威。
- 参考试点使用本项目真实资料，不使用虚构 Acme 数据。
