# EvalTriage 手绘叙事图提示词

更新时间：2026-06-30

本文档只保留需要手绘/生成的叙事图提示词。每张图一段提示词，中文为主，必要论文术语保留英文。提示词中统一只加入这些画面约束：二维，拼接感，图文并茂、写实风，参考ICSE软工类会议优秀论文配图。

## Fig. 1: Motivating Diagnosis Case

提示词：请为一篇投稿 ICSE 2027 Research Track 的 EvalTriage 论文生成 Fig. 1: Motivating Diagnosis Case，二维，拼接感，图文并茂、写实风，参考ICSE软工类会议优秀论文配图。这张图要表达论文的 motivating example：在 embodied-AI evaluation 中，metric drop 只是 observed symptom，不等于 diagnosis；EvalTriage 通过 manifest evidence 和 factor-directed replay 把一个模糊的 evaluation deviation 诊断成 setup-sensitive deviation。图中要讲清楚这个具体 case：Baseline run 使用 relative control，success = 0.80；Current run 改成 absolute control，success = 0.10，出现 observed deviation；manifest diff 显示 action.control_mode: relative -> absolute；factor-directed replay 恢复 baseline control mode 后 success recovers to 0.80；最终诊断为 Diagnosis: setup-sensitive deviation，Factor: action/controller interface。核心意图是让 ICSE 审稿人看到，仅报告 benchmark 分数变化是不够的，只有把配置变化和 replay recovery 连接起来，才能形成可解释、可行动的软件工程诊断。

## Fig. 2: Problem/Evidence Anatomy

提示词：请为一篇投稿 ICSE 2027 Research Track 的 EvalTriage 论文生成 Fig. 2: Problem/Evidence Anatomy，二维，拼接感，图文并茂、写实风，参考ICSE软工类会议优秀论文配图。这张图要表达论文的问题定义：embodied-AI evaluation deviation 不是一个单一现象，而是由 observed symptoms、evidence channels 和 diagnosis outcomes 共同构成的诊断问题。图中要讲清楚 metric drop、paired episode shift、failed run 这些只是 observed symptoms；aggregate metric、episode trace、manifest diff、failure record、replay recovery 这些 evidence channels 才能支撑 diagnosis；最终可能的 diagnosis outcomes 包括 setup-sensitive、flaky、true regression 和 unknown。核心意图是让 ICSE 审稿人理解，同一个 observed symptom 可能来自不同原因，manifest diff 只能提出 candidate factor，不能单独证明因果；如果证据缺失、冲突或不足，EvalTriage 应该输出 unknown，而不是强行归因。图中需要突出“A changed benchmark result is not itself a diagnosis.”这个中心思想。

## Fig. 4: EvalTriage Method Architecture

提示词：请为一篇投稿 ICSE 2027 Research Track 的 EvalTriage 论文生成 Fig. 4: EvalTriage Method Architecture，二维，拼接感，图文并茂、写实风，参考ICSE软工类会议优秀论文配图。这张图要表达 EvalTriage 的方法核心：系统输入不是单一 metric，而是一组 baseline/current/replay artifacts，包括 manifest.json、episodes.jsonl、summary.json、logs.txt 和 failure.json；EvalTriage 先检测 evaluation deviation，再从 manifest diff 中提出 factor candidates，并根据候选 factor 做 factor-directed replay；completed-rollout deviation 主要依赖 aggregate metrics 和 paired episode outcomes，failed-run deviation 主要依赖 failure stage 和 failure record；最后 Attribution / abstention 模块综合 symptom evidence、factor evidence、failure evidence 和 replay recovery，输出 diagnosis report。图要让 ICSE 审稿人理解，EvalTriage 的贡献不是保存日志，也不是简单比较分数，而是把 embodied-AI evaluation 的复杂运行产物组织成一个可审计的诊断流程，报告 status、ranked factor、supporting evidence、missing evidence 和 cost。

## Optional Fig.: Status Decision Logic

提示词：请为一篇投稿 ICSE 2027 Research Track 的 EvalTriage 论文生成 Optional Fig.: Status Decision Logic，二维，拼接感，图文并茂、写实风，参考ICSE软工类会议优秀论文配图。这张图要表达 EvalTriage diagnosis status 背后的保守判断逻辑：系统先判断是否存在 evaluation deviation；如果没有 detected deviation，则不做归因；如果有 deviation，则检查是否存在 candidate factor evidence；如果 replay 能恢复 baseline behavior 或 execution，则支持 setup-sensitive；如果 repeated comparable runs 表现出不稳定变化，则支持 flaky；如果 external-factor replay 不能解释 deviation，且 semantic code 或 policy change 仍是最合理原因，则支持 true regression；如果证据缺失、弱、冲突或无法支撑以上判断，则输出 unknown。核心意图是让 ICSE 审稿人看到 abstention 是 EvalTriage 的一等设计选择，不是失败兜底；论文强调的是证据责任，只有 evidence 足够时才做 attribution。
