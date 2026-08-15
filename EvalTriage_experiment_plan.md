# EvalTriage RQ 对齐实验规划

## 0. 当前对齐结论

本文档服务于 [EvalTriage_final_plan.md](/home/ubuntu/zjx/EvalTriage/EvalTriage_final_plan.md) 中的定稿 idea：当具身 AI evaluation pipeline 出现相对 baseline 的 deviation 时，EvalTriage 通过 manifest、deviation detection、factor-directed replay 和 attribution report 判断偏差属于 flaky evaluation behavior、true regression，还是 unknown / setup-sensitive engineering factor。

当前决策：

- RQ1 的 GitHub evidence mining 已整理为冻结输入，本仓库实验计划不重复实现该挖掘流程。
- 本文档重点规划 RQ2、RQ3、RQ4 的 benchmark 运行、fault injection、replay、metrics 和 artifact。
- 最终实现以 [EvalTriage_implementation_plan.md](/home/ubuntu/zjx/EvalTriage/EvalTriage_implementation_plan.md) 为准；本文档只保留 RQ 对齐、实验矩阵和论文指标解释。
- 后续代码从一开始就按最终可用系统的 schema、CLI、case 矩阵和 artifact 设计实现，不做只能跑单 case 的临时版本。
- LeRobot + LIBERO 主实验只使用一个 primary policy：`lerobot/pi0_libero_finetuned_v044`。
- `lerobot/pi0_libero_base` 不进入核心实验矩阵；它只作为可选 external-validity 或额外 checkpoint mismatch case，不是 EvalTriage 方法成立的必要条件。

一个 policy 足够的理由：

- final plan 要求的是 baseline/current/replay 之间的工程因素差异，不要求跨 policy 对照。
- `checkpoint_config_compatibility` 可以通过同一 policy 的 checkpoint、config、preprocessor、postprocessor 或 feature schema mismatch 构造。
- `action_controller_interface`、`observation_sensor_preprocessing`、`evaluation_protocol_metric`、`reset_or_initial_state`、`dependency_runtime_environment`、`semantic code regression` 都不依赖第二个 policy。
- 引入第二个 policy 会扩大下载、调试和矩阵成本，但不会直接提高 RQ2-RQ4 的核心可证性。

## 1. RQ 到实验的映射

### RQ1：taxonomy evidence

状态：已整理为本仓库内的冻结输入。

本仓库当前 RQ1 输出：

- 原始 evidence：`/home/ubuntu/zjx/EvalTriage/RQ1/rq1_evidence.jsonl`；
- 统计汇总：`/home/ubuntu/zjx/EvalTriage/RQ1/EvalTriage_RQ1_tables.md`；
- 证据表：`/home/ubuntu/zjx/EvalTriage/RQ1/tables/rq1_evidence_index.csv`；
- taxonomy 计数：`/home/ubuntu/zjx/EvalTriage/RQ1/tables/rq1_taxonomy_counts.csv`；
- case mapping：`/home/ubuntu/zjx/EvalTriage/RQ1/tables/rq1_case_mapping.csv`；
- RQ1 overview 图：`/home/ubuntu/zjx/EvalTriage/RQ1/figures/rq1_evidence_overview.pdf`。

关键结论：

- `473` 条 GitHub issue / PR evidence 覆盖 `15` 个项目；
- `258` 条为 `deviation_and_factor`，`144` 条为 `deviation_only`，`71` 条为 `factor_only`；
- `unknown_or_not_specified` 有 `153 / 473 = 32.35%`。这不是一个待归因 factor，而是说明真实 issue 中经常缺少足够证据判断根因，支撑 EvalTriage 需要 manifest、replay、attribution，以及证据不足时的 abstention / unknown handling。

本文档不再规划 GitHub mining 代码，只把 RQ1 输出作为实验输入和 case 设计依据。

### RQ2：deviation status classification

问题：相比 single-run、fixed-seed、rerun-k 和 naive statistical gate，EvalTriage 能否更准确地区分：

- `likely_flaky_evaluation`
- `likely_setup_sensitive_deviation`
- `likely_true_regression`
- `unknown_engineering_factor`

实验输入：

- baseline run manifest；
- injected / current run manifest；
- repeated run summaries；
- replay summaries；
- 每个 case 的 ground-truth expected status。

主要指标：

- status classification precision / recall / F1；
- false alarm rate；
- missed regression rate；
- unknown rate。

### RQ3：factor attribution / abstention

问题：EvalTriage 能否在证据充分时把 deviation 归因到正确的 engineering factor，并在证据不足时避免高置信错误归因。

目标 factors：

- `seed_or_randomness`
- `reset_or_initial_state`
- `object_scene_task_initialization`
- `simulator_physics_rendering`
- `dependency_runtime_environment`
- `action_controller_interface`
- `observation_sensor_preprocessing`
- `checkpoint_config_compatibility`
- `evaluation_protocol_metric`
- `evaluation_script_harness`
- `data_dataset_format`
- `semantic_code_regression`

注意：`unknown_or_not_specified` 不作为普通 factor 参与 Top-1 / Top-3 / MRR 的 attribution accuracy。它用于评估 EvalTriage 的 abstention / unknown handling：当 manifest 字段缺失、replay 证据冲突、或可用证据不足时，系统应输出 `unknown_engineering_factor` 并说明缺失证据，而不是强行猜测某个 factor。

`semantic_code_regression` 是 EvalTriage 的诊断标签，不是 RQ1 原始 primary factor category。它由 `code.semantic_bug_flag`、code diff 或 harness 逻辑变化支撑，可映射到 RQ1 的 `evaluation_script_harness`、`training_evaluation_interaction` 或 `ci_regression_evaluation` 证据类别。

主要指标：

- Top-1 factor attribution accuracy；
- Top-3 factor attribution accuracy；
- MRR for factor ranking；
- unsupported / unknown factor rate；
- unknown / abstention correctness。

### RQ4：diagnosis cost

问题：EvalTriage 能否在保持诊断准确率的同时减少盲目重跑成本。

主要指标：

- rerun count；
- GPU minutes / GPU hours；
- wall-clock diagnosis time；
- diagnosis latency；
- pipeline overhead；
- affected-task replay 相比 full benchmark replay 的成本比例。

## 2. 实验平台角色

### 2.1 LeRobot + LIBERO：真实 VLA evaluation pipeline

使用：

- primary policy：`lerobot/pi0_libero_finetuned_v044`；
- LIBERO task suites：`libero_spatial`、`libero_object`、`libero_goal`、`libero_10`；
- LeRobot 集成的 LIBERO simulation environment；
- policy 自带 config、preprocessor、postprocessor 和 train config；
- evaluation 运行产生的 observation、action、reward、success/failure 和 logs。

作用：

- 证明 EvalTriage 能处理真实 VLA / robot evaluation pipeline 中的复杂评测偏差；
- 覆盖 checkpoint/config/processor/action/evaluation protocol 等 LeRobot/LIBERO 真实工程因素。

不作为核心矩阵的内容：

- `lerobot/pi0_libero_base`；
- SmolVLA、XVLA、GR00T N1.5；
- `libero_90`。

这些可以作为后续 external validity，而不是 RQ2-RQ4 的第一批必要实验。

### 2.2 ManiSkill：可控 factor injection

固定任务：

- `PickCube-v1`
- `StackCube-v1`
- `PegInsertionSide-v1`
- `PushCube-v1`

作用：

- 提供更干净的 controlled injection；
- 更容易控制 seed、reset、object pose、controller、observation、simulator/task config；
- 支撑 RQ3 的 factor attribution accuracy。

Policy 选择原则：

- 不追求大模型性能；
- 优先使用稳定、可重复、运行成本低的官方 / 社区 baseline policy；
- 如果 baseline policy 难以复现，使用 scripted policy 或已有 checkpoint，但输出 schema、case 标注和 cost accounting 仍按最终系统要求实现。

## 3. 运行产物和目录

代码、wrapper、配置和文档：

```text
/home/ubuntu/zjx/EvalTriage
```

大资源和实验输出：

```text
/data/project/zjx
```

每次 run 的标准输出：

```text
/data/project/zjx/runs/evaltriage/runs/{run_id}/manifest.json
/data/project/zjx/runs/evaltriage/runs/{run_id}/episodes.jsonl
/data/project/zjx/runs/evaltriage/runs/{run_id}/summary.json
/data/project/zjx/runs/evaltriage/runs/{run_id}/logs.txt
```

每个 diagnosis case 的标准输出：

```text
/data/project/zjx/runs/evaltriage/cases/{case_id}/case.json
/data/project/zjx/runs/evaltriage/cases/{case_id}/deviation.json
/data/project/zjx/runs/evaltriage/cases/{case_id}/manifest_diff.json
/data/project/zjx/runs/evaltriage/cases/{case_id}/replay_plan.json
/data/project/zjx/runs/evaltriage/cases/{case_id}/diagnosis.json
```

## 4. Manifest 和 Episode 记录

每个 baseline、current、replay run 都必须生成 manifest。最终 schema 以 `EvalTriage_implementation_plan.md` 第 4 节为准，本文只列出论文实验必须能解释的核心字段：

```json
{
  "run_id": "libero_pi0_goal_baseline_seed1000",
  "platform": "lerobot_libero",
  "project": "lerobot",
  "benchmark": "libero",
  "task_suite": "libero_goal",
  "policy_path": "lerobot/pi0_libero_finetuned_v044",
  "checkpoint_revision": "",
  "checkpoint_checksum": "",
  "code_commit": "",
  "seed": 1000,
  "eval_command": "",
  "eval_config": {
    "n_episodes": 50,
    "batch_size": 1,
    "max_parallel_tasks": 1,
    "n_action_steps": null,
    "control_mode": ""
  },
  "runtime_env": {
    "python": "",
    "torch": "",
    "cuda": "",
    "gpu": "",
    "driver": "",
    "mujoco": "",
    "lerobot": "",
    "os": ""
  },
  "observation": {
    "image_keys": [],
    "camera_names": [],
    "preprocessors": []
  },
  "action": {
    "action_dim": null,
    "control_mode": "",
    "normalization": "",
    "postprocessors": []
  },
  "metrics": {
    "success_rate": null,
    "mean_reward": null,
    "num_episodes": null,
    "num_success": null,
    "num_failure": null
  }
}
```

Episode JSONL 每行必须能支撑 deviation detection、replay 和 cost accounting。最终 schema 以 `EvalTriage_implementation_plan.md` 为准，核心字段包括：

```json
{
  "episode_id": 0,
  "task": "libero_goal",
  "seed": 1000,
  "success": true,
  "reward": 1.0,
  "num_steps": 183,
  "termination_reason": "success",
  "error": null,
  "behavior_tags": []
}
```

如果出现异常行为，`behavior_tags` 可记录：

```json
["zero_actions", "stuck_policy", "jitter", "timeout", "crash"]
```

## 5. Case Families

### 5.1 Reference / baseline distribution

目的：建立 baseline distribution 和 repeated-run variance。

配置：

- primary policy：`lerobot/pi0_libero_finetuned_v044`；
- suites：`libero_spatial`、`libero_object`、`libero_goal`、`libero_10`；
- seeds：`1000`、`1001`、`1002`；
- per-suite episodes：正式实验固定后写入 `configs/experiments/full.yaml`，并在每个 `summary.json` 和 metrics CSV 中记录。

验收标准：

- 每个 run 有完整 `manifest.json`、`episodes.jsonl`、`summary.json`、`logs.txt`；
- repeated-run variance 可以用于 RQ2 的 flaky / non-flaky 判断阈值。

### 5.2 Setup-sensitive factor cases

每个 case 只改变一个主要 factor，并记录 ground truth。

Planned categories：

- `evaluation_protocol_metric`
  - 例子：改变 `eval.n_episodes`、episode length、success aggregation 或 metric definition。
- `action_controller_interface`
  - 例子：改变 action scaling、normalization、postprocessor、gripper mapping 或 action dimension order。
- `observation_sensor_preprocessing`
  - 例子：改变 image key、camera order、image flip / rotation、resolution、normalization stats 或 missing observation key。
- `checkpoint_config_compatibility`
  - 例子：同一 finetuned checkpoint 搭配错误 config、缺失 postprocessor、错误 feature schema 或错误 checkpoint revision。
- `reset_or_initial_state` / `object_scene_task_initialization`
  - 例子：改变 reset order、initial state、object pose 或 scene initialization。
- `dependency_runtime_environment` / `simulator_physics_rendering`
  - 例子：改变 MuJoCo、LeRobot、torch/transformers 版本，或渲染后端。
- `data_dataset_format`
  - 例子：删除 dataset feature column、破坏 parquet/video reference、制造 dataset schema 与 policy/eval wrapper 的不兼容。

验收标准：

- manifest diff 能捕获被改变的 factor；
- current run 相对 baseline 产生可检测 deviation；
- replay 恢复该 factor 后，结果明显接近 baseline 或错误消失。

### 5.3 Flaky cases

目的：验证 EvalTriage 能识别同配置下的不稳定，而不是误报为具体工程 factor。

候选机制：

- 同 manifest / 同配置 repeated runs 出现高 variance；
- simulator seed 或 task initialization 没有被完全控制，但 manifest 初版无法充分记录；
- headless rendering 或 runtime nondeterminism 导致 episode-level variance。

验收标准：

- manifest diff 很小或没有可解释工程差异；
- repeated runs 的 variance 超过预设阈值；
- diagnosis status 应为 `likely_flaky_evaluation`，而不是强行归因到 action/sensor/checkpoint。

### 5.4 True regression cases

目的：验证 EvalTriage 不把真实语义代码回归误判成 setup factor。

候选机制：

- action adapter semantic bug；
- eval wrapper logic bug；
- env wrapper logic bug；
- success condition implementation bug；
- action dimension order changed by code patch。

验收标准：

- manifest 中工程环境因素基本不变；
- controlled replay 无法通过恢复 action/sensor/checkpoint/protocol 等外部 factor 解释 deviation；
- code diff 指向语义逻辑变化；
- diagnosis status 应为 `likely_true_regression` 或 `true_regression_candidate`。

### 5.5 Unknown cases

目的：验证证据不足时 EvalTriage 会输出 unknown，而不是过度归因。RQ1 中 `unknown_or_not_specified = 153 / 473 = 32.35%`，说明真实 issue 经常只有 deviation symptom，没有足够 evidence 支持具体 factor 归因；unknown cases 因此是必要性和边界能力实验，不是一个普通 factor 归因任务。

候选机制：

- 隐藏或删除关键 manifest 字段；
- 引入组合因素但只允许有限 replay budget；
- 构造当前 taxonomy 尚未覆盖或无法观测的 factor；
- replay 结果互相冲突或只有弱改善。

验收标准：

- 不参与普通 Top-1 / Top-3 factor accuracy；
- Top-1 不应给出高置信错误 factor；
- diagnosis status 应为 `unknown_engineering_factor` 或低置信 setup-sensitive deviation；
- report 应明确缺失证据和建议补采字段。

## 6. Baselines 和 Ablations

### 6.1 比较对象

- `single_run_judgment`
  - 只根据一次 current vs baseline 的 metric drop 判断。
- `fixed_seed_evaluation`
  - 使用固定 seed 的 single comparison。
- `rerun_k`
  - 对同一 case 做 k 次 rerun，使用 mean / majority vote 判断 deviation。
- `naive_statistical_gate`
  - 使用 mean、variance、confidence interval 或 fixed threshold 判断。
- `original_benchmark_script`
  - 只使用原始 benchmark logs，不使用 manifest、replay 或 attribution。
- `manifest_diff_heuristic`
  - 使用 manifest diff 生成 factor ranking，但不执行 replay。
- `evaltriage_no_episode_evidence`
  - 移除 episode-level evidence 的 ablation。
- `evaltriage_no_replay`
  - 只做 detection 和 manifest diff，不做 differential replay。
- `evaltriage_full`
  - manifest + deviation detection + factor-directed replay + attribution report。

### 6.2 公平性原则

- 所有方法使用同一组 case、baseline run 和 current run。
- cost comparison 必须记录 rerun count、episode count、GPU minutes 和 wall-clock minutes。
- `rerun_k` 的 k 值需要在正式实验前固定，例如 `k=3` 或 `k=5`。
- 不产生 factor ranking 的 baseline 不参与 RQ3 Top-k/MRR，或单独标记为 `N/A`，不能和 attribution 方法混在一起解释。

## 7. Planned Experiment Matrix

### 7.1 LeRobot + LIBERO 核心矩阵

```text
Policy:
- lerobot/pi0_libero_finetuned_v044

Suites:
- libero_spatial
- libero_object
- libero_goal
- libero_10

Seeds:
- 1000
- 1001
- 1002

Case families:
- setup_sensitive_factor
- flaky
- true_regression
- unknown

Setup-sensitive injection categories:
- evaluation_protocol_metric
- evaluation_script_harness
- action_controller_interface
- observation_sensor_preprocessing
- checkpoint_config_compatibility
- reset_or_initial_state
- dependency_runtime_environment
- data_dataset_format
```

最终目标规模：

```text
1 policy x 4 suites x 3 seeds = 12 baseline/reference groups
8 setup-sensitive categories x >=3 cases = >=24 controlled setup-sensitive cases
flaky cases = 3-6 cases
true regression cases = 3-6 cases
unknown / abstention cases = 3-6 cases
```

### 7.2 ManiSkill 补充矩阵

```text
Tasks:
- PickCube-v1
- StackCube-v1
- PegInsertionSide-v1
- PushCube-v1

Seeds:
- 3 seeds per task, validation 后可扩到 5 seeds

Injection categories:
- seed_or_randomness
- reset_or_initial_state
- object_scene_task_initialization
- action_controller_interface
- observation_sensor_preprocessing
- simulator_physics_rendering
```

最终目标规模：

```text
4 tasks x 4 categories x 3 seeds = >=48 controlled runs
扩展后覆盖 4 tasks x 6 categories x 3 seeds = 72 controlled runs
```

## 8. Metrics 表结构

最终每个 case 至少整理为一行：

```json
{
  "case_id": "libero_pi0_action_steps_mismatch_001",
  "platform": "lerobot_libero",
  "policy": "lerobot/pi0_libero_finetuned_v044",
  "benchmark": "libero_goal",
  "case_family": "setup_sensitive_factor",
  "injected_factor": "action_controller_interface",
  "expected_status": "likely_setup_sensitive_deviation",
  "expected_factor": "action_controller_interface",
  "baseline_success_rate": 0.84,
  "current_success_rate": 0.12,
  "deviation_symptom": "success_rate_drop_or_mismatch",
  "evaltriage_status": "likely_setup_sensitive_deviation",
  "evaltriage_top1_factor": "action_controller_interface",
  "evaltriage_top3_factors": [
    "action_controller_interface",
    "evaluation_protocol_metric",
    "checkpoint_config_compatibility"
  ],
  "rerun_count": 2,
  "episode_count": 100,
  "gpu_minutes": 35,
  "wall_clock_minutes": 42,
  "artifact_path": "/data/project/zjx/runs/evaltriage/cases/libero_pi0_action_steps_mismatch_001"
}
```

注意：

- 任何 metric 都必须关联 case config、data split、run path 和命令。
- smoke test 结果必须标记为 smoke，不能作为主结果。
- diagnostic / validation 过程中挑选出来的阈值不能直接作为 test result 汇报。

## 9. ICSE Artifact 规划

ICSE 角度的含义是：论文主实验可以很重，但给 reviewer / artifact evaluator 的材料不能要求他们完整重跑所有 GPU benchmark。应该提前准备一个轻量、可复现、可检查的 artifact 包。

建议 artifact 分三层：

- `smoke`
  - 小 episode 数、小 task subset；
  - 目标是验证代码能跑、manifest 能生成、report 格式正确；
  - 不作为论文主结果。
- `precomputed`
  - 完整实验的 manifest、episodes、summary、diagnosis、metrics CSV；
  - evaluator 可以复算表格和图，不需要重跑 GPU benchmark。
- `full`
  - 完整 benchmark 命令和环境说明；
  - 供有 GPU 资源的 evaluator 或未来复现实验使用。

Artifact 内容：

```text
artifact/
  README.md
  environment.md
  scripts/
  sample_runs/
  sample_cases/
  precomputed_metrics/
  reproduce_tables.sh
```

## 10. 最终实现顺序

执行顺序不代表先做临时版本；每一步都必须遵守最终 schema、目录和验收门槛。权威实现清单见 `EvalTriage_implementation_plan.md` 第 12 节。

1. 建立 Python package、CLI 和 config loader：`evaltriage-run`、`evaltriage-case`、`evaltriage-aggregate`、`evaltriage-artifact`。
2. 实现最终 run schema：`manifest.json`、`episodes.jsonl`、`summary.json`、`logs.txt`。
3. 实现 LeRobot + LIBERO runner，直接支持四个 suite、task subset、seed、episode count、GPU cost。
4. 实现 ManiSkill runner，直接支持四个任务和 scripted/registered baseline policy。
5. 实现 manifest collector、checksum、runtime/env capture、manifest diff。
6. 实现 injection registry 和所有 required operators。
7. 实现 replay planner、replay executor、factor restoration。
8. 实现 deviation detection 和 threshold config。
9. 实现 factor attribution、diagnosis report 和 unknown handling。
10. 实现 baselines / ablations。
11. 实现 metrics aggregation 和 RQ2-RQ4 CSV。
12. 导入 RQ1 evidence tables 并连接 case mapping。
13. 实现 artifact builder。
14. 跑 smoke split、validation split、full split，并固化最终结果。

## 11. 当前已验证事实和待实现项

已验证事实：

- `evaltriage-lr` 已可运行 LeRobot + LIBERO。
- `lerobot-eval` 1 episode policy smoke 已通过，输出目录为 `/data/project/zjx/runs/evaltriage/smoke_lerobot_eval_gpu0_20260627_004843`。
- `evaltriage-ms` 已可 import 和 reset ManiSkill 四个固定任务。
- `PushCube-v1` 已确认存在并通过 reset smoke。
- `evaltriage-lr-mujoco37` 已创建，可用于 dependency/runtime drift。
- `lerobot/libero_10_image` 已下载到 `/data/project/zjx/datasets/lerobot/libero_10_image`，可支撑 dataset/data-format fault。

待实现项：

- 将 `lerobot-eval` 的 summary/log 输出包装为标准 `manifest.json`、`episodes.jsonl`、`summary.json`、`logs.txt`；如果原始命令不直接暴露 episode-level detail，需要在 runner 层从可用输出提取，或 patch/封装 evaluation loop。
- 固定 `configs/experiments/full.yaml` 中的正式 episode 数、rerun-k、validation/test split 和 deviation thresholds。
- 读取 `/home/ubuntu/zjx/EvalTriage/RQ1/tables/rq1_case_mapping.csv` 和 `rq1_evidence_index.csv`，在每个 core planned case config 中连接 `rq1_evidence_refs`。
- 运行 validation split 后再冻结 threshold；不能在 full/test 结果上调参。
