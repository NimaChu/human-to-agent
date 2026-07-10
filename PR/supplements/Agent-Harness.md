# Agent Harness 概念权威原文调研笔记

> 整理日期：2026-07-10
> 调研目的：定位 AI Agent 领域 "harness" 概念最权威的原始定义出处，逐字保留英文原文，供后续引用与溯源使用。

---

## TL;DR

关于 AI Agent 领域的 **harness** 概念，最权威的原文来自 **Anthropic 官方**，共三篇文章，分别从「定义」「架构分层」「工程实现」三个角度给出：

| # | 文章 | 发布日期 | 核心贡献 |
|---|------|---------|---------|
| 1 | Demystifying evals for AI agents | 2026-01-09 | 首次给出 "agent harness (or scaffold)" 的精确定义 |
| 2 | Trustworthy agents in practice | 2026-04-09 | 把 agent 拆为四组件，harness 作为其中之一（"指令与护栏"） |
| 3 | Scaling Managed Agents: Decoupling the brain from the hands | 2026-04-08 | 把 harness 形式化为可替换的工程接口（"调用循环"） |

三篇合起来覆盖 harness 的三个面向：**定义 → 架构定位 → 工程接口**。

---

## 一、权威原文（Anthropic 官方，共 3 篇）

### 原文 1 —— harness 的标准定义（最权威）

**这是目前能找到的、Anthropic 对 agent harness 给出最直接、最完整定义的原文。**

- **标题**：Demystifying evals for AI agents
- **作者**：Mikaela Grace, Jeremy Hadfield, Rodrigo Olivares, Jiri De Jonghe
- **发布**：Engineering at Anthropic · 2026-01-09
- **链接**：https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- **出处章节**：The structure of an evaluation

#### 原文逐字引用

> An **agent harness** (or **scaffold**) is the system that enables a model to act as an agent: it processes inputs, orchestrates tool calls, and returns results. When we evaluate "an agent," we're evaluating the harness *and* the model working together. For example, Claude Code is a flexible agent harness, and we used its core primitives through the Agent SDK to build our long-running agent harness.

同篇还定义了与之对照的 **evaluation harness**（评估基础设施，非本文主题）：

> An **evaluation harness** is the infrastructure that runs evals end-to-end. It provides instructions and tools, runs tasks concurrently, records all the steps, grades outputs, and aggregates results.

#### 释义要点

- 明确 `scaffold` 是 `agent harness` 的**同义词**。
- 强调评估 "an agent" 时，实际评估的是 **harness 与 model 协同工作的整体**，而非单一组件。
- 把 Claude Code 本身定位为 "a flexible agent harness"，并把基于 Agent SDK 构建的长运行 agent 也称为 harness。

---

### 原文 2 —— harness 在 Agent 四层架构中的位置

- **标题**：Trustworthy agents in practice
- **发布**：Anthropic Research · 2026-04-09
- **链接**：https://www.anthropic.com/research/trustworthy-agents
- **出处章节**：How agents work

#### 原文逐字引用

Agent 由四个组件构成，harness 是其中之一：

> An agent is built from four components, and each one is both a source of capability and a potential point of oversight:
>
> - **The model.** This is the "intelligence" that makes tasks possible. That intelligence is the product of our training process, which shapes both what the model knows and how it reasons and behaves.
> - **A harness.** This refers to **the instructions, and the guardrails, that the model operates under.** In our example above, the harness might tell Claude to flag anything over a hundred dollars, or to never submit expenses without user confirmation.
> - **Tools.** These are the services and applications the model can use, like your email, calendar, or expense software. Without tools, Claude can read the receipt but not file it.
> - **An environment.** This is where the agent runs—i.e., whether it's set up in Claude Code, Claude Cowork, or some other product—and which files, websites, or systems it can access.

四层需协同，任一层失守都会被利用：

> Agents' behavior depends on all four layers working together. A well-trained model can still be exploited through a poorly configured harness, an overly permissive tool, or an exposed environment. This is why the safeguards we and others build need to account for them all.

#### 释义要点

- 这篇给出的 harness 语义偏 **"指令与护栏"（instructions and guardrails）**，强调治理与安全属性。
- harness 既是能力来源，也是**治理介入点**（point of oversight）。
- 与原文 1 的 "system that enables a model to act as an agent" 互补：原文 1 讲"是什么"，原文 2 讲"治理上意味着什么"。

---

### 原文 3 —— harness 的工程化接口定义

- **标题**：Scaling Managed Agents: Decoupling the brain from the hands
- **作者**：Lance Martin, Gabe Cemaj, Michael Cohen
- **发布**：Engineering at Anthropic · 2026-04-08
- **链接**：https://www.anthropic.com/engineering/managed-agents
- **出处章节**：开篇 + Decouple the brain from the hands

#### 原文逐字引用

Managed Agents 将 agent 虚拟化为三个抽象，harness 是其中之一：

> We virtualized the components of an agent: a **session** (the append-only log of everything that happened), **a harness (the loop that calls Claude and routes Claude's tool calls to the relevant infrastructure)**, and a **sandbox** (an execution environment where Claude can run code and edit files). This allows the implementation of each to be swapped without disturbing the others.

harness 编码的是"模型当前做不到、需外部补足的假设"，而这些假设会随模型变强而过时：

> A common thread across this work is that harnesses encode assumptions about what Claude can't do on its own. However, those assumptions need to be frequently questioned because they can go stale as models improve.

> Harnesses encode assumptions that go stale as models improve. Managed Agents—our hosted service for long-horizon agent work—is built around interfaces that stay stable as harnesses change.

harness 应设计成可替换的 "cattle"（牲畜，可替换）而非 "pet"（宠物，不可丢）：

> The harness also became cattle. Because the session log sits outside the harness, nothing in the harness needs to survive a crash. When one fails, a new one can be rebooted with `wake(sessionId)`, use `getSession(id)` to get back the event log, and resume from the last event.

Managed Agents 本身被定位为 meta-harness（元 harness），不对具体 harness 做假设：

> Managed Agents is a meta-harness in the same spirit, unopinionated about the *specific* harness that Claude will need in the future. Rather, it is a system with general interfaces that allow many different harnesses.

#### 释义要点

- 这篇把 harness 落到**接口层面**：`the loop that calls Claude and routes Claude's tool calls to the relevant infrastructure`。
- 核心工程论点：harness 编码的假设会**随模型变强而过时**，因此要把 harness 设计成可热替换的组件（session 外置以支持崩溃恢复）。
- 引入 "brain / hands / session" 三分法：harness = brain 的一部分（与 Claude 共同构成 brain），sandbox = hands。

---

## 二、三篇原文的语义互补关系

同一概念，三篇原文分别强调不同面向，引用时按需选取：

| 面向 | 原文 | 关键句 |
|------|------|--------|
| **是什么**（定义） | 原文 1 | "the system that enables a model to act as an agent: it processes inputs, orchestrates tool calls, and returns results" |
| **治理上意味着什么**（护栏语义） | 原文 2 | "the instructions, and the guardrails, that the model operates under" |
| **工程上怎么实现**（接口语义） | 原文 3 | "the loop that calls Claude and routes Claude's tool calls to the relevant infrastructure" |

概念演化脉络：

```
原文1（2026-01）        原文2（2026-04）         原文3（2026-04）
定义层 ──────────────► 治理/架构层 ──────────────► 工程接口层
"是什么"               "指令与护栏"             "调用循环 + 可替换"
```

---

## 三、补充：学术综述（形式化定义）

如需学术化的形式定义，目前最完整的是这篇预印本综述，把 agent harness 形式化为六元组。

- **论文**：*Agent Harness for Large Language Model Agents: A Survey*
- **作者**：Meng Qianyu, Wang Yanan, Chen Liyi, Wang Qimeng, Lu Chengqiang, Wu Wei, Gao Yan, Wu Yi, Hu Yao
- **发布**：Preprints · 2026 · doi:10.20944/preprints202604.0428.v2（Under review）
- **链接**：https://www.preprints.org/manuscript/202604.0428/v2
- **GitHub**：https://github.com/Gloriaameng/LLM-Agent-Harness-Survey

六元组形式化定义 `Harness = ⟨E, T, C, S, L, V⟩`：

| 组件 | 符号 | 作用 |
|------|------|------|
| Execution Loop | E | Observe-think-act 循环、终止条件、错误恢复 |
| Tool Registry | T | 类型化工具目录、路由、监控、schema 校验 |
| Context Manager | C | 上下文窗口内容选择、压缩、检索 |
| State Store | S | 跨回合/会话持久化、崩溃恢复 |
| Lifecycle Hooks | L | 认证、日志、策略执行、埋点 |
| Evaluation Interface | V | 行动轨迹、中间状态、成功信号 |

> 注意：该综述为预印本（Under review），权威性低于 Anthropic 官方原文，但形式化最完整，适合用于需要可操作分解的场景。

---

## 四、引用建议

按用途选择出处：

- **引用 harness 的"定义"** → 用原文 1（Demystifying evals）那句 "An agent harness (or scaffold) is the system that enables a model to act as an agent…"。这是目前最干净、最被广泛转引的官方原文。
- **讲 harness 的"护栏/治理"语义** → 用原文 2（Trustworthy agents in practice）的 "the instructions, and the guardrails, that the model operates under"。
- **讲 harness 的"工程实现/可替换性"** → 用原文 3（Managed Agents）的 "the loop that calls Claude and routes Claude's tool calls to the relevant infrastructure"。
- **需要形式化分解** → 用学术综述的六元组 ⟨E, T, C, S, L, V⟩，并标注其为预印本。

---

## 五、参考链接汇总

1. Demystifying evals for AI agents — https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents (2026-01-09)
2. Trustworthy agents in practice — https://www.anthropic.com/research/trustworthy-agents (2026-04-09)
3. Scaling Managed Agents: Decoupling the brain from the hands — https://www.anthropic.com/engineering/managed-agents (2026-04-08)
4. Agent Harness for Large Language Model Agents: A Survey — https://www.preprints.org/manuscript/202604.0428/v2 (预印本)
5. 综述 GitHub 仓库 — https://github.com/Gloriaameng/LLM-Agent-Harness-Survey

---

*本笔记中所有英文引文均逐字摘自上述原文，未作改写。如需核对，请按章节链接溯源。*
