# RQ1 Evidence JSONL 移交说明

## 1. 文件位置

最终移交文件：

```text
rq1_evidence.jsonl
```

该文件用于后续 RQ1 总结、表格整理和论文证据支撑。

## 2. 文件形成流程

本文件由 GitHub evidence mining pipeline 逐步生成：

1. **GitHub 初始挖掘**

   从配置的开源具身 LeRobot、Habitat-Sim、ManiSkill、vla-evaluation-harness、OpenVLA-OFT、LIBERO、Habitat-Lab、ManiSkill-Learn、CALVIN、RLBench、robosuite、MetaWorld、Isaac Lab、SimplerEnv、OpenVLA 项目中，按关键词检索 issues 和 PRs，得到初始候选：
   当前共有 `2714` 条候选。

   检索关键词内容如下：
   

2. **第一阶段 LLM 预筛选**

   使用 LLM 对初始候选做粗粒度相关性筛选，判断其是否可能与 evaluation deviation、benchmark、rollout、reproducibility 或 evaluation-affecting factor 有关。

   保留第一阶段中较可能相关的候选，得到 `641` 条候选。

3. **人工证据分类与保留**

   对 LLM 预筛选后的 `641` 条候选进行单人逐条人工细粒度 evidence classification，判断其是否真正构成 evaluation deviation、evaluation-affecting factor 或二者兼有的证据，并标注 evidence role、deviation symptom、engineering factor、affected phase 与 evidence quote。人工分类后最终保留 `473` 条相关 evidence。

4. **合并原文上下文**
   人工分类结果合并原 issue / PR 文件，生成文件：
   ```text
   rq1_evidence.jsonl
   ```

## 3. 文件粒度

`rq1_evidence.jsonl` 是 JSONL 文件，每一行是一条 evidence record。

每条记录对应一个 GitHub issue 或 PR，并包含两类信息：

- 原始 GitHub 候选内容：repo、title、url、body、comments 等；
- 人工分类结果：deviation symptom、engineering factor、affected phase、evidence quote 等。

## 4. 字段说明

### 4.1 原始候选字段

| 字段 | 含义 |
|---|---|
| `candidate_id` | 候选唯一 ID，格式通常为 `github_issue::owner/repo::number` 或 `github_pr::owner/repo::number`。 |
| `project` | 项目名称，来自 repo 配置。 |
| `repo` | GitHub 仓库全名，例如 `huggingface/lerobot`。 |
| `source_type` | 来源类型，当前主要为 `issue` 或 `pr`。 |
| `number` | GitHub issue / PR 编号。 |
| `title` | issue / PR 标题。 |
| `url` | GitHub 页面 URL。 |
| `state` | issue / PR 状态，例如 `open` 或 `closed`。 |
| `labels` | GitHub labels。 |
| `created_at` | 创建时间。 |
| `updated_at` | 更新时间。 |
| `closed_at` | 关闭时间；未关闭时为 `null`。 |
| `matched_keywords` | mining 阶段命中的关键词。 |
| `linked_urls` | 正文或评论中抽取到的链接。 |
| `retrieved_at` | 本地抓取该候选的时间。 |
| `body` | issue / PR 正文，完整保留，不截断。 |
| `comments` | issue / PR comments，完整保留，不截断。 |
| `comment_count` | comments 数量。 |

### 4.2 分类字段

| 字段 | 含义 |
|---|---|
| `evidence_role` | 该记录提供的证据角色。 |
| `deviation_symptoms` | 该记录涉及的所有 deviation symptom，多标签列表。 |
| `factor_categories` | 该记录涉及的所有 engineering factor，多标签列表。 |
| `affected_phases` | 该记录涉及的 evaluation pipeline 阶段，多标签列表。 |
| `primary_deviation_symptom` | 最主要的 deviation symptom。 |
| `primary_factor_category` | 最主要的 engineering factor。 |
| `primary_affected_phase` | 最主要的 affected phase。 |
| `symptom_evidence_quote` | 支撑 deviation symptom 的原文短句。 |
| `factor_evidence_quote` | 支撑 engineering factor 的原文短句。 |
| `phase_evidence_quote` | 支撑 affected phase 的原文短句；可能为空。 |

## 5. 枚举值说明

### 5.1 `evidence_role`

| 枚举值 | 含义 |
|---|---|
| `deviation_only` | 文本报告了 evaluation / benchmark / rollout deviation，但没有明确工程因素。 |
| `factor_only` | 文本报告了影响 evaluation / benchmark / rollout 的工程因素，但没有明确 deviation metric 或 outcome。 |
| `deviation_and_factor` | 文本同时报告了 deviation 和与之相关的工程因素。 |

### 5.2 `deviation_symptoms`

| 枚举值 | 含义 |
|---|---|
| `reproduction_failure` | 无法复现 reported / official / paper / baseline / leaderboard 结果。 |
| `success_rate_drop_or_mismatch` | 成功率下降、为零，或与预期 / 官方 / baseline 结果不一致。 |
| `reward_score_metric_mismatch` | reward、score、metric 或 leaderboard 数值不一致。 |
| `rollout_behavior_anomaly` | rollout 中出现机器人抖动、原地移动、zero actions、stuck policy、抓取失败等异常行为。 |
| `evaluation_crash_or_failure` | evaluation、benchmark、rollout 或环境 reset 崩溃或无法完成。 |
| `evaluation_instability_or_flakiness` | 相同或相近条件下重复评测结果不稳定。 |
| `setup_sensitive_result` | 结果对 seed、task、camera、action steps、dependency、simulator 或 eval config 等设置敏感。 |
| `unknown_or_not_applicable` | 没有明确 deviation symptom，或该维度不适用。 |

### 5.3 `factor_categories`

| 枚举值 | 含义 |
|---|---|
| `seed_or_randomness` | seed 处理、随机性或非确定性导致的评测差异。 |
| `reset_or_initial_state` | 环境 reset、初始状态、环境复用或 episode 初始化相关因素。 |
| `object_scene_task_initialization` | 物体位置、场景设置、任务初始化或目标采样相关因素。 |
| `simulator_physics_rendering` | 仿真器、物理引擎、渲染后端或 headless rendering 相关因素。 |
| `dependency_runtime_environment` | Python、CUDA、driver、Docker、OS、包版本或运行环境相关因素。 |
| `action_controller_interface` | action schema、action scaling、control mode、controller、IK、gripper、action shape/dtype 等因素。 |
| `observation_sensor_preprocessing` | camera、sensor、observation space、image preprocessing、normalization 或 missing observation 相关因素。 |
| `checkpoint_config_compatibility` | checkpoint、policy config、processor config、feature schema 或 checkpoint-code 兼容性问题。 |
| `evaluation_protocol_metric` | success condition、metric definition、termination condition、episode length、aggregation 或 protocol drift。 |
| `evaluation_script_harness` | eval script、benchmark wrapper、rollout script、命令行参数、环境生命周期或 harness 行为问题。 |
| `ci_regression_evaluation` | nightly benchmark、continuous evaluation、leaderboard monitoring 或 regression CI 相关因素。 |
| `data_dataset_format` | dataset format、feature mismatch、missing data、video decoding、dataset-environment mismatch 或数据加载问题。 |
| `training_evaluation_interaction` | train/eval mode、validation split、normalization statistics、训练状态与评测相互影响。 |
| `unknown_or_not_specified` | 文本报告了偏差，但没有足够证据归因到具体 factor。 |

### 5.4 `affected_phases`

| 枚举值 | 含义 |
|---|---|
| `benchmark_or_eval_setup` | benchmark / evaluation 启动、配置和准备阶段。 |
| `checkpoint_or_config_loading` | checkpoint、policy config、processor config 加载阶段。 |
| `environment_reset` | 环境 reset、初始状态恢复、episode 初始化阶段。 |
| `rollout_execution` | policy rollout / inference 执行阶段。 |
| `observation_processing` | observation、sensor、camera、image preprocessing 处理阶段。 |
| `action_execution` | action 后处理、controller、gripper、IK 或环境 step 执行阶段。 |
| `metric_computation` | success rate、reward、score、metric 计算阶段。 |
| `runtime_or_dependency_setup` | runtime、dependency、CUDA、Docker、driver、OS 或 package setup 阶段。 |
| `data_loading_or_decoding` | dataset、video、parquet/json、feature 或 dataloader 读取解析阶段。 |
| `ci_or_regression_testing` | CI、nightly benchmark、regression evaluation 或 leaderboard monitoring 阶段。 |
| `training_eval_boundary` | 训练与评测交界处，例如 train/eval mode、validation split、评测污染训练状态。 |
| `unknown_or_not_specified` | 无法判断影响阶段，或该维度不适用。 |

## 6. 使用注意

- 本文件适合用于 RQ1 的证据整理和后续统计。
- `body` 和 `comments` 为完整原文，文件体积较大，后续处理时应按 JSONL 流式读取。
- `symptom_evidence_quote`、`factor_evidence_quote` 和 `phase_evidence_quote` 是 LLM 从原文中抽取的证据短句。
- `unknown_or_not_specified` 不代表无用样本，而是表示文本只报告了现象，但没有足够证据支持具体 factor 归因。
