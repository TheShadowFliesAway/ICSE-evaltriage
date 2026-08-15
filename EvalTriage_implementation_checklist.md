# EvalTriage Implementation Checklist

更新时间：2026-06-28

本文档用于粗粒度跟踪 EvalTriage 实现进度。权威实现标准仍以 `EvalTriage_implementation_plan.md` 为准；本清单只回答两个问题：当前已经做到哪里，下一步应该补什么。

原则保持不变：不做 toy 闭环，不生成 fake benchmark 结果；正式 run/case 输出必须来自真实 runner、真实 injection/replay，或真实 precomputed outputs。

## 当前状态总览

| 模块 | 状态 | 说明 |
|---|---|---|
| 项目骨架与 CLI | 已完成 | package 结构、`pyproject.toml`、Typer CLI、poe 基础任务已建立。 |
| Schema / Config / Path 契约层 | 已完成 | Pydantic v2 严格 schema、case/run/threshold config、输出根目录限制、RQ1 evidence refs 校验已具备。 |
| 标准 Run 产物 | 已完成 | 每个正式 run 的 `manifest.json`、`episodes.jsonl`、`summary.json`、`logs.txt` 四件套已打通。 |
| 真实 Runner 接入 | 部分完成 | LeRobot/LIBERO 和 ManiSkill smoke 已能生成真实 run outputs；ManiSkill `random` policy 可用但不适合 validation diagnosis，`motionplanning` 当前不稳定。 |
| Runtime / Manifest / Diff | 基本完成 | runtime capture、checksum、manifest diff 已有基础实现；后续随 validation/full case 补字段完整性。 |
| Fault Injection Registry | 部分完成 | operator registry 已覆盖计划列表；真实接入 runner overlay 的目前包括 ManiSkill 的 `action.scale_multiplier`、`reset.disable_fixed_init_state`，以及 LeRobot/LIBERO 的 `eval_protocol.change_episode_length`、`action.change_control_mode`、`observation.image_flip`、`checkpoint.config_feature_mismatch`、`reset.disable_fixed_init_state`。 |
| Case-Level Pipeline | 初步完成 | `evaltriage-case` 能复用已有 run，生成 case outputs，并做 schema 校验。 |
| Deviation Detection | 初步完成 | 支持 `success_rate` 优先、`mean_reward` fallback；无 deviation 时 diagnosis 会输出 unknown，避免只凭 manifest diff 过度归因。 |
| Replay Planner / Executor | 部分完成 | replay plan 已能根据 manifest diff 生成；还需要进一步把 replay plan 自动 materialize 成真实 replay run。 |
| Diagnosis / Attribution | 初步完成 | 已有 no-deviation guard、基础 replay recovery 和 conflicting replay abstention；还需要增强缺字段、缺 replay、多因素混杂、no-replay/no-episode ablation。 |
| Baselines / Ablations | 部分完成 | single-run、rerun-k、naive statistical、manifest diff 有基础实现；original logs、no-episode、no-replay、EvalTriage full 还要补齐。 |
| Metrics Aggregation | 骨架完成 | CSV 聚合入口已有；RQ2/RQ3/RQ4 论文级统计口径还需要增强。 |
| Artifact Builder | 骨架完成 | artifact 生成入口已有；smoke/precomputed/full 三层材料还没有成熟。 |
| Validation / Full 实验矩阵 | 已开始 | ManiSkill random validation probes 显示 random policy 无稳定 deviation；LeRobot/LIBERO + `pi0_libero_finetuned_v044` 已完成固定 seed 下 3 个成功 validation factors，并找到一个 eval-protocol soft-drop calibration case。observation 和 reset/init-states 已有真实 backend negative calibration。还没有论文结果级 full matrix 数据。 |

## 已经具备的能力

- `evaltriage-run` 能生成标准 run-level 四件套。
- `evaltriage-case` 能从已有真实 run 产物生成 case-level outputs。
- existing-run 模式会校验 `manifest.json`、`episodes.jsonl`、`summary.json`、`logs.txt`。
- case config 支持 `baseline_run_ids`、`current_run_ids`、`replay_run_ids` 复用已有 run。
- case config 禁止同一 split 同时混用 run request 和 existing run id。
- case config 的 run-request 模式会校验 split role、platform 和 case_id，避免 baseline/current/replay 配错位。
- unconnected injection operator 会明确失败，不写假产物。
- 当前 smoke case 只作为工程验收，不作为论文实验结果。

## 当前真实 smoke 产物

已存在的真实 run/case 产物位于：

```text
/data/project/zjx/runs/evaltriage/runs/
/data/project/zjx/runs/evaltriage/cases/
```

当前 smoke cases：

```text
smoke_maniskill_action_scale
smoke_maniskill_reset_seed
```

这两个 case 的意义是验证 pipeline 和 schema，不代表论文结果。由于当前 smoke 没有检测到稳定 deviation，diagnosis 输出 `unknown_engineering_factor` 是符合预期的。

## 下一阶段重点

下一步主线不是 aggregate smoke，也不是直接做论文表格，而是把当前真实 run / injection / replay 能力提升为 validation-ready case foundation。

建议顺序：

1. 继续完善少量 validation case config，当前优先从 LeRobot/LIBERO + `pi0_libero_finetuned_v044` 开始。
2. 执行 LeRobot/LIBERO validation probe，确认 baseline/current/replay 能产生稳定、可检测的真实 deviation。
3. 明确使用 `success_rate` 或预注册的 `mean_reward` threshold，避免事后调参。
4. 把 replay recovery 和 diagnosis evidence 对齐，只有 replay 恢复 baseline behavior 才给 high confidence。
5. 再扩展更多真实 operator，例如 LeRobot/LIBERO 的 action、observation 或 checkpoint 类 operator；ManiSkill operator 需要等稳定 policy/scripted backend 后再扩。
6. validation cases 稳定后，再补 baselines/ablations、metrics aggregation 和 artifact packaging。

## 后续大块任务

| 阶段 | 目标 | 结果 |
|---|---|---|
| Validation Case Foundation | 少量真实 case 能稳定产生 deviation，并能通过 replay/diagnosis 给出可信证据链。 | 工程上进入 validation split 准备状态。 |
| Operator Expansion | 逐步接入更多真实 injection operators。 | 覆盖 RQ3 factor matrix 的核心因素。 |
| Diagnosis Hardening | 补 replay conflict、缺字段、缺 replay、多因素混杂、unknown abstention 规则。 | 降低过度归因风险。 |
| Baselines / Ablations Completion | 补齐 original logs、no-episode、no-replay、EvalTriage full 等对照。 | 支撑 RQ2/RQ3 消融实验。 |
| Metrics Maturity | 完整输出 RQ2/RQ3/RQ4 CSV，并严格处理 unknown 分母口径。 | 可以从 validation/full outputs 生成论文表格。 |
| Artifact Maturity | 自动生成 smoke/precomputed/full 三层 artifact。 | 支撑 ICSE artifact 复现。 |
| Full Matrix Execution | 运行 validation/full 实验矩阵。 | 产生论文结果级数据。 |

## 已准备的 Validation Configs

当前已经准备并执行过的 ManiSkill random validation probes：

```text
configs/thresholds/validation_maniskill_random.yaml
configs/cases/validation_maniskill_action_scale_pickcube.yaml
configs/cases/validation_maniskill_reset_seed_pickcube.yaml
```

执行结论：

| case | baseline success / reward | current success / reward | deviation | diagnosis |
|---|---|---|---|---|
| `validation_maniskill_action_scale_pickcube` | `0.0 / 2.9749` | `0.0 / 3.1885` | `detected=false`, `metric=mean_reward`, `delta=-0.2136` | `unknown_engineering_factor` |
| `validation_maniskill_reset_seed_pickcube` | `0.0 / 2.5295` | `0.0 / 2.5645` | `detected=false`, `metric=mean_reward`, `delta=-0.0349` | `unknown_engineering_factor` |

结论：ManiSkill `random` policy 的 baseline 行为不可用，success-rate 恒为 0，mean_reward 也没有稳定下降；这些 probes 只说明 pipeline 正确 abstain，不能进入论文结果。下一步转向 LeRobot/LIBERO + `pi0_libero_finetuned_v044`，优先接入能通过 `lerobot-eval` 参数真实生效的 operator。

已执行成功的 LeRobot/LIBERO validation foundation：

```text
configs/thresholds/validation_lerobot_libero.yaml
configs/cases/validation_lerobot_eval_protocol_episode_length_goal_task0.yaml
configs/cases/validation_lerobot_eval_protocol_episode_length_goal_task1.yaml
configs/cases/validation_lerobot_action_control_mode_goal_task0.yaml
configs/cases/validation_lerobot_action_control_mode_goal_task1.yaml
```

该 probe 使用现有 policy：

```text
/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044
```

真实 operators：

```text
eval_protocol.change_episode_length
action.change_control_mode
```

实现方式：

- `eval_protocol.change_episode_length`：current run 通过 `lerobot-eval --env.episode_length=10` 真实缩短 LIBERO episode length；baseline/replay 不设置该参数，恢复默认 evaluation protocol。
- `action.change_control_mode`：current run 通过 `lerobot-eval --env.control_mode=absolute` 真实改变 LIBERO action semantics；baseline/replay 使用默认 `relative`。

执行产物：

```text
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_eval_protocol_episode_length_goal_task0
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_eval_protocol_episode_length_goal_task1
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_action_control_mode_goal_task0
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_action_control_mode_goal_task1
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_task0_ep1_baseline_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_task0_ep1_current_episode_length_10_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_task0_ep1_current_control_mode_absolute_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_task0_ep1_replay_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_task1_ep1_baseline_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_task1_ep1_current_episode_length_10_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_task1_ep1_current_control_mode_absolute_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_task1_ep1_replay_seed1000
```

执行结果：

| case | task | expected factor | baseline SR | current SR | replay SR | diagnosis |
|---|---:|---|---:|---:|---:|---|
| `validation_lerobot_eval_protocol_episode_length_goal_task0` | `0` | `evaluation_protocol_metric` | `1.0` | `0.0` | `1.0` | correct, confidence `0.8` |
| `validation_lerobot_eval_protocol_episode_length_goal_task1` | `1` | `evaluation_protocol_metric` | `1.0` | `0.0` | `1.0` | correct, confidence `0.8` |
| `validation_lerobot_action_control_mode_goal_task0` | `0` | `action_controller_interface` | `1.0` | `0.0` | `1.0` | correct, confidence `0.8` |
| `validation_lerobot_action_control_mode_goal_task1` | `1` | `action_controller_interface` | `1.0` | `0.0` | `1.0` | correct, confidence `0.8` |

Diagnosis:

```text
status = likely_setup_sensitive_deviation
top_factor = expected factor for each case
confidence = 0.8
rule = replay_recovered_baseline_behavior
```

结论：这条 LeRobot/LIBERO 路线已经形成固定 seed 下的真实 validation foundation。按照当前策略，后续不优先扩 seed，而是继续扩 factor 和 task；下一批建议接入 observation 或 checkpoint 类真实 operator。

### LeRobot/LIBERO soft-drop calibration

为回答 hard fault 为什么经常直接降到 `0.0`，额外执行了一个真实 calibration sweep。该 sweep 只用于工程校准，不作为论文结果。

关键原因：

- 单 task、单 episode 的 success rate 分母为 1，只能是 `1.0` 或 `0.0`。
- `episode_length=10` 和 `control_mode=absolute` 是强 fault，适合验证诊断链路，但不适合展示二三成/半数下降。
- 若要看到部分下降，需要扩大 task/episode 分母，并选择较软的 fault 参数。

已新增 configs：

```text
configs/cases/calibration_lerobot_eval_protocol_episode_length_goal_tasks012_len250.yaml
configs/cases/calibration_lerobot_eval_protocol_episode_length_goal_tasks012_len200.yaml
configs/cases/calibration_lerobot_eval_protocol_episode_length_goal_tasks01_len100.yaml
```

执行命令示例：

```text
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/calibration_lerobot_eval_protocol_episode_length_goal_tasks01_len100.yaml --replay-budget 1
```

校准结果：

| probe | task set | baseline SR | current SR | replay SR | conclusion |
|---|---|---:|---:|---:|---|
| `len250` | `[0,1,2]` | `0.6667` | `0.6667` | `0.6667` | 无 deviation；task2 baseline 本身失败，不适合作为 clean validation case。 |
| `len200` | `[0,1,2]` | `0.6667` | `0.6667` | `0.6667` | 无 deviation；同上。 |
| `len150` | `[0,1]` | `1.0` | `1.0` | 未生成 case | fault 太软。 |
| `len100` | `[0,1]` | `1.0` | `0.5` | `1.0` | 找到真实部分下降；task0 失败、task1 成功；diagnosis 正确归因 `evaluation_protocol_metric`，confidence `0.8`。 |
| `len75` | `[0,1]` | `1.0` | `0.0` | 未生成 case | fault 偏硬，属于全灭型下降。 |

`len100` 标准 case 产物：

```text
/data/project/zjx/runs/evaltriage/cases/calibration_lerobot_eval_protocol_episode_length_goal_tasks01_len100
/data/project/zjx/runs/evaltriage/runs/calibration_lr_goal_tasks01_ep1_baseline_seed1000
/data/project/zjx/runs/evaltriage/runs/calibration_lr_goal_tasks01_ep1_current_episode_length_100_seed1000
/data/project/zjx/runs/evaltriage/runs/calibration_lr_goal_tasks01_ep1_replay_seed1000
```

`len100` case 层结果：

```text
deviation.metric_name = success_rate
deviation.baseline_value = 1.0
deviation.current_value = 0.5
deviation.delta = 0.5
deviation.detected = true
diagnosis.status = likely_setup_sensitive_deviation
diagnosis.top_factor = evaluation_protocol_metric
diagnosis.status_confidence = 0.8
diagnosis.rule = replay_recovered_baseline_behavior
```

实现侧顺手修复：

- `lerobot-eval --env.task_ids` 现在使用无空格格式，例如 `[0,1]`，避免 multi-task CLI 解析风险。
- 新 run 的 `episodes.jsonl` 中 `video_path` 会从 staging 路径 finalize 到正式 run 路径；不回写历史产物。
- `poe check`：`17 passed`。

### LeRobot/LIBERO observation operator calibration

继续按“扩 factor 和 task，不扩 seed”的策略，接入并执行了真实 observation preprocessing operator。该批结果只用于 validation probe / negative calibration，不作为论文结果。

已新增并执行的 configs：

```text
configs/cases/validation_lerobot_observation_image_flip_goal_task0.yaml
configs/cases/validation_lerobot_observation_image_flip_goal_task1.yaml
```

实现方式：

- `observation.image_flip` 通过 `evaltriage.runners.lerobot_overlay_worker` 调用真实 `lerobot-eval`。
- overlay 只 monkey-patch LeRobot 的 `LiberoProcessorStep._process_observation`，对 policy 输入图像做 `torch.flip`；rollout、episode、video、`eval_info.json` 仍由真实 LeRobot/LIBERO runner 生成。
- current run 使用 `libero_image_flip_axis=both`；baseline/replay 复用已存在的真实 task0/task1 run。

执行产物：

```text
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_observation_image_flip_goal_task0
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_observation_image_flip_goal_task1
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_task0_ep1_current_image_flip_both_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_task1_ep1_current_image_flip_both_seed1000
```

执行结果：

| case | task | operator | baseline SR / reward | current SR / reward | replay SR / reward | deviation | diagnosis |
|---|---:|---|---:|---:|---:|---|---|
| `validation_lerobot_observation_image_flip_goal_task0` | `0` | `observation.image_flip(axis=both)` | `1.0 / 1.0` | `1.0 / 1.0` | `1.0 / 1.0` | `detected=false` | `unknown_engineering_factor` |
| `validation_lerobot_observation_image_flip_goal_task1` | `1` | `observation.image_flip(axis=both)` | `1.0 / 1.0` | `1.0 / 1.0` | `1.0 / 1.0` | `detected=false` | `unknown_engineering_factor` |

结论：

- `observation.image_flip` 是真实接入的 operator，但在 `libero_goal` task0/task1、`pi0_libero_finetuned_v044`、`seed=1000`、1 episode 设置下没有造成可检测下降。
- 这两个 case 不计为成功的 observation validation factor。
- 诊断模块正确触发 `no_deviation_detected`，没有仅凭 manifest diff 强行归因。
- 当前 observation 方向已有 `camera_swap`、`drop_image_key`、`image_flip` 三类 negative calibration；后续如果继续 observation，应优先换更敏感 task 或更强但仍真实的 preprocessing operator，而不是降低 threshold。

验证命令：

```text
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_image_flip_goal_task0.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_image_flip_goal_task1.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_image_flip_goal_task0.yaml --replay-budget 1
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_image_flip_goal_task1.yaml --replay-budget 1
conda run -n evaltriage-lr poe check
```

验证结果：

```text
poe check: 19 passed
```

### LeRobot/LIBERO task/factor 扩充

按“扩 factor 和 task，不扩 seed”的策略，继续在 `pi0_libero_finetuned_v044`、`seed=1000` 下筛选 `libero_goal` 可用 task，并把已验证有效的两个 factor 扩到多任务 case。

screening run：

```text
/data/project/zjx/runs/evaltriage/runs/screen_lr_goal_tasks3456789_ep1_baseline_seed1000
```

screening 结果：

| task | baseline success | reward | 结论 |
|---:|---|---:|---|
| `3` | false | `0.0` | 不适合作为 clean validation task。 |
| `4` | true | `1.0` | 可用于扩充。 |
| `5` | true | `1.0` | 可用于扩充。 |
| `6` | false | `0.0` | 不适合作为 clean validation task。 |
| `7` | true | `1.0` | 可用于扩充。 |
| `8` | false | `0.0` | 不适合作为 clean validation task。 |
| `9` | true in screening, but false in repeated validation baseline | unstable | 不进入 clean subset。 |

先尝试了 `[4,5,7,9]`：

```text
configs/cases/validation_lerobot_eval_protocol_episode_length_goal_tasks4579.yaml
configs/cases/validation_lerobot_action_control_mode_goal_tasks4579.yaml
```

结果：

| case | tasks | baseline SR | current SR | replay SR | diagnosis | caveat |
|---|---|---:|---:|---:|---|---|
| `validation_lerobot_eval_protocol_episode_length_goal_tasks4579` | `[4,5,7,9]` | `0.75` | `0.0` | `0.75` | correct, `evaluation_protocol_metric`, confidence `0.8` | task9 在 baseline/replay 中失败，不是 clean case。 |
| `validation_lerobot_action_control_mode_goal_tasks4579` | `[4,5,7,9]` | `0.75` | `0.25` | `0.75` | correct, `action_controller_interface`, confidence `0.8` | task9 在 baseline/replay 中失败，不是 clean case。 |

随后改用 clean subset `[4,5,7]`：

```text
configs/cases/validation_lerobot_eval_protocol_episode_length_goal_tasks457.yaml
configs/cases/validation_lerobot_action_control_mode_goal_tasks457.yaml
```

正式 validation probe 结果：

| case | tasks | operator | baseline SR / reward | current SR / reward | replay SR / reward | diagnosis |
|---|---|---|---:|---:|---:|---|
| `validation_lerobot_eval_protocol_episode_length_goal_tasks457` | `[4,5,7]` | `eval_protocol.change_episode_length(10)` | `1.0 / 1.0` | `0.0 / 0.0` | `1.0 / 1.0` | correct, `evaluation_protocol_metric`, confidence `0.8` |
| `validation_lerobot_action_control_mode_goal_tasks457` | `[4,5,7]` | `action.change_control_mode(absolute)` | `1.0 / 1.0` | `0.3333 / 0.3333` | `1.0 / 1.0` | correct, `action_controller_interface`, confidence `0.8` |

关键结论：

- `tasks457` 是目前更干净的 LeRobot/LIBERO multi-task validation foundation：baseline/replay 都是 `3/3` 成功，current 有真实下降。
- action case 给出了部分下降：`1.0 -> 0.3333`，不是 hard-fault 全灭；这比单 task 1-episode 的 `0/1` 指标更适合展示部分下降现象。
- `tasks4579` 仍保留为有 caveat 的 probe，不建议作为 clean validation 结果，因为 task9 在重复 baseline 中失败。
- 目前已具备固定 seed 下 `2 factors x task subset` 的真实 case foundation；下一步应继续扩 factor 覆盖，优先找 checkpoint/config compatibility 或 evaluation-script harness 的真实可恢复 operator。

新增验证命令：

```text
conda run -n evaltriage-lr evaltriage-run --platform lerobot_libero --run-id screen_lr_goal_tasks3456789_ep1_baseline_seed1000 --role baseline --suite libero_goal --task-ids 3,4,5,6,7,8,9 --seed 1000 --episodes 1 --policy-path /data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044 --obs-type pixels_agent_pos --camera-size 360 --compile-model false --use-async-envs false
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_eval_protocol_episode_length_goal_tasks457.yaml --replay-budget 1
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_action_control_mode_goal_tasks457.yaml --replay-budget 1
conda run -n evaltriage-lr poe check
```

验证结果：

```text
poe check: 19 passed
```

### LeRobot/LIBERO checkpoint/config factor 扩充

继续扩 factor，不扩 seed。本轮新增真实 `checkpoint_config_compatibility` backend：`checkpoint.config_feature_mismatch`。

实现方式：

- current run 在 staging `raw/checkpoint_overlay/` 下创建临时 checkpoint overlay。
- overlay 不复制 6.6GB `model.safetensors`，而是 symlink 原始权重；JSON 和小型 processor state 文件复制到 overlay。
- fault 只修改 overlay 中的 `policy_postprocessor.json`：把 action postprocessor 的 `norm_map.ACTION` 从 `MEAN_STD` 改为 `IDENTITY`。
- 真实 `lerobot-eval` 使用 `--policy.path=<overlay>` 加载该 checkpoint；baseline/replay 仍使用原始 checkpoint。
- 原始 checkpoint 不被修改，overlay 随正式 run artifact 一起保存。

代码侧新增：

```text
evaltriage/runners/lerobot_libero.py
evaltriage/runners/executor.py
evaltriage/runners/base.py
evaltriage/injection/registry.py
evaltriage/config.py
evaltriage/cli.py
evaltriage/manifest/collect.py
evaltriage/schemas.py
```

新增 configs：

```text
configs/cases/validation_lerobot_checkpoint_postprocessor_norm_goal_tasks457.yaml
configs/cases/validation_lerobot_checkpoint_postprocessor_norm_goal_tasks457_v2.yaml
```

`v1` 结果行为正确，但发现 manifest checksum 记录不完整：

| case | tasks | baseline SR | current SR | replay SR | diagnosis | caveat |
|---|---|---:|---:|---:|---|---|
| `validation_lerobot_checkpoint_postprocessor_norm_goal_tasks457` | `[4,5,7]` | `1.0` | `0.0` | `1.0` | correct, `checkpoint_config_compatibility`, confidence `0.8` | overlay path 在 checksum 计算前被 finalize，导致 current policy checksums 为 `None`。 |

已修复 manifest 记录后重新跑 `v2`：

| case | tasks | operator | baseline SR / reward | current SR / reward | replay SR / reward | diagnosis |
|---|---|---|---:|---:|---:|---|
| `validation_lerobot_checkpoint_postprocessor_norm_goal_tasks457_v2` | `[4,5,7]` | `checkpoint.config_feature_mismatch(postprocessor_action_norm_identity)` | `1.0 / 1.0` | `0.0 / 0.0` | `1.0 / 1.0` | correct, `checkpoint_config_compatibility`, confidence `0.8` |

`v2` manifest diff 关键证据：

```text
policy.path: original checkpoint -> run-local raw/checkpoint_overlay
policy.postprocessor_checksum: 3b51f092... -> 132218ce...
policy.checkpoint_checksum: unchanged
policy.config_checksum: unchanged
policy.preprocessor_checksum: unchanged
injection.operator: checkpoint.config_feature_mismatch
```

结论：

- 已新增第 3 个成功 validation factor：`checkpoint_config_compatibility`。
- 这是一个真实 checkpoint/config overlay，不是 manifest-only tag。
- 当前 clean `tasks457` foundation 已覆盖：
  - `evaluation_protocol_metric`
  - `action_controller_interface`
  - `checkpoint_config_compatibility`
- 下一步如果继续扩 factor，优先考虑 `evaluation_script_harness` 或 `dependency_runtime_environment`；如果做 crash 类 case，需要先补 crash-run schema/writer，不能直接让 runner 失败后冒充正式 case。

新增验证命令：

```text
conda run -n evaltriage-lr evaltriage-run --platform lerobot_libero --run-id validation_lr_goal_tasks457_ep1_current_checkpoint_postnorm_identity_seed1000_validate --role current --suite libero_goal --task-ids 4,5,7 --seed 1000 --episodes 1 --policy-path /data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044 --obs-type pixels_agent_pos --camera-size 360 --compile-model false --use-async-envs false --injection-operator checkpoint.config_feature_mismatch --checkpoint-overlay-mode postprocessor_action_norm_identity --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_checkpoint_postprocessor_norm_goal_tasks457_v2.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_checkpoint_postprocessor_norm_goal_tasks457_v2.yaml --replay-budget 1
conda run -n evaltriage-lr poe check
```

验证结果：

```text
poe check: 19 passed
```

### Diagnosis hardening：conflicting replay abstention

为避免 diagnosis 在有歧义证据时过度归因，本轮补强了 replay conflict 规则：当同一个 case 中既存在恢复 baseline behavior 的 replay，也存在未恢复的 replay，EvalTriage 不再因为一个恢复 replay 就输出 high-confidence factor，而是输出 `unknown_engineering_factor` 并说明 replay 证据冲突。

代码侧新增：

```text
evaltriage/diagnosis/attribution.py
evaltriage/config.py
tests/test_contracts.py
```

新增真实 replay run：

```text
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep1_replay_control_mode_absolute_seed1000
```

该 replay 是真实 `role=replay` run，但保留了 current 的错误 `control_mode=absolute`，因此没有恢复 baseline：

| run | role | tasks | success rate | 说明 |
|---|---|---|---:|---|
| `validation_lr_goal_tasks457_ep1_baseline_seed1000` | baseline | `[4,5,7]` | `1.0` | clean baseline |
| `validation_lr_goal_tasks457_ep1_current_control_mode_absolute_seed1000` | current | `[4,5,7]` | `0.3333` | action interface deviation |
| `validation_lr_goal_tasks457_ep1_replay_seed1000` | replay | `[4,5,7]` | `1.0` | 恢复 baseline behavior |
| `validation_lr_goal_tasks457_ep1_replay_control_mode_absolute_seed1000` | replay | `[4,5,7]` | `0.3333` | 未恢复 baseline behavior |

新增 conflict / unknown case：

```text
configs/cases/validation_lerobot_unknown_replay_conflict_action_goal_tasks457.yaml
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_unknown_replay_conflict_action_goal_tasks457
```

case 结果：

```text
deviation.metric_name = success_rate
deviation.baseline_value = 1.0
deviation.current_value = 0.3333333333333333
deviation.delta = 0.6666666666666667
deviation.detected = true
diagnosis.status = unknown_engineering_factor
diagnosis.status_confidence = 0.3
diagnosis.unknown_reason = conflicting replay outcomes: some replay runs recovered baseline behavior while others did not
decision_rules_fired =
  - replay_recovered:validation_lr_goal_tasks457_ep1_replay_seed1000
  - replay_not_recovered:validation_lr_goal_tasks457_ep1_replay_control_mode_absolute_seed1000
```

结论：

- 这是一个真实产物层面的 ambiguity / abstention case，不是 fake benchmark output。
- 它不进入普通 RQ3 Top-1 / Top-3 / MRR factor accuracy 分母。
- 它用于 unknown / abstention correctness：当 replay evidence 冲突时，EvalTriage 应拒绝高置信 factor attribution。
- 这类 case 能支撑论文叙事中“EvalTriage 不只是看到 manifest diff 就猜 factor”的部分。

新增验证命令：

```text
conda run -n evaltriage-lr evaltriage-run --platform lerobot_libero --run-id validation_lr_goal_tasks457_ep1_replay_control_mode_absolute_seed1000 --role replay --suite libero_goal --task-ids 4,5,7 --seed 1000 --episodes 1 --policy-path /data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044 --obs-type pixels_agent_pos --camera-size 360 --libero-control-mode absolute --compile-model false --use-async-envs false
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_unknown_replay_conflict_action_goal_tasks457.yaml --replay-budget 2 --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_unknown_replay_conflict_action_goal_tasks457.yaml --replay-budget 2
conda run -n evaltriage-lr poe check
```

验证结果：

```text
poe check: 21 passed
```

### LeRobot/LIBERO reset/init-states operator calibration

继续按“扩 factor 和 task，不扩 seed”的策略，接入真实 `reset_or_initial_state` backend：`reset.disable_fixed_init_state`。

实现方式：

- LeRobot/LIBERO current run 通过真实 `lerobot-eval --env.init_states=false` 禁用 LIBERO task init states。
- baseline/replay 使用默认 `--env.init_states=true`。
- `RunRequest` 和 `manifest.json` 新增 `libero_init_states` / `reset.init_states`，manifest diff 可直接看到 `reset.init_states: true -> false`。
- operator 参数按平台校验：ManiSkill 使用 `seed_offset`，LeRobot/LIBERO 使用 `init_states: false`，避免无意义参数混入正式 run。

新增代码侧能力：

```text
evaltriage/schemas.py
evaltriage/runners/lerobot_libero.py
evaltriage/runners/executor.py
evaltriage/injection/registry.py
evaltriage/config.py
evaltriage/cli.py
evaltriage/manifest/collect.py
evaltriage/manifest/diff.py
tests/test_contracts.py
```

新增 config：

```text
configs/cases/validation_lerobot_reset_disable_init_states_goal_tasks457.yaml
```

执行产物：

```text
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_reset_disable_init_states_goal_tasks457
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep1_baseline_seed1000_reset_v2
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep1_current_init_states_false_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep1_replay_seed1000_reset_v2
```

执行结果：

| case | tasks | operator | baseline SR / reward | current SR / reward | replay SR / reward | deviation | diagnosis |
|---|---|---|---:|---:|---:|---|---|
| `validation_lerobot_reset_disable_init_states_goal_tasks457` | `[4,5,7]` | `reset.disable_fixed_init_state(init_states=false)` | `1.0 / 1.0` | `1.0 / 1.0` | `1.0 / 1.0` | `detected=false`, `metric=mean_reward`, `delta=0.0` | `unknown_engineering_factor` |

manifest diff 关键证据：

```text
reset.init_states: true -> false
injection.operator: null -> reset.disable_fixed_init_state
injection.factor: null -> reset_or_initial_state
```

结论：

- `reset.disable_fixed_init_state` 已经是真实接入的 LeRobot/LIBERO operator，不是 manifest-only tag。
- 在当前 clean subset `tasks457`、`pi0_libero_finetuned_v044`、`seed=1000`、1 episode 设置下，它没有造成可检测下降。
- diagnosis 正确触发 `no_deviation_detected`，没有因为 manifest diff 中存在 `reset_or_initial_state` 就强行归因。
- 这条结果记为 reset/init-states negative calibration，不计为第 4 个成功 validation factor。
- 如果后续继续 reset factor，应换更依赖初始状态的 task/suite 或增加预注册 task set，而不是降低 threshold。

新增验证命令：

```text
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_reset_disable_init_states_goal_tasks457.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_reset_disable_init_states_goal_tasks457.yaml --replay-budget 1
conda run -n evaltriage-lr poe check
```

验证结果：

```text
poe check: 23 passed
```

### LeRobot/LIBERO evaluation-script harness batch-size calibration

继续尝试扩第 4 个 factor：`evaluation_script_harness`。本轮接入真实 `evaluation_script.modify_harness_flag` backend，当前只支持 LeRobot/LIBERO 的 `eval.batch_size`。

实现方式：

- `RunRequest` 新增 `eval_batch_size`，真实传给 `lerobot-eval --eval.batch_size=<n>`。
- `manifest.json` 记录 `evaluation.batch_size`。
- `manifest_diff` 将 `evaluation.batch_size` 映射到 `evaluation_script_harness`，避免误归为 `evaluation_protocol_metric`。
- operator 参数为 `flag: eval.batch_size`、`value: <integer>`，config/executor/CLI 均校验 `run.eval_batch_size == injection.params.value`。
- 该 operator 对齐 RQ1 evidence `github_issue::huggingface/lerobot::2850`，即 LeRobot/LIBERO eval batch size 影响评测初始状态覆盖。

新增代码侧能力：

```text
evaltriage/schemas.py
evaltriage/runners/lerobot_libero.py
evaltriage/runners/executor.py
evaltriage/injection/registry.py
evaltriage/config.py
evaltriage/cli.py
evaltriage/manifest/collect.py
evaltriage/manifest/diff.py
tests/test_contracts.py
```

新增 config：

```text
configs/cases/validation_lerobot_harness_eval_batch_size_goal_tasks457_ep2.yaml
```

执行产物：

```text
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_harness_eval_batch_size_goal_tasks457_ep2
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep2_baseline_batch1_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep2_current_eval_batch2_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep2_replay_batch1_seed1000
```

执行结果：

| case | tasks | episodes/task | operator | baseline SR / reward | current SR / reward | replay SR / reward | deviation | diagnosis |
|---|---|---:|---|---:|---:|---:|---|---|
| `validation_lerobot_harness_eval_batch_size_goal_tasks457_ep2` | `[4,5,7]` | `2` | `evaluation_script.modify_harness_flag(eval.batch_size=2)` | `0.8333 / 0.8333` | `0.8333 / 0.8333` | `0.8333 / 0.8333` | `detected=false`, `metric=mean_reward`, `delta=0.0` | `unknown_engineering_factor` |

episode-level 观察：

```text
baseline batch_size=1: task4 seed1001 failed, total 5/6
current  batch_size=2: task5 seed1003 failed, total 5/6
replay   batch_size=1: task4 seed1001 failed, total 5/6
```

manifest diff 关键证据：

```text
evaluation.batch_size: 1 -> 2
injection.operator: null -> evaluation_script.modify_harness_flag
injection.factor: null -> evaluation_script_harness
```

结论：

- `evaluation_script.modify_harness_flag(eval.batch_size=2)` 已经是真实接入的 LeRobot/LIBERO operator。
- 该 harness flag 确实改变了 episode-level failure 分布，但 aggregate success/reward 没有下降，因此当前 case 不能作为第 4 个成功 validation factor。
- diagnosis 正确触发 `no_deviation_detected`，没有仅凭 `evaluation.batch_size` manifest diff 强行归因。
- 这条结果记为 evaluation-script harness negative/ambiguous calibration。
- 后续如果继续 harness factor，应考虑更大的预注册 task/episode subset 或更强但仍能正常产出 run outputs 的 harness 参数；不能降低 threshold。

新增验证命令：

```text
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_harness_eval_batch_size_goal_tasks457_ep2.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_harness_eval_batch_size_goal_tasks457_ep2.yaml --replay-budget 1
conda run -n evaltriage-lr poe check
```

验证结果：

```text
poe check: 25 passed
```

### Episode-level deviation detection for harness cases

针对 `eval.batch_size` probe aggregate 指标不变的问题，本轮没有新增 v1/v2，也没有改动真实 run 数据，而是在原有 deviation detection 中加入 episode-level paired outcome shift 检测。

优化内容：

- `evaltriage-case` 在检测 deviation 时读取 baseline/current/replay 的标准 `episodes.jsonl`。
- 原有 `success_rate` / `mean_reward` drop 逻辑保留。
- 新增 paired episode 检测：只有当 baseline 和 replay 在同一个 `(task_id, seed)` episode 上 outcome 一致，而 current outcome 不一致时，才记录 `paired_episode_outcome_mismatch_rate`。
- diagnosis 对该 metric 使用 replay recovery 证据：因为 deviation 本身已经要求 replay 恢复 baseline episode behavior。
- 该优化不生成 fake benchmark outputs，只复用已存在的真实 run 四件套。

代码侧新增/修改：

```text
evaltriage/detection/deviation.py
evaltriage/case_runner.py
evaltriage/diagnosis/attribution.py
tests/test_contracts.py
```

新增复算 config：

```text
configs/cases/validation_lerobot_harness_eval_batch_size_goal_tasks457_ep2_paired.yaml
```

复用真实 runs：

```text
validation_lr_goal_tasks457_ep2_baseline_batch1_seed1000
validation_lr_goal_tasks457_ep2_current_eval_batch2_seed1000
validation_lr_goal_tasks457_ep2_replay_batch1_seed1000
```

复算产物：

```text
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_harness_eval_batch_size_goal_tasks457_ep2_paired
```

复算结果：

| case | aggregate SR baseline/current/replay | paired evidence | deviation | diagnosis |
|---|---:|---|---|---|
| `validation_lerobot_harness_eval_batch_size_goal_tasks457_ep2_paired` | `0.8333 / 0.8333 / 0.8333` | baseline/replay agree but current differs on `task=4/seed=1001` and `task=5/seed=1003` | `paired_episode_outcome_mismatch_rate=0.3333`, `detected=true` | correct, `evaluation_script_harness`, confidence `0.8` |

deviation evidence:

```text
success_rate baseline=0.8333 current=0.8333 delta=0.0 threshold=0.5
paired_episode_outcome_shift stable_pairs=6 shifted_pairs=2 shift_rate=0.3333 shifted=task=4/seed=1001, task=5/seed=1003
baseline/replay agree on paired episode outcomes while current differs; aggregate success_rate may be unchanged
```

diagnosis:

```text
status = likely_setup_sensitive_deviation
top_factor = evaluation_script_harness
confidence = 0.8
rule = replay_recovered_baseline_behavior
```

结论：

- 这不是把 aggregate no-drop case 硬改成成功，而是把系统从只看 aggregate drop 扩展到 episode-level replay-supported deviation。
- `eval.batch_size` case 现在可作为 `evaluation_script_harness` 的 validation candidate，但论文中需要明确它捕获的是 episode-level outcome distribution shift，而不是 aggregate success-rate drop。
- reset/init-states 仍然不是成功 case，因为它没有 episode-level outcome shift。

新增验证命令：

```text
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_harness_eval_batch_size_goal_tasks457_ep2_paired.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_harness_eval_batch_size_goal_tasks457_ep2_paired.yaml --replay-budget 1
conda run -n evaltriage-lr poe check
```

验证结果：

```text
poe check: 26 passed
```

### LeRobot/LIBERO observation drop-camera tasks457 calibration

继续尝试扩 `observation_sensor_preprocessing`。本轮没有改系统，复用现有真实 backend `observation.drop_image_key`，在 clean `libero_goal` tasks `[4,5,7]` 上测试单相机 observation 是否足够造成 deviation。

实现语义说明：

- `observation.drop_image_key` 当前通过真实 LeRobot/LIBERO 参数 `--env.camera_name=<single camera>` 生效。
- baseline/replay 使用双相机：`agentview_image,robot0_eye_in_hand_image`。
- `drop_agentview` case 只保留 `robot0_eye_in_hand_image`，因此实际删除 agentview/image key。
- `drop_wrist` case 只保留 `agentview_image`，因此实际删除 wrist/image2 key。
- 该 backend 会写入真实 `manifest.json` 的 `observation.camera_names`、`observation.image_keys` 和 `observation.preprocessing`，不是只改 case 标签。

新增 config：

```text
configs/cases/validation_lerobot_observation_drop_agentview_goal_tasks457.yaml
configs/cases/validation_lerobot_observation_drop_wrist_goal_tasks457.yaml
```

执行产物：

```text
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_observation_drop_agentview_goal_tasks457
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_observation_drop_wrist_goal_tasks457
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep1_current_drop_agentview_seed1000
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep1_current_drop_wrist_seed1000
```

执行结果：

| case | tasks | operator | baseline SR / reward | current SR / reward | replay SR / reward | deviation | diagnosis |
|---|---|---|---:|---:|---:|---|---|
| `validation_lerobot_observation_drop_agentview_goal_tasks457` | `[4,5,7]` | keep `robot0_eye_in_hand_image` only | `1.0 / 1.0` | `1.0 / 1.0` | `1.0 / 1.0` | `detected=false`, `metric=mean_reward`, `delta=0.0` | `unknown_engineering_factor` |
| `validation_lerobot_observation_drop_wrist_goal_tasks457` | `[4,5,7]` | keep `agentview_image` only | `1.0 / 1.0` | `1.0 / 1.0` | `1.0 / 1.0` | `detected=false`, `metric=mean_reward`, `delta=0.0` | `unknown_engineering_factor` |

episode-level 结果：

```text
drop_agentview current: task4/1000=true, task5/1001=true, task7/1002=true
drop_wrist current:     task4/1000=true, task5/1001=true, task7/1002=true
```

manifest diff 关键证据：

```text
drop_agentview:
  observation.camera_names: [agentview_image, robot0_eye_in_hand_image] -> [robot0_eye_in_hand_image]
  observation.image_keys: [observation.images.image, observation.images.image2] -> [observation.images.image2]

drop_wrist:
  observation.camera_names: [agentview_image, robot0_eye_in_hand_image] -> [agentview_image]
  observation.image_keys: [observation.images.image, observation.images.image2] -> [observation.images.image]
```

结论：

- 两个 observation drop-camera case 都是真实运行并落盘的负校准结果。
- 现有单相机 drop backend 对 `tasks457` 不敏感；不能把它们算作 `observation_sensor_preprocessing` 成功 factor。
- diagnosis 行为正确：虽然 manifest diff 明确指向 observation factor，但没有 aggregate 或 episode-level deviation，因此输出 `unknown_engineering_factor`。
- 后续若继续 observation，应优先接更强但仍真实的 preprocessing operator，例如 image blackout/mask/noise/resize/crop，而不是降低 threshold 或强行归因。

新增验证命令：

```text
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_drop_agentview_goal_tasks457.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_drop_wrist_goal_tasks457.yaml --replay-budget 1 --validate-only
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_drop_agentview_goal_tasks457.yaml --replay-budget 1
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_drop_wrist_goal_tasks457.yaml --replay-budget 1
conda run -n evaltriage-lr poe check
```

验证结果：

```text
poe check: 26 passed
```

### LeRobot/LIBERO observation image-blackout backend and calibration

由于 `camera_swap`、`drop_image_key`、`image_flip` 以及 `drop-camera tasks457` 均未造成 deviation，本轮按原计划接入一个更强但仍真实的 observation preprocessing backend：`observation.image_blackout`。

实现方式：

- 新增 operator：`observation.image_blackout`。
- LeRobot/LIBERO runner 通过 `evaltriage.runners.lerobot_overlay_worker` 调用真实 `lerobot-eval`。
- overlay monkey-patch `LiberoProcessorStep._process_observation`，在 LeRobot processor 输出 policy image tensor 后，将所有 `observation.images.*` tensor 置为固定值。
- 本轮配置使用 `value=0.0`。
- rollout、policy loading、episode execution、videos、`eval_info.json` 仍由真实 LeRobot/LIBERO runner 产生。
- `manifest.json` 记录 `observation.preprocessing=["image_blackout_value=0.0"]`。

新增/修改代码：

```text
evaltriage/schemas.py
evaltriage/injection/registry.py
evaltriage/runners/lerobot_overlay_worker.py
evaltriage/runners/lerobot_libero.py
evaltriage/runners/executor.py
evaltriage/config.py
evaltriage/manifest/collect.py
evaltriage/cli.py
tests/test_contracts.py
```

新增 config：

```text
configs/cases/validation_lerobot_observation_image_blackout_goal_tasks457.yaml
```

执行产物：

```text
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_observation_image_blackout_goal_tasks457
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep1_current_image_blackout0_seed1000
```

执行结果：

| case | tasks | operator | baseline SR / reward | current SR / reward | replay SR / reward | deviation | diagnosis |
|---|---|---|---:|---:|---:|---|---|
| `validation_lerobot_observation_image_blackout_goal_tasks457` | `[4,5,7]` | `observation.image_blackout(value=0.0)` | `1.0 / 1.0` | `1.0 / 1.0` | `1.0 / 1.0` | `detected=false`, `metric=mean_reward`, `delta=0.0` | `unknown_engineering_factor` |

episode-level 结果：

```text
current image_blackout0: task4/1000=true, task5/1001=true, task7/1002=true
```

manifest diff 关键证据：

```text
injection.operator: null -> observation.image_blackout
injection.factor: null -> observation_sensor_preprocessing
observation.preprocessing: [] -> [image_blackout_value=0.0]
```

结论：

- `observation.image_blackout` 已经接入真实 LeRobot/LIBERO overlay backend，并能产出标准 run/case 四件套。
- 在当前 `pi0_libero_finetuned_v044`、`libero_goal` tasks `[4,5,7]`、`seed=1000`、1 episode/task 设置下，即使 image blackout 也未造成 aggregate 或 episode-level deviation。
- 因此该 case 不能作为 `observation_sensor_preprocessing` 成功 factor；diagnosis 正确输出 `unknown_engineering_factor`。
- observation 方向当前累计多类负校准，说明该 policy/task subset 对 observation preprocessing 不敏感，或者 policy 可依赖 state/proprioception 完成这些 tasks。
- 该结果后续应作为“不要在 tasks457 上继续硬救 observation”的 evidence；若继续 observation，需要先确认 policy 输入图像依赖或换更敏感 task/suite，而不是降低 threshold。

新增验证命令：

```text
conda run -n evaltriage-lr poe check
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_image_blackout_goal_tasks457.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-run --platform lerobot_libero --run-id validate_lr_observation_blackout --role current --suite libero_goal --task-ids 4,5,7 --seed 1000 --episodes 1 --policy-path /data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044 --obs-type pixels_agent_pos --camera-size 360 --compile-model false --use-async-envs false --injection-operator observation.image_blackout --libero-image-blackout-value 0.0 --validate-only
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_image_blackout_goal_tasks457.yaml --replay-budget 1
conda run -n evaltriage-lr poe check
```

验证结果：

```text
poe check: 28 passed
```

### LeRobot/LIBERO dependency runtime MuJoCo drift calibration

继续尝试扩 `dependency_runtime_environment`。本轮接入真实 backend `runtime.switch_mujoco_env`，让 current run 使用单独 conda env `evaltriage-lr-mujoco37` 运行真实 `lerobot-eval`。baseline/replay 继续使用默认 `evaltriage-lr`。

环境差异：

```text
baseline/replay env: evaltriage-lr
current env:         evaltriage-lr-mujoco37
baseline mujoco:     3.8.1
current mujoco:      3.7.0
torch/cuda/driver:   unchanged
```

实现方式：

- `runtime.switch_mujoco_env` 新增参数 `conda_env`。
- `RunRequest.libero_env` 和 `RunRequest.mujoco_env` 必须同时等于 injection 参数中的 `conda_env`。
- LeRobot/LIBERO runner 真实执行：

```text
conda run -n evaltriage-lr-mujoco37 lerobot-eval ...
```

- LeRobot runner 现在会从实际执行的 target conda env 捕获 runtime manifest，而不是使用父进程 env。
- `manifest_diff` 不再忽略 `runtime_env.*`，因此会把 runtime version drift 映射到 `dependency_runtime_environment`。

新增/修改代码：

```text
evaltriage/injection/registry.py
evaltriage/manifest/diff.py
evaltriage/runners/lerobot_libero.py
evaltriage/runners/executor.py
evaltriage/config.py
evaltriage/cli.py
tests/test_contracts.py
```

新增 config：

```text
configs/cases/validation_lerobot_dependency_mujoco37_goal_tasks457.yaml
```

执行产物：

```text
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_dependency_mujoco37_goal_tasks457
/data/project/zjx/runs/evaltriage/runs/validation_lr_goal_tasks457_ep1_current_mujoco37_seed1000
```

执行结果：

| case | tasks | operator | baseline SR / reward | current SR / reward | replay SR / reward | deviation | diagnosis |
|---|---|---|---:|---:|---:|---|---|
| `validation_lerobot_dependency_mujoco37_goal_tasks457` | `[4,5,7]` | `runtime.switch_mujoco_env(conda_env=evaltriage-lr-mujoco37)` | `1.0 / 1.0` | `1.0 / 1.0` | `1.0 / 1.0` | `detected=false`, `metric=mean_reward`, `delta=0.0` | `unknown_engineering_factor` |

episode-level 结果：

```text
current mujoco37: task4/1000=true, task5/1001=true, task7/1002=true
```

manifest diff 关键证据：

```text
injection.operator: null -> runtime.switch_mujoco_env
injection.factor: null -> dependency_runtime_environment
runtime_env.conda_env: evaltriage-lr -> evaltriage-lr-mujoco37
runtime_env.mujoco: 3.8.1 -> 3.7.0
```

结论：

- `runtime.switch_mujoco_env` 已经是真实接入的 LeRobot/LIBERO backend。
- runtime drift 证据干净，manifest diff 可直接指向 `dependency_runtime_environment`。
- 但在当前 `pi0_libero_finetuned_v044`、`libero_goal` tasks `[4,5,7]`、`seed=1000`、1 episode/task 设置下，MuJoCo `3.8.1 -> 3.7.0` 没有造成 aggregate 或 episode-level deviation。
- 因此该 case 是 dependency/runtime negative calibration，不能算成功 factor。
- 后续若继续 dependency/runtime，应换更可能影响行为的 runtime drift，例如 robosuite/transformers/torch/attention backend，或换更敏感 task/suite；不能只凭 runtime manifest diff 强行归因。

新增验证命令：

```text
conda run -n evaltriage-lr poe check
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_dependency_mujoco37_goal_tasks457.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-run --platform lerobot_libero --run-id validate_lr_dependency_mujoco37 --role current --suite libero_goal --task-ids 4,5,7 --seed 1000 --episodes 1 --policy-path /data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044 --obs-type pixels_agent_pos --camera-size 360 --compile-model false --use-async-envs false --injection-operator runtime.switch_mujoco_env --mujoco-env evaltriage-lr-mujoco37 --validate-only
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_dependency_mujoco37_goal_tasks457.yaml --replay-budget 1
conda run -n evaltriage-lr poe check
```

验证结果：

```text
poe check: 30 passed
```

### Factor exhaustion pass: state observation, reset all-goal, seed drift, action variants

本轮按“尽量穷尽 factor”的策略继续扩展 completed-rollout factor。原则不变：只接受真实 backend、真实 run/case artifacts、预注册 threshold 或 paired episode evidence，不降低阈值，不把 crash-only case 混入 completed-rollout 成功矩阵。

新增/修改 backend：

- `observation.state_blackout`
- `observation.state_noise`
- `observation.state_key_drop`
- `action.drop_postprocessor`
- `action.reorder_dimensions`

新增/修改代码：

```text
evaltriage/schemas.py
evaltriage/injection/registry.py
evaltriage/runners/lerobot_overlay_worker.py
evaltriage/runners/lerobot_libero.py
evaltriage/runners/executor.py
evaltriage/config.py
evaltriage/manifest/collect.py
evaltriage/cli.py
tests/test_contracts.py
```

新增 config：

```text
configs/cases/validation_lerobot_observation_state_blackout_goal_tasks457.yaml
configs/cases/validation_lerobot_observation_state_noise_goal_tasks457.yaml
configs/cases/validation_lerobot_observation_state_key_drop_goal_tasks457.yaml
configs/cases/validation_lerobot_observation_state_blackout_goal_tasks0to9.yaml
configs/cases/validation_lerobot_observation_state_noise_goal_tasks0to9.yaml
configs/cases/validation_lerobot_reset_disable_init_states_goal_tasks0to9.yaml
configs/cases/validation_lerobot_seed_drift_goal_tasks0to9_seed2000.yaml
configs/cases/validation_lerobot_seed_drift_goal_tasks0to9_seed3000.yaml
configs/cases/validation_lerobot_action_drop_postprocessor_goal_tasks457.yaml
configs/cases/validation_lerobot_action_reorder_dimensions_goal_tasks457.yaml
```

执行产物：

```text
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_observation_state_blackout_goal_tasks457
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_observation_state_noise_goal_tasks457
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_reset_disable_init_states_goal_tasks0to9
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_seed_drift_goal_tasks0to9_seed2000
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_seed_drift_goal_tasks0to9_seed3000
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_action_drop_postprocessor_goal_tasks457
/data/project/zjx/runs/evaltriage/cases/validation_lerobot_action_reorder_dimensions_goal_tasks457
/data/project/zjx/runs/evaltriage/failures/preflight_ms_PickCube_motionplanning_seed1000_ep3/logs.txt
```

执行结果：

| case | factor | operator | tasks/seeds | baseline | current | replay | deviation | diagnosis | conclusion |
|---|---|---|---|---:|---:|---:|---|---|---|
| `validation_lerobot_observation_state_blackout_goal_tasks457` | observation | `observation.state_blackout(value=0.0)` | `[4,5,7]`, seed 1000 | `1.0` | `0.0` | `1.0` | detected, success_rate delta `1.0` | correct, observation | success candidate |
| `validation_lerobot_observation_state_noise_goal_tasks457` | observation | `observation.state_noise(std=10.0)` | `[4,5,7]`, seed 1000 | `1.0` | `0.0` | `1.0` | detected, success_rate delta `1.0` | correct, observation | success candidate |
| `validation_lerobot_reset_disable_init_states_goal_tasks0to9` | reset/init | `reset.disable_fixed_init_state(init_states=false)` | `[0-9]`, seed 1000 | `0.8` | `0.9` | `0.8` | detected by paired shift `0.1`, shifted `task=4/seed=1004` | correct, reset | success candidate, episode-level |
| `validation_lerobot_seed_drift_goal_tasks0to9_seed2000` | seed/randomness | clean seed drift | baseline seed 1000, current seed 2000 | `0.8` | `0.7` | `0.8` | not detected, delta `0.1 < 0.5` | unknown | negative/weak signal |
| `validation_lerobot_seed_drift_goal_tasks0to9_seed3000` | seed/randomness | clean seed drift | baseline seed 1000, current seed 3000 | `0.8` | `0.6` | `0.8` | not detected, delta `0.2 < 0.5` | unknown | negative/weak signal |
| `validation_lerobot_action_drop_postprocessor_goal_tasks457` | action | `action.drop_postprocessor` | `[4,5,7]`, seed 1000 | `1.0` | `0.0` | `1.0` | detected, success_rate delta `1.0` | correct, action | success candidate |
| `validation_lerobot_action_reorder_dimensions_goal_tasks457` | action | `action.reorder_dimensions([1,0,2,3,4,5,6])` | `[4,5,7]`, seed 1000 | `1.0` | `0.0` | `1.0` | detected, success_rate delta `1.0` | correct, action | success candidate |

关键解释：

- 之前 image-level observation 扰动全部负校准，是因为当前 policy/task 对图像不敏感；state/proprio 扰动直接影响 `observation.state` 后，observation factor 成功闭环。
- reset/init-states 在 tasks `[4,5,7]` 无信号，但扩到 tasks `[0-9]` 后出现 paired episode shift；aggregate success_rate 甚至变好，不能用 aggregate-only 规则解释。
- seed drift 在 seed `2000/3000` 上有小幅成功率下降，但未达预注册阈值，不能算成功 factor。
- ManiSkill motionplanning preflight 在 `PickCube-v1` 直接 segfault (`exit 139`)，因此 object/simulator completed-rollout 暂停，转入 formal failure/crash support 队列。
- `observation.state_key_drop`、`checkpoint.remove_processor_stats`、dataset format、dependency import/version error 都更适合 failure/crash case，不应在现有 executor 拒绝 failed runner outputs 的情况下硬跑成 completed-rollout case。

本轮 factor matrix 摘要：

```text
action_controller_interface:       8 cases, 6 detected
checkpoint_config_compatibility:   2 cases, 2 detected
evaluation_protocol_metric:        7 cases, 5 detected
evaluation_script_harness:         2 cases, 1 detected
observation_sensor_preprocessing: 13 cases, 2 detected
reset_or_initial_state:            4 cases, 1 detected
seed_or_randomness:                2 cases, 0 detected
dependency_runtime_environment:    1 case,  0 detected
```

新增验证命令：

```text
conda run -n evaltriage-lr poe check
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_state_blackout_goal_tasks457.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_state_noise_goal_tasks457.yaml --replay-budget 1 --validate-only
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_reset_disable_init_states_goal_tasks0to9.yaml --replay-budget 1 --validate-only
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_state_blackout_goal_tasks457.yaml --replay-budget 1
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_observation_state_noise_goal_tasks457.yaml --replay-budget 1
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_reset_disable_init_states_goal_tasks0to9.yaml --replay-budget 1
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_seed_drift_goal_tasks0to9_seed2000.yaml --replay-budget 1
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_seed_drift_goal_tasks0to9_seed3000.yaml --replay-budget 1
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_action_drop_postprocessor_goal_tasks457.yaml --replay-budget 1
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/validation_lerobot_action_reorder_dimensions_goal_tasks457.yaml --replay-budget 1
```

验证结果：

```text
poe check: 34 passed
no lingering evaltriage-case/evaltriage-run/lerobot-eval/overlay/maniskill_worker process
```

## 当前不应该做的事

- 不把 smoke aggregate 当论文结果。
- 不用 fake benchmark outputs 测诊断准确率。
- 不为了跑通 case 手工拼表。
- 不接入只写 manifest tag、但没有真实 backend effect 的 injection。
- 不在看到结果后临时调 threshold。

## 2026-06-29 paper full matrix / failed-run schema

目标：把 crash/failure-only factor 从“不能进入 completed-rollout 矩阵”的边缘状态，升级成正式 failed-run case；同时生成 LeRobot/LIBERO 论文主矩阵 config，并保持主表 completed-rollout 与 failure/crash 附表分离。

实现状态：

- 已新增 failed-run artifact 契约：`execution_status=completed|failed`、`FailureRecord`、`failure.json`。
- failed run 现在写入正式 run 目录：`manifest.json`、`summary.json`、空 `episodes.jsonl`、`logs.txt`、`failure.json`。
- `RunRequest`/CLI 已支持 `allow_failure`，默认仍然 failure 即抛错；只有 crash/failure case 显式允许写 failed artifact。
- completed run 仍要求至少 1 episode；failed run 禁止伪造 success/reward/episode metrics。
- `evaluation_crash_or_failure` detection 使用 execution status：baseline completed、current failed、replay completed 即 detected。
- diagnosis 已接入 failed-run replay recovery、manifest diff、failure record、injected factor；baseline 失败、replay 不恢复或不相关时仍会输出 unknown。
- 新增真实 failure backend：`checkpoint.remove_processor_stats`、`dataset.remove_feature_column`、`runtime.switch_incompatible_env`，并复用已有 `observation.state_key_drop`。
- 新增正式 ablation baselines：`no_replay`、`no_episode_evidence`、`logs_only_failure_regex`。这些是 pipeline-consistent baseline，不使用 toy/fake outputs。
- aggregate 已输出论文需要的三类主 CSV：`rq1_factor_matrix.csv`、`rq3_factor_metrics.csv`、`rq4_cost_metrics.csv`，并补充 `failures.csv`。

生成的 paper configs：

```text
scripts/generate_paper_matrix_configs.py
configs/cases/paper_lerobot_full_*                    # 16 个 LeRobot/LIBERO main-matrix configs
configs/cases/paper_failure_*                         # 4 个 failed-run configs
```

主矩阵 config 范围：

```text
platform: lerobot_libero
policy: /data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044
suite/tasks: libero_goal tasks 0-9
seeds: 1000, 2000
episodes: 2 episodes/task
case grain: factor x seed
canonical factors:
  action_controller_interface
  checkpoint_config_compatibility
  evaluation_protocol_metric
  evaluation_script_harness
  observation_sensor_preprocessing
  reset_or_initial_state
  seed_or_randomness
  dependency_runtime_environment
```

failed-run matrix 已真实执行：

```text
paper_failure_observation_state_key_drop_goal_task4_seed1000
  factor: observation_sensor_preprocessing
  failure: KeyError: observation.state
  conclusion: failure-supported

paper_failure_checkpoint_remove_processor_stats_goal_task4_seed1000
  factor: checkpoint_config_compatibility
  failure: checkpoint/processor loading failure after removing processor stats from real checkpoint overlay
  conclusion: failure-supported

paper_failure_dataset_remove_observation_state_libero10_seed1000
  factor: data_dataset_format
  failure: missing_dataset_feature during real dataset preflight
  conclusion: failure-supported

paper_failure_dependency_incompatible_env_goal_task4_seed1000
  factor: dependency_runtime_environment
  failure: incompatible conda env, lerobot-eval command missing
  conclusion: failure-supported
```

关键 artifact：

```text
/data/project/zjx/runs/evaltriage/cases/paper_failure_observation_state_key_drop_goal_task4_seed1000
/data/project/zjx/runs/evaltriage/cases/paper_failure_checkpoint_remove_processor_stats_goal_task4_seed1000
/data/project/zjx/runs/evaltriage/cases/paper_failure_dataset_remove_observation_state_libero10_seed1000
/data/project/zjx/runs/evaltriage/cases/paper_failure_dependency_incompatible_env_goal_task4_seed1000
/data/project/zjx/runs/evaltriage/metrics/paper_full_matrix_20260629
```

验证命令：

```text
python scripts/generate_paper_matrix_configs.py
conda run -n evaltriage-lr evaltriage-case --case-config <each configs/cases/paper_*.yaml> --replay-budget 1 --validate-only
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/paper_failure_observation_state_key_drop_goal_task4_seed1000.yaml --replay-budget 1
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/paper_failure_checkpoint_remove_processor_stats_goal_task4_seed1000.yaml --replay-budget 1
conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/paper_failure_dataset_remove_observation_state_libero10_seed1000.yaml --replay-budget 1
CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config configs/cases/paper_failure_dependency_incompatible_env_goal_task4_seed1000.yaml --replay-budget 1
conda run -n evaltriage-lr evaltriage-aggregate --cases-root /data/project/zjx/runs/evaltriage/cases --output-dir /data/project/zjx/runs/evaltriage/metrics/paper_full_matrix_20260629
conda run -n evaltriage-lr poe check
```

验证结果：

```text
paper configs: 20/20 validate-only passed
failed-run cases: 4/4 detected and attributed to the intended top factor
poe check: 37 passed
```

注意：

- 16 个 completed-rollout main-matrix configs 已生成并 validate-only 通过，但尚未执行完整 8 factors x 2 seeds x 10 tasks x 2 episodes/task 的长跑。
- 当前 aggregate 目录包含历史 calibration/smoke/validation cases 与 4 个 paper failed-run cases；写论文主表时应按 `case_id` 前缀或 generated config list 过滤 canonical paper cases。
- 不把 failed-run case 塞进 completed-rollout success-rate matrix；RQ3/RQ4 已按 `completed_rollout` 与 `failed_run` bucket 分开统计。

## 2026-06-29 paper main matrix full run

目标：执行 16 个 LeRobot/LIBERO completed-rollout paper main matrix case，并与已完成的 4 个 failed-run case 合并成 paper-only 结果。

执行命令：

```text
find configs/cases -maxdepth 1 -name 'paper_lerobot_full_*.yaml' | sort | while read -r cfg; do
  CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case --case-config "$cfg" --replay-budget 1
done

conda run -n evaltriage-lr evaltriage-aggregate \
  --cases-root /data/project/zjx/runs/evaltriage/cases \
  --output-dir /data/project/zjx/runs/evaltriage/metrics/paper_full_matrix_after_main_20260629

conda run -n evaltriage-lr poe check
```

运行日志：

```text
/data/project/zjx/runs/evaltriage/paper_full_matrix_run_20260629_055703.log
```

paper-only 输出：

```text
/data/project/zjx/runs/evaltriage/metrics/paper_full_matrix_after_main_20260629/paper_only_rq1_factor_matrix.csv
/data/project/zjx/runs/evaltriage/metrics/paper_full_matrix_after_main_20260629/paper_only_factor_metrics.csv
/data/project/zjx/runs/evaltriage/metrics/paper_full_matrix_after_main_20260629/paper_only_summary.json
```

paper-only 结果：

```text
paper main completed-rollout:
  cases: 16
  detected: 12
  success candidate: 12
  negative calibration: 4
  top1 among detected deviations: 12/12 = 1.0
  top1 over all main cases, counting negative calibration in denominator: 12/16 = 0.75

paper failed-run appendix:
  cases: 4
  detected: 4
  failure-supported: 4
  top1 among detected failures: 4/4 = 1.0

paper combined:
  cases: 20
  detected: 16
  success candidate: 12
  failure-supported: 4
  negative calibration: 4
  top1 among detected cases: 16/16 = 1.0
  top1 over all cases, counting negative calibration in denominator: 16/20 = 0.8
```

completed-rollout factor conclusions:

```text
action_controller_interface:        2/2 success candidate
checkpoint_config_compatibility:    2/2 success candidate
evaluation_protocol_metric:         2/2 success candidate
evaluation_script_harness:          2/2 success candidate
observation_sensor_preprocessing:   2/2 success candidate
reset_or_initial_state:             2/2 success candidate
dependency_runtime_environment:     2/2 negative calibration
seed_or_randomness:                 2/2 negative calibration
```

failed-run factor conclusions:

```text
checkpoint_config_compatibility:    1/1 failure-supported
data_dataset_format:                1/1 failure-supported
dependency_runtime_environment:     1/1 failure-supported
observation_sensor_preprocessing:   1/1 failure-supported
```

代表性 main-matrix measurements：

```text
action seed1000:       success_rate 0.8 -> 0.1, detected, top1 action_controller_interface
action seed2000:       success_rate 0.95 -> 0.0, detected, top1 action_controller_interface
checkpoint seed1000:   success_rate 0.8 -> 0.0, detected, top1 checkpoint_config_compatibility
checkpoint seed2000:   success_rate 0.95 -> 0.0, detected, top1 checkpoint_config_compatibility
eval protocol seed1000: success_rate 0.8 -> 0.0, detected, top1 evaluation_protocol_metric
eval protocol seed2000: success_rate 0.95 -> 0.0, detected, top1 evaluation_protocol_metric
observation seed1000:  success_rate 0.8 -> 0.0, detected, top1 observation_sensor_preprocessing
observation seed2000:  success_rate 0.95 -> 0.0, detected, top1 observation_sensor_preprocessing
harness seed1000:      paired outcome shift 0.30, detected, top1 evaluation_script_harness
harness seed2000:      paired outcome shift 0.25, detected, top1 evaluation_script_harness
reset seed1000:        paired outcome shift 0.30, detected, top1 reset_or_initial_state
reset seed2000:        paired outcome shift 0.10, detected, top1 reset_or_initial_state
dependency seed1000:   0.8 -> 0.8, no deviation, negative calibration
dependency seed2000:   0.95 -> 0.95, no deviation, negative calibration
seed drift 1000->2000: 0.8 -> 0.95, no thresholded deviation, negative calibration
seed drift 2000->1000: 0.95 -> 0.8, no thresholded deviation, negative calibration
```

cost summary:

```text
paper-only cases: 20
summed wall-clock across case cost records: 386.7 minutes
summed GPU minutes across case cost records: 265.0
mean wall-clock per case cost record: 19.3 minutes
```

验证结果：

```text
paper_lerobot_full case dirs: 16/16
paper_failure case dirs: 4/4
poe check: 37 passed
no lingering evaltriage-case / lerobot-eval / overlay worker processes
```

解读：

- 现在 paper main matrix 已经实际跑完，不再只是 validate-only。
- 诊断准确率应优先报告为 detected-case denominator：completed-rollout 12/12，failed-run 4/4，combined 16/16。
- 如果把 negative calibration 也放进分母，则 completed-rollout 是 12/16，combined 是 16/20；这个口径更保守，适合在正文或 appendix 里同时说明。
- 依赖运行时 MuJoCo 3.7/3.8 在 completed rollout 上是负校准，但 dependency 在 failed-run appendix 中有 failure-supported 证据。
- seed/randomness 在当前 policy/task/2-seed/2-episode 主矩阵下是负校准；不要包装成成功 factor。

## 2026-06-29 formal paper ablation

目标：做正式方法诊断型消融，不新增 toy benchmark，不使用 synthetic outputs，不混入历史 smoke/calibration case。消融只读 20 个 paper-only real artifacts，并从 `case.json`、`deviation.json`、`manifest_diff.json`、`diagnosis.json`、run `summary.json`、`failure.json` 重新计算；不信任旧 `baselines.json` 作为论文消融结果。

实现：

```text
evaltriage/metrics/ablation.py
evaltriage-ablate
```

执行命令：

```text
conda run -n evaltriage-lr evaltriage-ablate \
  --cases-root /data/project/zjx/runs/evaltriage/cases \
  --include-prefix paper_lerobot_full_ \
  --include-prefix paper_failure_ \
  --output-dir /data/project/zjx/runs/evaltriage/metrics/paper_ablation_20260629

conda run -n evaltriage-lr poe check
```

输出：

```text
/data/project/zjx/runs/evaltriage/metrics/paper_ablation_20260629/ablation_case_matrix.csv
/data/project/zjx/runs/evaltriage/metrics/paper_ablation_20260629/ablation_summary.csv
/data/project/zjx/runs/evaltriage/metrics/paper_ablation_20260629/ablation_miss_analysis.csv
```

核心结果，all bucket：

```text
evaltriage_full:          top1 among detected/applicable 16/16 = 1.000, top1 over all cases 16/20 = 0.800
no_replay:                top1 among detected/applicable 14/16 = 0.875, top1 over all cases 14/20 = 0.700
no_episode_evidence:      top1 among detected/applicable  8/12 = 0.667, top1 over all cases  8/20 = 0.400, not_applicable_rate=0.20
manifest_diff_heuristic:  top1 among detected/applicable 13/16 = 0.8125, top1 over all cases 13/20 = 0.650
single_run_judgment:      top1 among detected/applicable  0/12 = 0.000, not_applicable_rate=0.20
rerun_k:                  top1 among detected/applicable  0/12 = 0.000, not_applicable_rate=0.20
naive_statistical_gate:   top1 among detected/applicable  0/12 = 0.000, not_applicable_rate=0.20
logs_only_failure_regex:  top1 among detected/applicable  4/4  = 1.000, top1 over all cases  4/20 = 0.200, not_applicable_rate=0.80
```

关键诊断：

```text
no_episode_evidence misses:
  harness seed1000 / seed2000
  reset seed1000 / seed2000
Reason: aggregate success_rate unchanged; only paired episode outcome shift exposes the deviation.

no_replay misses:
  checkpoint feature mismatch seed1000 / seed2000
Reason: without replay recovery, manifest-only evidence ranks action_controller_interface ahead of checkpoint_config_compatibility.

manifest_diff_heuristic false attribution on negative calibration:
  dependency mujoco37 seed1000 / seed2000
  seed drift 1000->2000 / 2000->1000
Reason: config/runtime/seed fields differ, but EvalTriage full correctly abstains because no deviation is detected.

logs_only_failure_regex:
  failed-run 4/4 top1 under current code.
  dataset missing feature now top1=data_dataset_format; old baselines.json ordering is no longer used.
```

验证：

```text
evaltriage-ablate --validate-only: passed
ablation_case_matrix.csv: 160 method-case rows + header
ablation_summary.csv: 24 method-bucket rows + header
ablation_miss_analysis.csv: 81 diagnostic miss/not-applicable rows + header
poe check: 41 passed
```

解读：

- 正式消融支持“episode-level evidence 是必要组件”：去掉后 completed-rollout detected/applicable top1 从 12/12 降到 8/12。
- 正式消融支持“replay recovery 能校正 manifest-only 误导”：去掉 replay 后 checkpoint 两个 seed top1 都错到 action。
- manifest diff 是强 baseline 但会在负校准上过度归因；这正好支撑 EvalTriage 不只看配置差异。
- weak statistical baselines 能发现部分数值差异或 flakiness，但不能输出 factor attribution，因此 RQ3 top1 为 0。

## 2026-06-29 paper robustness package

目标：把原 paper-only 20 cases 扩成更稳的 robustness appendix，不做 toy benchmark，不改 threshold，不混历史 smoke/calibration，不把 failed-run 塞进 completed-rollout 矩阵。主表仍保留原 20 cases；本节新增 35 个 robustness cases，并提供 combined 55-case appendix。

实现：

```text
scripts/generate_paper_robustness_configs.py
scripts/summarize_paper_robustness.py
configs/cases/robust_lerobot_ep3_*.yaml: 27
configs/cases/robust_failure_*.yaml: 8
```

执行命令：

```text
python scripts/generate_paper_robustness_configs.py

for cfg in configs/cases/robust_*.yaml; do
  conda run -n evaltriage-lr evaltriage-case \
    --case-config "$cfg" \
    --replay-budget 1 \
    --validate-only
done

find configs/cases -maxdepth 1 -name 'robust_lerobot_ep3_*.yaml' | sort | while read -r cfg; do
  CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case \
    --case-config "$cfg" \
    --replay-budget 1
done

find configs/cases -maxdepth 1 -name 'robust_failure_*.yaml' | sort | while read -r cfg; do
  CUDA_VISIBLE_DEVICES=0 conda run -n evaltriage-lr evaltriage-case \
    --case-config "$cfg" \
    --replay-budget 1
done

conda run -n evaltriage-lr evaltriage-aggregate \
  --cases-root /data/project/zjx/runs/evaltriage/cases \
  --output-dir /data/project/zjx/runs/evaltriage/metrics/paper_robustness_20260629

python scripts/summarize_paper_robustness.py \
  --metrics-dir /data/project/zjx/runs/evaltriage/metrics/paper_robustness_20260629

conda run -n evaltriage-lr evaltriage-ablate \
  --cases-root /data/project/zjx/runs/evaltriage/cases \
  --include-prefix paper_lerobot_full_ \
  --include-prefix paper_failure_ \
  --include-prefix robust_lerobot_ep3_ \
  --include-prefix robust_failure_ \
  --output-dir /data/project/zjx/runs/evaltriage/metrics/paper_ablation_with_robustness_20260629

conda run -n evaltriage-lr poe check
```

输出：

```text
/data/project/zjx/runs/evaltriage/metrics/paper_robustness_20260629/robustness_factor_matrix.csv
/data/project/zjx/runs/evaltriage/metrics/paper_robustness_20260629/robustness_summary.csv
/data/project/zjx/runs/evaltriage/metrics/paper_robustness_20260629/robustness_failure_matrix.csv
/data/project/zjx/runs/evaltriage/metrics/paper_robustness_20260629/robustness_counts_table.csv
/data/project/zjx/runs/evaltriage/metrics/paper_robustness_20260629/combined_factor_matrix.csv
/data/project/zjx/runs/evaltriage/metrics/paper_robustness_20260629/combined_summary.csv
/data/project/zjx/runs/evaltriage/metrics/paper_ablation_with_robustness_20260629/ablation_case_matrix.csv
/data/project/zjx/runs/evaltriage/metrics/paper_ablation_with_robustness_20260629/ablation_summary.csv
/data/project/zjx/runs/evaltriage/metrics/paper_ablation_with_robustness_20260629/ablation_miss_analysis.csv
```

case counts:

```text
paper-only:       20 cases = 16 completed-rollout + 4 failed-run
robustness-only:  35 cases = 27 completed-rollout + 8 failed-run
combined:         55 cases = 43 completed-rollout + 12 failed-run
```

robustness-only conclusions:

```text
success candidate:     19
negative calibration:   8
failure-supported:      8
```

combined conclusions:

```text
success candidate:     31
negative calibration:  12
failure-supported:     12
```

completed-rollout robustness results:

```text
action_controller_interface:
  3/3 detected, 3/3 top1 correct
  success_rate 0.80/0.833/0.80 -> 0.033/0.033/0.0

checkpoint_config_compatibility:
  3/3 detected, 3/3 top1 correct
  success_rate 0.80/0.833/0.80 -> 0.0/0.0/0.0

evaluation_protocol_metric:
  3/3 detected, 3/3 top1 correct
  success_rate 0.80/0.833/0.80 -> 0.0/0.0/0.0

evaluation_script_harness:
  3/3 detected, 3/3 top1 correct
  paired_episode_outcome_mismatch_rate 0.30/0.20/0.20

observation_sensor_preprocessing:
  3/3 detected, 3/3 top1 correct
  success_rate 0.80/0.833/0.80 -> 0.0/0.0/0.0

reset_or_initial_state:
  3/3 detected, 3/3 top1 correct
  paired_episode_outcome_mismatch_rate 0.20/0.20/0.20

dependency_runtime_environment:
  1/3 detected, 1/1 detected top1 correct
  seed1000 has 1/30 paired outcome shift
  seed2000/seed3000 are negative calibration

seed_or_randomness:
  6/6 directed clean comparisons are negative calibration
  no false attribution
```

failed-run robustness results:

```text
checkpoint_config_compatibility: 2/2 failure-supported, 2/2 top1 correct
data_dataset_format:             2/2 failure-supported, 2/2 top1 correct
dependency_runtime_environment:  2/2 failure-supported, 2/2 top1 correct
observation_sensor_preprocessing:2/2 failure-supported, 2/2 top1 correct
```

failed-run schema check:

```text
8/8 current runs:  execution_status=failed and failure.json present
8/8 baseline runs: execution_status=completed
8/8 replay runs:   execution_status=completed
```

combined ablation with robustness:

```text
evaltriage_full:
  all detected/applicable top1 43/43 = 1.000
  all-case top1 43/55 = 0.782
  negative false attribution 0/12

no_replay:
  all detected/applicable top1 38/43 = 0.884
  all-case top1 38/55 = 0.691

no_episode_evidence:
  all detected/applicable top1 20/31 = 0.645
  all-case top1 20/55 = 0.364
  not_applicable_rate 12/55 = 0.218

manifest_diff_heuristic:
  all detected/applicable top1 35/43 = 0.814
  all-case top1 35/55 = 0.636
  negative false attribution 12/12 = 1.000

logs_only_failure_regex:
  failed-run top1 12/12 = 1.000
  all-case top1 12/55 = 0.218
  not_applicable_rate 43/55 = 0.782
```

验证：

```text
robust_lerobot_ep3 case dirs: 27/27
robust_failure case dirs: 8/8
robust completed-rollout standard artifacts: 27/27
robust failed-run standard artifacts: 8/8
poe check: 41 passed
```

解读：

- Robustness appendix 把样本量从 20 提高到 55，同时保留原 20 个 main paper cases 不被替换。
- 六个 completed-rollout strong factors 在 3 seeds、3 episodes/task 下都站住：action、checkpoint、eval protocol、harness、observation、reset。
- Observation 的 state blackout 解决了早期 camera drop/drop wrist 无信号的问题；结论应写成 image camera perturbation 是负校准，但 state/proprio preprocessing 是强 factor。
- Harness/reset 再次证明 episode-level evidence 的必要性：aggregate success 不一定下降，paired outcome shift 稳定出现。
- Dependency completed-rollout 不能包装成强成功 factor；它是 1/3 weak paired drift + 2/3 negative calibration，但 failed-run appendix 中有 3/3 combined failure-supported 证据。
- Seed/randomness 保持 negative calibration，说明 EvalTriage full 没有把普通 clean seed difference 误归因。
