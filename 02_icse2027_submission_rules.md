# ICSE 2027 Research Track 投稿规则摘录

更新时间：2026-06-29

官方来源：

- Research Track CFP：<https://conf.researchr.org/track/icse-2027/icse-2027-research-track>
- Submission site：<https://icse2027.hotcrp.com/>

本文档只整理和 EvalTriage 投稿直接相关的硬性规则与写作提醒。最终提交前必须再次核对官方页面。

## 1. 截止日期

ICSE 2027 Research Track 使用 single submission cycle。官方页面列出的时间均为 23:59:59 AoE (UTC-12h)。

| 事项 | 日期 |
|---|---|
| Mandatory abstract | 2026-06-23 |
| Submission | 2026-06-30 |
| Author response period | 2026-09-23 到 2026-09-25 |
| Notification | 2026-10-20 |
| Revision due | 2026-11-17 |
| Camera-ready for directly accepted papers | 2026-11-24 |
| Final decision for major revision papers | 2026-12-18 |
| Camera-ready for accepted major revision papers | 2027-01-25 |

写作提醒：当前日期为 2026-06-29，mandatory abstract deadline 已在 2026-06-23 过去；正式 submission deadline 是 2026-06-30 AoE。

## 2. 页数与模板

硬性规则：

- 使用 IEEE conference proceedings template。
- LaTeX 必须使用：

```latex
\documentclass[10pt,conference]{IEEEtran}
```

- 不要使用 `compsoc` 或 `compsocconf` options。
- 2027 年使用 IEEE format；官方页面特别说明上一年是 ACM format。
- 正文最多 10 页。
- 10 页正文包含所有 figures、tables、appendices 等。
- 额外最多 2 页只能放 references。
- 所有 submissions 必须是 PDF。
- Accepted papers 的 camera-ready main text 允许额外 1 页。

EvalTriage 写作动作：

- 现在就按 10 页正文设计，不要把 appendix 写进正文预算。
- References 控制在额外 2 页内，但不能把非 reference 内容塞进 reference pages。
- 不要改 `IEEEtran.cls`、字体、边距、列宽、全局行距或全局浮动体 spacing。

## 3. Desk-reject 风险

官方页面明确说，以下情况可能 desk reject：

- 不符合 IEEE conference proceedings formatting。
- 修改 spacing、font size 或其他格式要求。
- 并发投稿或已发表 / 正在其他 venue under review。
- 违反 plagiarism policies。
- confirmed hallucinated、fabricated 或 unverifiable references。
- 不遵守 double-anonymous review。

EvalTriage 写作动作：

- 每一条 reference 都必须能打开、能追踪、作者标题年份 venue 正确。
- 不要让 Codex 或其他 AI 工具凭记忆生成 bibliography。
- 引用 GitHub issue / PR evidence 时，优先从 RQ1 frozen input 和 CSV 中复制 URL，并抽查可访问性。
- PDF 生成后检查页数、字体嵌入、匿名性和 bibliography。

## 4. Double-anonymous review

ICSE 2027 Research Track 使用 double-anonymous review。提交稿不能暴露作者身份。

必须做到：

- 删除作者姓名和 affiliation。
- 对自己的 prior work 使用 third person 表述。
- 如果有 arXiv 或类似预印本，不要写“submitted to ICSE 2027”。
- 官方建议作者尽量推迟在 arXiv 等网站公开 submitted work，直到 notification 之后。
- 与 PC 的沟通必须通过 program co-chairs，不能直接联系个别 PC member。

EvalTriage 写作动作：

- Artifact 或 repo link 必须匿名化。
- 本地路径 `/home/ubuntu/zjx/...` 不能出现在提交稿。
- Acknowledgment 在匿名提交版本中通常先移除或匿名化。
- 自己的项目、账号、私有路径、机器名、commit author 信息都不要暴露。

## 5. Open Science Policy

官方页面说：sharing research artifacts 不是 submission 或 acceptance 的强制条件，但 expected default 是共享；如果不能共享，需要解释原因。

提交时需要做一项：

- 提供匿名 artifact 或 supplemental material，并在论文里说明访问方法；或
- 解释为什么不能共享；并且
- 如果接受后不打算公开 data / study materials，需要说明原因。

EvalTriage 写作动作：

- 准备匿名 artifact 分三层：
  - `smoke`：轻量运行，验证 CLI、manifest、diagnosis report。
  - `precomputed`：完整 manifest、episodes、summary、diagnosis、metrics CSV，可复算表格。
  - `full`：完整 GPU benchmark 命令和环境说明。
- 正文写 artifact availability statement，但匿名提交时不要暴露作者身份。
- 重 benchmark 可以不要求 reviewer 全量重跑；重点让 reviewer 能复算表格和检查 case artifacts。

## 6. Generative AI 使用披露

官方页面列出 ACM 和 IEEE 对 Generative AI 的要求：

- Generative AI 不能列为作者。
- 使用 Generative AI 生成内容需要在 work 中充分披露。
- IEEE 要求 AI-generated text 在 acknowledgments 中披露，并对使用 AI 生成文本的部分引用所用 AI system。
- 仅把工具用于类似 Grammarly 的拼写、语法、标点、清晰度编辑时，ACM 规则下不需要披露。
- 如果不确定是否需要披露，应保守披露。

EvalTriage 写作动作：

- 如果用 Codex/ChatGPT 辅助生成论文文本、表格说明、图 caption 或代码，应准备 disclosure。
- 匿名提交阶段可在非匿名性允许的方式下处理 disclosure；最终 camera-ready 必须按要求补齐。
- AI 不能生成不可核验 citation；所有引用必须手工或脚本核查。

## 7. Review criteria

官方 review criteria 包括：

- Novelty
- Rigor
- Relevance
- Verifiability and Transparency
- Presentation

EvalTriage 对应写作策略：

- Novelty：强调 evaluation deviation diagnosis 是 embodied AI evaluation pipeline 中被忽视的 SE 问题；manifest + factor-directed replay 的组合不是普通 flaky-test detection。
- Rigor：RQ1 frozen evidence、真实 LeRobot/LIBERO runs、failed-run artifacts、ablation、negative calibration、robustness appendix。
- Relevance：对应 Software Engineering for AI、Testing and Analysis、Analytics。
- Verifiability：precomputed artifacts、case configs、standard run outputs、metrics CSV。
- Presentation：每个 RQ 都要有清晰 takeaway，不要让机器人背景淹没 SE 贡献。

## 8. Research area 选择

最合适的 primary area：

- Software Engineering for AI

可考虑 secondary area：

- Testing and Analysis
- Analytics

理由：EvalTriage 的核心是 AI-based systems / embodied AI evaluation 的软件工程诊断、testing、analysis 和 reproducibility。

## 9. 提交前检查清单

- [ ] PDF 正文不超过 10 页。
- [ ] References 不超过额外 2 页，且 reference pages 只有 references。
- [ ] 使用 `\documentclass[10pt,conference]{IEEEtran}`。
- [ ] 没有 `compsoc` / `compsocconf`。
- [ ] 没有修改 IEEE spacing、font size、margins、column style。
- [ ] 作者、单位、路径、账号、artifact owner 已匿名化。
- [ ] References 全部可核验，没有 hallucinated citation。
- [ ] GitHub issue / PR evidence URL 可访问。
- [ ] Artifact link 匿名，或明确解释不能共享的原因。
- [ ] AI 使用披露策略已准备。
- [ ] 没有并发投稿。
- [ ] HotCRP conflicts 已完整填写。

## 10. 对 EvalTriage 当前写作的具体提醒

- 正文主结果优先用 paper-only 20 cases；combined 55 cases 放 robustness。
- RQ2 true-regression/flaky 正在补，不能在提交稿里声称 full status coverage 已完成，除非后续正式 artifacts 补齐并重新汇总。
- 不要把 smoke/calibration/validation probe 写成主结果。
- RQ1 的 473 evidence 是强动机，但不要把每类 issue 都塞正文；正文只放 summary 和 representative examples。
- ICSE 2027 对 reference integrity 明确严格，所有引用和 issue/PR 链接都要最后逐条核查。

