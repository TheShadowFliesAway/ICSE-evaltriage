# EvalTriage 最终可用实验系统实现计划

更新时间：2026-06-27

本文档固化 EvalTriage 后续实现路线。原则是：**第一版实现就按论文最终可用系统设计和验收，不做只能跑通单 case 的临时最小版本**。执行时可以按模块推进，但每个模块的接口、产物、命名和验收都必须直接服务 RQ2-RQ4 的完整实验矩阵、ICSE artifact 和后续论文表格。

## 0. 当前事实

- Final idea：`/home/ubuntu/zjx/EvalTriage/EvalTriage_final_plan.md`
- RQ 对齐实验计划：`/home/ubuntu/zjx/EvalTriage/EvalTriage_experiment_plan.md`
- 资源清单：`/home/ubuntu/zjx/EvalTriage/EvalTriage_resource_inventory.md`
- 项目代码与文档根目录：`/home/ubuntu/zjx/EvalTriage`
- LeRobot 源码目录：`/home/ubuntu/zjx/lerobot`
- 大资源与实验输出根目录：`/data/project/zjx`
- LeRobot + LIBERO 主环境：`evaltriage-lr`
- ManiSkill 控制实验环境：`evaltriage-ms`
- MuJoCo drift 对照环境：`evaltriage-lr-mujoco37`
- 主 policy：`/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044`
- LIBERO runtime assets：`/data/project/zjx/assets/libero/assets`
- dataset/data-format fault 数据集：`/data/project/zjx/datasets/lerobot/libero_10_image`
- `lerobot-eval` 1 episode smoke 已通过：`/data/project/zjx/runs/evaltriage/smoke_lerobot_eval_gpu0_20260627_004843`

## 1. 最终交付定义

EvalTriage 最终可用实验系统必须包含以下能力：

- 能统一运行 LeRobot + LIBERO 和 ManiSkill 实验。
- 每个 baseline、current、replay run 都生成标准 `manifest.json`、`episodes.jsonl`、`summary.json`、`logs.txt`。
- 每个 diagnosis case 都生成 `case.json`、`deviation.json`、`manifest_diff.json`、`replay_plan.json`、`diagnosis.json`。
- 支持 setup-sensitive、flaky、true regression、unknown 四类 case family。
- 支持 RQ3 的 factor ranking：Top-1、Top-3、MRR，并支持证据不足时的 unknown / abstention correctness。
- 支持 RQ4 的 cost accounting：rerun count、episode count、GPU minutes、wall-clock minutes、diagnosis latency、pipeline overhead。
- 支持 baselines / ablations：single-run、fixed-seed、rerun-k、naive statistical gate、original benchmark logs、manifest-diff heuristic、no-episode-evidence、no-replay、EvalTriage full。
- 能输出论文表格所需的 `cases.csv`、`runs.csv`、`rq2_status_metrics.csv`、`rq3_factor_metrics.csv`、`rq4_cost_metrics.csv`。
- 能生成 ICSE artifact 三层材料：`smoke`、`precomputed`、`full`。

不接受只写 preliminary manifest、只包一条命令、只跑单 case、手动复制指标、或事后临时整理表格的实现。

## 2. 代码结构

在 `/home/ubuntu/zjx/EvalTriage` 下实现如下结构：

```text
evaltriage/
  __init__.py
  cli.py
  config.py
  schemas.py
  paths.py
  runtime.py
  runners/
    lerobot_libero.py
    maniskill.py
  injection/
    registry.py
    libero_cases.py
    maniskill_cases.py
  manifest/
    collect.py
    diff.py
    checksum.py
  detection/
    deviation.py
    thresholds.py
  replay/
    planner.py
    executor.py
  diagnosis/
    attribution.py
    report.py
  baselines/
    single_run.py
    fixed_seed.py
    rerun_k.py
    naive_statistical.py
    manifest_diff.py
  metrics/
    aggregate.py
    rq2.py
    rq3.py
    rq4.py
  artifact/
    build.py
scripts/
  evaltriage-run
  evaltriage-case
  evaltriage-aggregate
  evaltriage-artifact
configs/
  experiments/
  cases/
  thresholds/
tests/
```

约束：

- 不修改全局 shell 配置。
- 大输出只写 `/data/project/zjx/runs/evaltriage`。
- cache、checkpoint、dataset、assets 继续使用 `/data/project/zjx`。
- 真实 HF token 不进入任何文件。
- 默认 GPU 使用 `CUDA_VISIBLE_DEVICES=0`。
- LeRobot + LIBERO 默认关闭 `policy.compile_model` 和 async env，除非某个 case 明确测试这些因素。

## 3. 命令行接口

最终系统提供四个稳定命令。

### 3.1 evaltriage-run

用途：运行一个 baseline/current/replay run，并生成 run-level 标准产物。

必需参数：

```text
--platform {lerobot_libero,maniskill}
--run-id RUN_ID
--role {baseline,current,replay,smoke}
--suite SUITE_OR_TASK
--task-ids TASK_IDS
--seed SEED
--episodes N
--output-root /data/project/zjx/runs/evaltriage
```

LeRobot + LIBERO 参数：

```text
--policy-path /data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044
--libero-env evaltriage-lr
--mujoco-env evaltriage-lr-mujoco37
--obs-type pixels_agent_pos
--camera-size 360
--compile-model false
--use-async-envs false
```

ManiSkill 参数：

```text
--maniskill-env evaltriage-ms
--control-policy scripted_or_registered
--obs-mode state_or_rgbd
```

输出：

```text
/data/project/zjx/runs/evaltriage/runs/{run_id}/manifest.json
/data/project/zjx/runs/evaltriage/runs/{run_id}/episodes.jsonl
/data/project/zjx/runs/evaltriage/runs/{run_id}/summary.json
/data/project/zjx/runs/evaltriage/runs/{run_id}/logs.txt
```

### 3.2 evaltriage-case

用途：执行完整 diagnosis case，包括 baseline、current、replay、diagnosis 和 baselines/ablations。

必需参数：

```text
--case-config configs/cases/{case_id}.yaml
--output-root /data/project/zjx/runs/evaltriage
--rerun-k 3
--replay-budget EPISODES_OR_MINUTES
```

输出：

```text
/data/project/zjx/runs/evaltriage/cases/{case_id}/case.json
/data/project/zjx/runs/evaltriage/cases/{case_id}/deviation.json
/data/project/zjx/runs/evaltriage/cases/{case_id}/manifest_diff.json
/data/project/zjx/runs/evaltriage/cases/{case_id}/replay_plan.json
/data/project/zjx/runs/evaltriage/cases/{case_id}/diagnosis.json
/data/project/zjx/runs/evaltriage/cases/{case_id}/baselines.json
/data/project/zjx/runs/evaltriage/cases/{case_id}/cost.json
```

### 3.3 evaltriage-aggregate

用途：汇总所有 case 输出，生成 RQ2-RQ4 表格。

输入：

```text
--cases-root /data/project/zjx/runs/evaltriage/cases
--output-dir /data/project/zjx/runs/evaltriage/metrics/{timestamp}
```

输出：

```text
cases.csv
runs.csv
rq2_status_metrics.csv
rq3_factor_metrics.csv
rq4_cost_metrics.csv
failures.csv
```

### 3.4 evaltriage-artifact

用途：生成 ICSE artifact 目录。

输出：

```text
/data/project/zjx/runs/evaltriage/artifact/{timestamp}/
  README.md
  environment.md
  scripts/
  sample_runs/
  sample_cases/
  precomputed_metrics/
  reproduce_tables.sh
```

## 4. 标准数据结构

### 4.1 manifest.json

每个 run 必须记录：

```json
{
  "schema_version": "1.0",
  "run_id": "",
  "case_id": null,
  "role": "baseline",
  "platform": "lerobot_libero",
  "benchmark": "libero",
  "task_suite": "",
  "task_ids": [],
  "seed": 1000,
  "n_episodes": 50,
  "policy": {
    "path": "",
    "repo_id": "lerobot/pi0_libero_finetuned_v044",
    "checkpoint_checksum": "",
    "config_checksum": "",
    "preprocessor_checksum": "",
    "postprocessor_checksum": ""
  },
  "code": {
    "evaltriage_commit": "",
    "lerobot_commit": "",
    "dirty": false
  },
  "runtime_env": {
    "conda_env": "",
    "python": "",
    "torch": "",
    "cuda": "",
    "gpu": "",
    "driver": "",
    "mujoco": "",
    "robosuite": "",
    "mani_skill": "",
    "os": ""
  },
  "evaluation": {
    "command": "",
    "episode_length": null,
    "batch_size": 1,
    "use_async_envs": false,
    "compile_model": false,
    "metric_definition": "success_rate_percent"
  },
  "observation": {
    "obs_type": "",
    "camera_names": [],
    "image_keys": [],
    "height": null,
    "width": null,
    "preprocessing": []
  },
  "action": {
    "action_dim": null,
    "control_mode": "",
    "normalization": "",
    "postprocessing": []
  },
  "injection": {
    "enabled": false,
    "factor": null,
    "operator": null,
    "params": {}
  },
  "metrics": {
    "success_rate": null,
    "mean_reward": null,
    "num_episodes": null,
    "num_success": null,
    "num_failure": null
  },
  "cost": {
    "wall_clock_s": null,
    "gpu_minutes": null,
    "max_gpu_mem_mb": null
  }
}
```

### 4.2 episodes.jsonl

每行一个 episode：

```json
{
  "episode_id": 0,
  "task_suite": "libero_goal",
  "task_id": 0,
  "seed": 1000,
  "success": true,
  "reward": 1.0,
  "num_steps": 120,
  "termination_reason": "success",
  "error": null,
  "behavior_tags": [],
  "video_path": ""
}
```

### 4.3 case.json

每个 case 必须显式记录 ground truth：

```json
{
  "case_id": "",
  "platform": "",
  "case_family": "setup_sensitive_factor",
  "deviation_symptom": "",
  "expected_status": "likely_setup_sensitive_deviation",
  "expected_factor": "action_controller_interface",
  "injected_factor": "action_controller_interface",
  "injection_operator": "",
  "baseline_run_ids": [],
  "current_run_ids": [],
  "replay_run_ids": [],
  "rq1_evidence_refs": [],
  "artifact_split": "full"
}
```

### 4.4 diagnosis.json

诊断输出必须可直接计算 RQ2/RQ3：

```json
{
  "case_id": "",
  "status": "likely_setup_sensitive_deviation",
  "status_confidence": 0.0,
  "top_factors": [
    {
      "factor": "action_controller_interface",
      "confidence": 0.0,
      "evidence": []
    }
  ],
  "decision_rules_fired": [],
  "recommended_actions": [],
  "unknown_reason": null
}
```

## 5. 最终 Case 矩阵

### 5.1 LeRobot + LIBERO

固定资源：

```text
policy: pi0_libero_finetuned_v044
suites: libero_spatial, libero_object, libero_goal, libero_10
seeds: 1000, 1001, 1002
baseline episodes per suite/seed: 正式实验固定后写入 configs/experiments/full.yaml
rerun_k: 3
```

必须实现的 setup-sensitive factors：

```text
evaluation_protocol_metric
evaluation_script_harness
action_controller_interface
observation_sensor_preprocessing
checkpoint_config_compatibility
reset_or_initial_state
dependency_runtime_environment
data_dataset_format
```

每类 factor 至少 3 个 case，其中至少 1 个 case 必须有成功 replay，至少 1 个 case 必须验证 baseline/ablation 方法表现。

必须实现的 non-setup families：

```text
flaky: 3-6 cases
true_regression: 3-6 cases
unknown: 3-6 cases
```

unknown 不是普通 factor。它用于验证 EvalTriage 在证据不足、manifest 字段缺失、replay 结果冲突或多因素混杂时能够 abstain，输出 `unknown_engineering_factor` 和缺失证据说明，而不是强行给出高置信错误 factor。unknown cases 不参与普通 Top-1 / Top-3 / MRR attribution accuracy，应单独计算 unknown / abstention correctness。

### 5.2 ManiSkill

固定任务：

```text
PickCube-v1
StackCube-v1
PegInsertionSide-v1
PushCube-v1
```

必须实现的 factors：

```text
seed_or_randomness
reset_or_initial_state
object_scene_task_initialization
action_controller_interface
observation_sensor_preprocessing
simulator_physics_rendering
```

每个任务至少覆盖 4 类 factor；最终矩阵不少于 48 个 ManiSkill controlled runs。

## 6. Injection 设计要求

所有 injection 必须是可配置、可复现、可逆的 operator，不允许手改代码后忘记恢复。

必须实现的 operator：

```text
eval_protocol.change_episode_length
eval_protocol.change_success_aggregation
evaluation_script.modify_harness_flag
action.scale_multiplier
action.drop_postprocessor
action.reorder_dimensions
observation.swap_camera_keys
observation.image_flip
observation.drop_image_key
checkpoint.remove_processor_stats
checkpoint.config_feature_mismatch
reset.disable_fixed_init_state
maniskill.change_object_pose
runtime.switch_mujoco_env
dataset.remove_feature_column
dataset.corrupt_video_or_parquet_reference
code.semantic_bug_flag
manifest.hide_factor_fields
```

每个 operator 必须定义：

```text
factor
expected symptom
required platform
config params
replay reversal
expected status
expected factor
rq1_factor_category
rq1_evidence_refs
rq1_support_level: evidence_backed / synthetic_stress / extension
validation checks
```

## 7. Replay 和 Attribution

Replay planner 必须根据 manifest diff、deviation symptom、case family 和 budget 生成排序计划。

Replay 类型：

```text
restore_seed_or_init
restore_action_interface
restore_observation_pipeline
restore_checkpoint_config
restore_eval_protocol
restore_runtime_env
restore_dataset_format
rerun_same_manifest
affected_task_subset_replay
```

Attribution 规则：

- 如果某个 replay 恢复 baseline behavior，则对应 factor high confidence。
- 如果 repeated same-manifest runs 方差超过阈值且 manifest diff 无可解释因素，则 likely_flaky_evaluation。
- 如果外部 factor replay 都不能恢复，且 code semantic bug flag / code diff 指向逻辑变化，则 likely_true_regression。
- 如果 evidence 不足、字段缺失、多个 replay 冲突，必须输出 unknown，不允许高置信错误归因。

## 8. Baselines 和 Ablations

每个正式 case 必须运行或计算：

```text
single_run_judgment
fixed_seed_evaluation
rerun_k
naive_statistical_gate
original_benchmark_script
manifest_diff_heuristic
evaltriage_no_episode_evidence
evaltriage_no_replay
evaltriage_full
```

公平性约束：

- 所有方法使用同一 baseline/current/replay run pool。
- 不产生 factor ranking 的 baseline 在 RQ3 标为 `N/A`。
- 阈值必须写入 `configs/thresholds/*.yaml`，不能在 test result 上临时调参。

## 9. Metrics 和论文表格

最终聚合输出：

```text
/data/project/zjx/runs/evaltriage/metrics/{timestamp}/cases.csv
/data/project/zjx/runs/evaltriage/metrics/{timestamp}/runs.csv
/data/project/zjx/runs/evaltriage/metrics/{timestamp}/rq2_status_metrics.csv
/data/project/zjx/runs/evaltriage/metrics/{timestamp}/rq3_factor_metrics.csv
/data/project/zjx/runs/evaltriage/metrics/{timestamp}/rq4_cost_metrics.csv
/data/project/zjx/runs/evaltriage/metrics/{timestamp}/failures.csv
```

RQ2 指标：

```text
status precision / recall / F1
false alarm rate
missed regression rate
unknown rate
confusion matrix
```

RQ3 指标：

```text
Top-1 factor accuracy
Top-3 factor accuracy
MRR
unsupported / unknown factor rate
unknown / abstention correctness
per-factor accuracy
```

RQ3 计算口径：

- `unknown_engineering_factor` / `unknown_or_not_specified` cases 不进入普通 factor Top-1、Top-3、MRR 分母。
- unknown cases 单独评估 abstention correctness：证据不足时是否避免高置信错误 factor，并是否报告缺失字段、冲突 replay 或建议补采证据。
- 如果 unknown case 被系统高置信归因到具体 factor，记为 over-attribution error。

RQ4 指标：

```text
rerun count
episode count
GPU minutes
wall-clock minutes
diagnosis latency
pipeline overhead
affected-task replay vs full replay cost ratio
```

任何 metric 行必须包含：

```text
case_id
config path
run path
split: smoke / validation / full
selected_by_validation: true/false
```

## 10. RQ1 输入对接

用户已完成 GitHub evidence mining，并已在本仓库整理为冻结输入。最终系统读取以下文件：

```text
/home/ubuntu/zjx/EvalTriage/RQ1/rq1_evidence.jsonl
/home/ubuntu/zjx/EvalTriage/RQ1/tables/rq1_evidence_index.csv
/home/ubuntu/zjx/EvalTriage/RQ1/tables/rq1_taxonomy_counts.csv
/home/ubuntu/zjx/EvalTriage/RQ1/tables/rq1_case_mapping.csv
/home/ubuntu/zjx/EvalTriage/RQ1/EvalTriage_RQ1_tables.md
/home/ubuntu/zjx/EvalTriage/RQ1/figures/rq1_evidence_overview.pdf
```

要求：

- 每个 core planned controlled fault case 至少链接 1 个或多个 RQ1 evidence refs。
- 论文中用于声称 taxonomy coverage 的 case 必须链接 RQ1 category。
- 如果某个 case 没有 RQ1 evidence，只能作为 synthetic stress case 标记，不能伪装成 evidence-backed case。
- `unknown_or_not_specified` 不作为普通 engineering factor。它支撑 unknown / abstention handling 的必要性：真实 issue 中有 `153 / 473 = 32.35%` 缺少足够归因证据，EvalTriage 必须能在类似条件下拒绝过度归因。

## 11. ICSE Artifact

最终 artifact 不是事后手工整理，而是由 `evaltriage-artifact` 从 run outputs 自动生成。

Artifact 三层：

```text
smoke:
  小 task subset，小 episode 数，用于 evaluator 快速检查代码和格式。

precomputed:
  完整实验的 manifest、episodes、summary、diagnosis、metrics CSV。
  evaluator 可以复算表格，不需要重跑 GPU benchmark。

full:
  完整运行命令、环境说明、资源路径和硬件说明。
```

Artifact 验收：

- `reproduce_tables.sh` 能从 `precomputed_metrics` 生成论文表格 CSV。
- `scripts/run_smoke.sh` 能在 GPU0 上跑出 smoke manifest、episodes、summary、diagnosis。
- `environment.md` 记录 conda env、CUDA、MuJoCo、LeRobot commit、resource inventory。
- 不要求 reviewer 跑完整 GPU benchmark。

## 12. 实现顺序

执行顺序不代表先做临时版本；每一步的交付都必须遵守最终 schema 和目录。

1. 建立 Python package、CLI 和 config loader。
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

## 13. 验收门槛

代码完成不等于实验系统完成。最终可用版本必须通过：

- `evaltriage-run` 对 LeRobot + LIBERO 和 ManiSkill 均能生成完整 run outputs。
- `evaltriage-case` 能自动完成 baseline/current/replay/diagnosis/baseline comparisons。
- 至少覆盖所有 required factors 和所有 case families。
- 所有正式 case 都有 ground truth、manifest diff、replay outcome、diagnosis、cost。
- `evaltriage-aggregate` 能生成 RQ2-RQ4 所有 CSV。
- `evaltriage-artifact` 能生成 smoke/precomputed/full artifact。
- 没有真实 HF token、绝对个人临时路径或未记录依赖进入 artifact。
- `EvalTriage_resource_inventory.md` 与实际资源状态一致。

## 14. 废弃内容

`EvalTriage_experiment_update.md` 已删除。原因：

- 它记录的是 2026-06-26 的旧状态。
- 它包含 `wrapper skeleton`、未验证 smoke、未下载 dataset 等过时表述。
- 它容易把实现方向带回“最小可跑版本”，不符合当前要求的最终可用实验系统路线。

后续状态更新应直接追加到本文件或另建新的日期化实验日志，但不得覆盖本文档中的最终交付定义。
