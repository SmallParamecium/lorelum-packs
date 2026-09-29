# Issue #26：检索评测接入 CI 的设计决策

- 更新：2026-09-28
- 状态：本地实现与验证已完成；仍须由 PR 的 Ubuntu CI 正、负向运行验收
- 范围：`agentic-coding` Pack 的 PR 检索门禁；不改变 lore CLI、Registry 或发布流程

## 目标和边界

Issue #26 要解决的是“改动 Pack、fixture 或评测脚本的 PR 不依赖人记得运行检索检查”。它验证候选 Pack 中的 Practice 能否被既定 Query 找到，以及既有命中是否丢失；**不证明 Practice 正文质量、Agent 行为效果或所有真实请求的检索表现**。

职责分层如下：

| 层 | 本次职责 | 不承担的职责 |
| --- | --- | --- |
| PR 工作流 | 按目标路径触发、准备隔离环境、运行单测和 keyword 门禁、上传可用证据 | 在 CI 运行时生成或重新标注 Query；发布 Pack |
| `lore` CLI | 校验并加载候选 Pack，提供实际检索结果 | 决定 fixture 的标签或门槛 |
| `scripts/eval-queries` | 校验 fixture 与来源、执行查询、比较基线、作出可复现的门禁判定 | 审定场景真实性；评判 Agent 最终决策 |
| fixture 与基线 | 保存人工确认的场景、预期目标、迁移记录和历史结果 | 因本次检索结果自动改写预期答案 |
| 维护者 | 审查 Query 的场景、标签、边界和有理由的迁移 | 把未审候选或生成结果直接当作测试真值 |

行为验证继续使用独立的 decision-probe / benchmark 流程，不混进本次 PR 检索门禁。

## 已确定的处理决策

### 1. 评测 PR 内容，而不是只测已发布版本

CI 把 PR 的 `packs/agentic-coding` 放入隔离的 ProjectContext，以 `base: none` 加载。评测前必须确认候选 Pack 有效、上下文就绪、活动 Practice 与候选文件一致，并确认读取的 Practice 确实来自项目源。任一前提不成立即失败，不回退到 LocalStore 的已发布 Pack；否则绿灯无法代表 PR 内容。

因此 CI **不用** `--ensure-install` 安装 release 来代替候选评测。已发布版本仅作为历史基线来源。CLI 固定版本，keyword 为 CI 模式；semantic 的环境/索引不确定性留给发布前的独立验证，不以降级结果冒充通过。

### 2. 固定 Query 是门禁输入，不在 CI 动态生产

正式 fixture 中，positive 指定应命中的 Practice；neighbor 指定应命中的相邻 Practice，并记录容易误选的 `resembles`。标签在看本次检索排名之前由维护者确认，不能因排名不理想而改 `expect` 来取得绿灯。每个活动 Practice 至少有一条活动 positive Query；重要边界可由 neighbor 补充，但本 issue 不新增“一律每篇固定几条”的配额。

正式运行要求所有活动 Query 明确为 `status: frozen`。`candidate` / `reviewed` 不能进入正式门禁；`retired` 必须说明原因，保留历史身份，但不参与覆盖率、检索或 Top-3 分母。Agent 辅助改写或真实样本若将来引入，先经人工审查再冻结；本次不建立生成流水线，也不让生成结果临时改变 CI 结论。

本次移除了旧 fixture 中统一填充的 `origin: regression`：这并不能证明每条 Query 的实际来源，而且评测器也未校验该字段。不得据此声称来源审计已经完成；可核实的来源、审核人与标签依据留待独立任务，不是 #26 的验收条件。

### 3. 基线只能防回归，不能替代标签判断

CI 以当前已发布的 0.5.1 keyword 运行作主线基线，比较同一 Query 的 Top-3 命中；0.4.0 基线保留供跨版本分析，不把主线已存在的变化归责于本 PR。旧命中丢失则失败，改善不阻断；新增 Query 没有旧结果可比，仍须参与本次覆盖率与 Top-3 门槛。基线的 Pack、fixture set、Top-k、完整结果条数和结果格式必须兼容，缺失或不可用时失败，而不是视作零回归。

同一 ID 的 Query 文本不得悄悄改写；需要改写时，说明旧 Query 退休原因并用新 ID 加入。预期 Practice 改变必须明确记录先前目标和迁移原因，不能简单改标签。旧 Practice 仍活动时，保留其独立 positive 覆盖及新旧边界；旧 Practice 已合并或退出时，记录对应 Practice 迁移及受影响 Query。这样既能容纳当前 0.4.0 → 0.5.1 的合法合并，也能拦住无说明的重新标注或删除。

neighbor 的命中与混淆会报告；当前没有单独新增“neighbor 达到某百分比”的硬门槛。其既有命中丢失仍按基线规则处理。

### 4. 正式门禁的失败条件

| 检查 | 当前判定 |
| --- | --- |
| 候选来源/Pack 有效性 | 无法确认候选被实际加载时失败，不改测已发布版本 |
| fixture 完整性 | 必填值、重复、引用与迁移记录不合规时失败；正式 Query 必须 frozen |
| Practice 覆盖 | 有活动 Practice 缺 positive Query 时失败 |
| 基础反照搬 | 活动 Query 明显复述 Practice **标题或 `applies_when`** 时失败 |
| 实际检索 | Query 执行错误或 positive Top-3 低于 90% 时失败；CI 显式固定 `--min-top3 0.90`，删除 fixture 默认值也不能绕过 |
| 基线 | 不兼容、无说明的文本/标签变化、无说明的旧 Query 删除或既有命中丢失时失败 |

`--limit` 只供探索，不能拿局部运行冒充正式通过。门禁失败时尽量写入 JSON 和 Markdown 的失败原因；若 CLI 无法启动、fixture 无法读取或候选 Pack 校验在建立运行记录前失败，工作流本身仍应红，但不保证有评测 artifact。上传步骤不应把“没有产物”解释成通过。

基础反照搬**只覆盖标题和 `applies_when`**；正文、Guidance、anti-pattern、例外与步骤顺序尚未自动比对。人工审阅应避免把答案直接写进 Query，但不能宣称这已由 CI 全面保证。后续方向见 [Query 独立性后续设计](issue-26-query-dedup-implementation.md)。

## 工作流与验收

PR 触碰 `packs/agentic-coding/**`、`fixtures/agentic-coding/**`、`scripts/eval-queries`、相关测试或工作流文件时触发。顺序为单测、固定 CLI 安装、候选 Pack 准备、keyword 正式评测、无论成功与否上传已产生的证据。工作流脚本只负责编排，不在 YAML 中复制评测政策。

合入前需要以下**实际 GitHub Actions**证据，而不是仅凭本地测试：

1. 目标路径的 PR 自动触发，并在 `ubuntu-latest` 上跑通 CLI 安装、候选来源验证与完整 keyword 门禁；
2. 临时删除某活动 Practice 的全部 positive Query，CI 因 coverage 变红；恢复后再让某 Query 复述 Practice 标题或 `applies_when`，CI 因 discipline 变红；
3. 恢复 fixture，最终 CI 变绿，查看失败与成功时可用的日志及 artifact。

本地 45 个单测及固定 CLI 的完整/负向运行只是预验证，不能代替以上 CI 验收。若期望“红灯绝不可合并”，仓库还须由维护者将该 job 设为必需状态检查；这属于仓库合并策略，不属于评测脚本的职责，也不是原 issue 的功能验收项。

## 明确不在本次范围

- 对 Query 与 Practice **正文**、Guidance、anti-pattern、例外或决策步骤做自动相似性/答案泄漏检查；
- 自动术语学习、语义改写、多模型投票或 masked-query 检索控制；
- 自动生成 Query、真实请求采样、来源/审核人的可验证审计系统；
- secrets/PII/prompt-injection 等内容安全扫描；
- 上下文摘要注入、decision-probe 或 benchmark 门禁、semantic CI、Registry 发布。

这些方向可以分别规划，但不能让未实现的检查阻塞 #26，亦不得写作当前 CI 已有能力。
