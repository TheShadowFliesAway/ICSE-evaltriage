# EvalTriage 论文写作指南

更新时间：2026-06-29

本文档用于把 `/home/ubuntu/zjx/EvalTriage` 当前项目状态转成 ICSE 2027 论文写作入口。它不是最终论文正文，而是写作时的事实底稿、叙事边界和结果口径清单。

## 1. 论文一句话

EvalTriage 研究的问题是：当具身 AI / robot evaluation pipeline 的 benchmark 结果相对 baseline 发生 deviation 时，开发者如何判断它是 flaky evaluation behavior、true regression、setup-sensitive engineering factor，还是证据不足的 unknown case。

核心方法是 factor-directed diagnosis：记录结构化 evaluation manifest，检测 deviation，基于 manifest diff 选择可疑 factor，并执行 budget-aware differential replay，用 replay 证据做 status classification、factor attribution 和 abstention。

## 2. 论文定位

EvalTriage 不是新的 robot policy、不是新的 benchmark，也不是提升成功率的方法。它是一个 software engineering for AI / testing and analysis 方向的诊断系统，目标是把具身 AI 评测里的不透明结果漂移变成可追踪、可复现、可归因的软件工程问题。

最适合投 ICSE Research Track 的角度：

- Problem formulation：定义 embodied AI evaluation deviation diagnosis。
- Empirical motivation：从开源具身 AI / robot learning 项目中挖掘真实 evaluation deviation 和 engineering factor。
- System design：manifest + deviation detection + differential replay + attribution report。
- Evaluation：用真实 LeRobot + LIBERO pipeline、真实 fault injection、failed-run artifacts、ablation 和 robustness appendix 评估诊断能力与成本。

## 3. RQ 和写作目标

建议正文保留 4 个 RQ：

| RQ | 写作目标 | 当前材料 |
|---|---|---|
| RQ1 | 具身 AI 评测偏差和工程影响因素是否真实存在、如何分类 | `RQ1/rq1_evidence.jsonl`、`EvalTriage_RQ1_tables.md`、overview 图 |
| RQ2 | EvalTriage 能否区分 setup-sensitive、flaky、true regression 和 unknown | setup-sensitive / unknown 已有强结果；true-regression 和 flaky 正在补实验 |
| RQ3 | 能否正确归因到具体 factor，并在证据不足时 abstain | paper-only、robustness、formal ablation 已有主要结果 |
| RQ4 | 能否降低诊断成本并减少盲目 rerun | `rq4_cost_metrics.csv`、case cost records、replay budget 对比 |

注意：当前 RQ2 不能写成完整完成。`/data/project/zjx/runs/evaltriage/cases` 下正式落盘的 `rq2_*` case 目前只有：

```text
rq2_true_regression_freeze_first_action_goal_tasks0to9_seed1000
rq2_true_regression_freeze_first_action_goal_tasks0to9_seed2000
rq2_true_regression_freeze_first_action_goal_tasks0to9_seed3000
```

`flaky` case 尚未正式落盘；`gripper_sign_flip` 还有 staging 目录，不能作为完成结果写入论文主表。

## 4. 方法章节骨架

建议方法章节按系统数据流写，而不是按代码模块流水账写：

1. Evaluation manifest
   - 记录 code、checkpoint、runtime、task、seed、evaluation protocol、observation、action、reset、metrics、episode outcomes。
   - 写作重点：manifest 不是普通日志，它是 factor comparison 和 replay planning 的输入。

2. Deviation detection
   - 支持 aggregate metrics，例如 success rate / mean reward。
   - 支持 failed-run deviation：baseline completed、current failed、replay completed。
   - 支持 paired episode outcome shift：aggregate success 不变时，episode-level 分布变化仍可构成 deviation。

3. Factor-directed differential replay
   - 不盲目 rerun whole benchmark。
   - 基于 manifest diff 和 suspected factor 运行小预算 replay，恢复或控制单个 factor。
   - 写作时强调 budget-aware 和 affected-task replay。

4. Diagnosis and attribution
   - 输出 `likely_setup_sensitive_deviation`、`likely_flaky_evaluation`、`likely_true_regression`、`unknown_engineering_factor`。
   - 对 factor 进行 Top-1 / Top-3 ranking。
   - 当无 deviation、replay 冲突、manifest 缺字段或证据不足时 abstain。

5. Developer-facing report
   - 报告 deviation、affected tasks、top factors、evidence、recommended actions。
   - 强调它服务 merge/release/reproduction 决策。

## 5. 当前已完成的主要事实

### RQ1 evidence

- RQ1 frozen input：`/home/ubuntu/zjx/EvalTriage/RQ1/rq1_evidence.jsonl`
- 共 473 条 GitHub issue / PR evidence。
- 覆盖 15 个项目。
- `deviation_and_factor` 为 258 条，`deviation_only` 为 144 条，`factor_only` 为 71 条。
- `unknown_or_not_specified` 为 153 / 473 = 32.35%，应写成真实 issue 常缺少足够归因证据，因此需要 manifest、replay 和 abstention。

### Paper-only main results

Paper-only 结果目录：

```text
/data/project/zjx/runs/evaltriage/metrics/paper_full_matrix_after_main_20260629
```

当前 paper-only 口径：

| Bucket | Cases | Detected | 结论 | Top-1 |
|---|---:|---:|---|---|
| completed-rollout main matrix | 16 | 12 | 12 success candidate + 4 negative calibration | 12/12 among detected |
| failed-run appendix | 4 | 4 | 4 failure-supported | 4/4 |
| paper-only combined | 20 | 16 | 12 success + 4 failure + 4 negative calibration | 16/16 among detected |

保守口径：如果把 negative calibration 放进分母，paper-only combined 为 16/20 = 0.8。

### Robustness appendix

Robustness 结果目录：

```text
/data/project/zjx/runs/evaltriage/metrics/paper_robustness_20260629
```

Combined robustness 口径：

- paper-only：20 cases。
- robustness-only：35 cases。
- combined：55 cases。
- combined 包含 43 completed-rollout cases 和 12 failed-run cases。
- combined 结论：31 success candidate、12 failure-supported、12 negative calibration。
- combined detected/applicable Top-1：43/43 = 1.0。
- negative calibration false attribution：0/12。

写作建议：正文主表使用 paper-only 20 cases，appendix 或 robustness subsection 展示 combined 55-case 结果。不要用 robustness 替换主表，否则读者会误以为主实验规模和附录扩展混在一起。

### Formal ablation

Ablation 结果目录：

```text
/data/project/zjx/runs/evaltriage/metrics/paper_ablation_with_robustness_20260629
```

Combined ablation 关键结果：

| Method | Detected/applicable Top-1 | All-case Top-1 | 关键解释 |
|---|---:|---:|---|
| EvalTriage full | 43/43 = 1.0 | 43/55 = 0.782 | 完整 manifest + replay + episode evidence |
| no replay | 38/43 = 0.884 | 38/55 = 0.691 | checkpoint cases 容易被 manifest-only 误导 |
| no episode evidence | 20/31 = 0.645 | 20/55 = 0.364 | harness/reset 的 paired episode shift 会丢失 |
| manifest diff heuristic | 35/43 = 0.814 | 35/55 = 0.636 | negative calibration 上 12/12 误归因 |
| logs-only failure regex | 12/12 on failed-run only | 12/55 = 0.218 | 对 failed-run 有用，但覆盖面极窄 |

写作重点：EvalTriage 的贡献不只是检测数值下降，而是结合 replay 和 episode evidence 避免过度归因。

## 6. 结果写作口径

建议正文使用以下表述：

- “In detected and applicable cases, EvalTriage attributes all deviations to the expected factor.”
- “When there is no thresholded deviation, EvalTriage abstains instead of attributing manifest differences.”
- “Negative calibration cases are not failures of factor attribution; they test over-attribution resistance.”
- “Completed-rollout and failed-run cases are reported separately because their observable evidence differs.”
- “RQ2 true-regression/flaky experiments are being extended; current main results should not claim full coverage of those two statuses.”

避免以下表述：

- 不要说 EvalTriage 在所有 55 cases 中 accuracy 是 100%。正确口径是 detected/applicable 43/43，all-case denominator 是 43/55。
- 不要把 seed/randomness 写成已成功归因 factor。当前它主要是 negative calibration。
- 不要把 dependency completed-rollout 写成强成功 factor。它在 completed rollout 中 mostly negative calibration，但在 failed-run appendix 中有 failure-supported 证据。
- 不要把 smoke、calibration、validation probe 混入主表。
- 不要把 `rq2_status_enhanced_20260629` 当成完整 RQ2 final result；它缺少正式 flaky 和完整 true-regression cases。

## 7. 推荐论文结构

在 10 页正文限制下，当前 LaTeX 骨架已经按以下结构拆到 `sections/` 目录。`main.tex` 只负责 IEEEtran 模板、宏、标题、keywords、`\input{}` 装配和 bibliography。

| 顺序 | 文件 | Section | 建议页数 | 叙事任务 |
|---:|---|---|---:|---|
| 0 | `sections/abstract.tex` | Abstract | 0.25 | 一段讲清问题、方法、数据、主要结果；等 RQ2 补完后再定稿 |
| 1 | `sections/intro.tex` | Introduction | 1.0 | 把 evaluation deviation 立成 SE 问题，给出 gap、insight、贡献和结果亮点 |
| 2 | `sections/motivating_example.tex` | Motivating Example | 0.7 | 用一个 LeRobot/LIBERO baseline-current-replay case 让读者直观看到为什么 metric drop + manifest diff 不够 |
| 3 | `sections/background_problem.tex` | Background and Problem Definition | 0.9 | 定义 embodied AI evaluation pipeline、deviation、diagnosis task、factor space |
| 4 | `sections/empirical_study.tex` | Empirical Study of Evaluation Deviations | 1.1 | 回答 RQ1：473 evidence、15 projects、taxonomy、unknown motivation |
| 5 | `sections/approach.tex` | Approach | 1.8 | 按数据流写 manifest、deviation detection、factor-directed replay、attribution/abstention、report |
| 6 | `sections/evaluation.tex` | Evaluation | 2.3 | 合并写 setup、RQ2 status、RQ3 attribution/abstention、RQ4 cost、ablation/robustness |
| 7 | `sections/discussion_threats.tex` | Discussion and Threats to Validity | 0.7 | 解释 negative calibration、completed vs failed-run、validity threats |
| 8 | `sections/related_work.tex` | Related Work | 0.8 | 对齐 flaky tests、SE for AI、robotics reproducibility、experiment provenance |
| 9 | `sections/conclusion.tex` | Conclusion | 0.2 | 回扣问题定义和方法价值，带最终数字 |

当前结构的核心叙事顺序是：先让读者相信“evaluation deviation diagnosis”是真问题，再用 motivating example 说明为什么需要 replay evidence，然后用 RQ1 证明问题普遍存在，接着介绍系统，最后用 RQ2-RQ4 证明 status、attribution/abstention 和 cost。

这篇论文最容易超页的是 RQ1 evidence 表、RQ3 factor matrix 和 robustness 细节。建议正文只放 1 个 EvalTriage overview 图、1 个 motivating example 图、1 个 RQ1 summary table、1 个 paper-only result table、1 个 ablation table、1 个 cost table；详细 factor-by-factor robustness 放 appendix、artifact 或 online supplement。

## 8. 推荐图表清单

正文优先图表：

- Fig. 1：EvalTriage pipeline。输入 baseline/current runs，输出 diagnosis report。
- Fig. 2：RQ1 taxonomy overview。可复用 `RQ1/figures/rq1_evidence_overview.pdf`。
- Table 1：RQ1 top factors / symptoms / evidence role。
- Table 2：Paper-only main matrix，区分 completed-rollout 和 failed-run。
- Table 3：Formal ablation。
- Table 4：RQ4 cost summary。

Appendix / supplement：

- Robustness 55-case combined factor matrix。
- Failed-run case details。
- Negative calibration examples。
- RQ2 true-regression/flaky 补充结果，等正式落盘后再加入。

## 9. 当前最该补的实验

优先补 RQ2，因为它直接影响 Research Question 完整性：

1. 完成 `rq2_true_regression_*` 剩余 cases。
   - 现有配置包括 `zero_action_output`、`freeze_first_action`、`translation_sign_flip`、`gripper_sign_flip`。
   - 当前只有 `freeze_first_action` 三个 seed 正式落盘。

2. 完成 `rq2_flaky_*` cases。
   - 当前有 fixed/unfixed init、async batch2/batch4、sync batch1 configs。
   - 目前没有正式 case 目录。

3. 重新生成 RQ2 status metrics。
   - 只有当 true-regression 和 flaky case 正式落盘后，才能把 RQ2 表写入论文。

4. 清理或标记 staging。
   - 当前存在 `gripper_sign_flip` replay staging 目录；写作前不要把 staging 当作成功产物。

## 10. 代码与数据入口

论文写作时优先引用这些路径：

```text
/home/ubuntu/zjx/EvalTriage/EvalTriage_final_plan.md
/home/ubuntu/zjx/EvalTriage/EvalTriage_experiment_plan.md
/home/ubuntu/zjx/EvalTriage/EvalTriage_implementation_checklist.md
/home/ubuntu/zjx/EvalTriage/RQ1/EvalTriage_RQ1_tables.md
/data/project/zjx/runs/evaltriage/metrics/paper_full_matrix_after_main_20260629
/data/project/zjx/runs/evaltriage/metrics/paper_robustness_20260629
/data/project/zjx/runs/evaltriage/metrics/paper_ablation_with_robustness_20260629
```

实现入口：

```text
evaltriage/cli.py
evaltriage/schemas.py
evaltriage/case_runner.py
evaltriage/detection/deviation.py
evaltriage/diagnosis/attribution.py
evaltriage/replay/planner.py
evaltriage/metrics/aggregate.py
evaltriage/metrics/ablation.py
evaltriage/metrics/rq2.py
```

## 11. 与“读取项目 md 文件”对话的衔接

本机 Codex 对话“读取项目 md 文件”的早期结论是：EvalTriage 的主线是 manifest、deviation detection、factor-directed replay 和 attribution；当时已确认 RQ1 evidence、CLI/schema/run 四件套、LeRobot/LIBERO validation foundation，以及 ManiSkill random policy 不适合作为论文级 validation。

当前状态相对那次对话已有重要更新：

- paper main matrix 已经真实跑完，不只是 validate-only。
- failed-run artifact schema 已落地。
- formal ablation 已落地。
- robustness appendix 已扩到 combined 55 cases。
- RQ2 true-regression/flaky 仍在补，不能提前完成叙事。

写论文时以本文档的状态为准，并在后续补完 RQ2 后更新。
