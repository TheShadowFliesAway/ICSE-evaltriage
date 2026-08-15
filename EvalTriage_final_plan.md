# EvalTriage：面向具身 AI 流水线中评测偏差的细粒度诊断

## 摘要

具身 AI 系统越来越多地通过复杂的评测流水线进行开发、评估和回归测试。在这些流水线中，评测偏差，例如成功率下降、奖励漂移，或非预期的 episode 级行为，是系统变化的重要信号。然而，这类偏差并不必然表示真实的策略退化。它们也可能来自仿真器版本、依赖环境、任务配置、物体初始化、传感器设置、动作接口、checkpoint 与代码兼容性，或评测协议的变化。由于具身 AI 评测通常运行成本高、统计噪声大，并且受到多个工程因素交互影响，开发者面临一个困难的分诊问题：如何判断一个观测到的偏差究竟是评测不稳定、真实回归，还是未知工程因素造成的。

本文提出 EvalTriage，一种面向具身 AI 流水线评测偏差的 factor-directed diagnosis 方法。EvalTriage 为每次运行记录结构化 evaluation manifest，捕获代码版本、checkpoint、仿真器、依赖、任务配置、传感器配置、动作接口和 episode 级结果。当检测到相对于 baseline 的偏差时，EvalTriage 分析 manifest 差异以识别可疑因素，并执行 budget-aware differential replay，有选择地控制或替换这些因素。通过 factor 级诊断规则，EvalTriage 区分 flaky deviation、true regression、setup-sensitive deviation，以及证据不足时应 abstain 的 unknown case，并生成面向开发者行动的报告，对可能原因进行排序或说明缺失证据。我们进一步对开源具身 AI 和机器人学习项目中的可复现性与回归问题进行跨项目实证研究，归纳具身场景特有的评测偏差模式 taxonomy，并通过重复评测运行和可控故障注入评估 EvalTriage。实验表明，EvalTriage 在 XXX 个项目、XXX 类偏差和 XXX 个偏差场景中，以 XXX 的准确率识别偏差类型，并相比完整评测重跑将诊断成本降低 XXX%。

## 1. 核心思想

EvalTriage 关注当具身 AI 评测流水线产生非预期结果时出现的诊断问题。目标信号不是传统的 pass/fail 测试失败，而是 **evaluation deviation**：相对于 baseline，在 benchmark、evaluation 或 rollout 行为中出现的统计上或语义上有意义的变化。

典型评测偏差包括：

- 成功率下降或不匹配；
- reward drift；
- score 或 metric 差异；
- 无法复现 official、paper、baseline 或 leaderboard 结果；
- 非预期的 episode 级行为，例如机器人抖动、原地移动、产生接近零的动作，或所有 rollout 都失败；
- evaluation crash 或 rollout 未完成；
- 由 task、simulator、dependency、action、sensor、checkpoint 或 evaluation protocol 变化导致的 setup-sensitive result。

核心观点是：许多具身 AI 评测偏差并非纯随机现象，也并不总是真实策略回归。它们往往来自评测流水线中有限的一组工程因素。如果每次运行都记录足够的工程上下文，并且在 replay 时有选择地控制或替换可疑因素，那么偏差就可以从一个不透明的 benchmark drop 转化为一个可诊断的软件工程问题。

## 2. 研究问题

研究问题是：

> 当具身 AI benchmark 或 evaluation 结果相对于 baseline 发生偏差时，开发者如何判断该偏差是 flaky evaluation behavior、true regression，还是 setup-sensitive engineering factor 造成的？当证据不足时，又如何避免过度归因并在可接受的诊断成本下指出最值得补采的证据？

这个问题不同于传统开源软件 CI 中的 flaky-test 检测。传统 CI 通常观测确定性的 pass/fail 测试。具身 AI 评测流水线产生的是有噪声、成本高、多因素影响的输出，例如 success rate、reward、trajectory-level behavior 和 episode-level outcome。成功率下降可能反映真实策略回归，但也可能反映仿真器漂移、物体初始化变化、动作接口不匹配、传感器预处理不匹配、checkpoint-code 不兼容，或评测协议变化。

## 3. 研究问题列表

**RQ1.** 在开源具身 AI、机器人学习、仿真和 VLA 评测项目中，常见的评测偏差模式和影响评测的工程因素有哪些？

**RQ2.** 相比 single-run evaluation、fixed-seed evaluation、rerun-k 和 naive statistical gates，EvalTriage 能否更准确地区分 flaky evaluation behavior、true regression、setup-sensitive deviation 和 evidence-insufficient unknown cases？

**RQ3.** EvalTriage 能否在证据充分时将评测偏差归因到具体工程因素，例如物体初始化、仿真器版本漂移、依赖漂移、动作 schema 不匹配、传感器配置漂移、checkpoint-code mismatch、evaluation protocol drift 或语义代码回归，并在证据不足时正确 abstain？

**RQ4.** EvalTriage 能否在保持诊断准确率的同时，减少不必要重跑、GPU 小时数、墙钟诊断时间和人工调试成本？

## 4. 目标用户和使用场景

EvalTriage 面向：

- 具身 AI 和机器人学习项目维护者；
- benchmark 和 evaluation harness 维护者；
- VLA 和机器人策略开发者；
- 负责 release 或 merge 决策的开发者；
- 尝试复现已报告 benchmark 结果的研究者；
- 为具身 AI 评测流水线构建 CI/CD 工具的开发者。

EvalTriage 帮助回答的实际问题包括：

- 这个偏差是否应该阻塞 merge 或 release？
- 这是 flaky evaluation result 还是真实回归？
- 开发者应该重跑、锁定依赖、修复任务初始化、检查动作适配、检查 checkpoint 兼容性，还是回滚代码？
- 应该优先检查哪个工程因素？
- 后续评测运行如何避免同样的不可复现或不可比较结果？

## 5. 评测偏差 Taxonomy

EvalTriage 使用一个由两部分连接而成的 taxonomy：观测到的 deviation symptoms 和可能的 engineering factors。

### 5.1 Deviation Symptoms

symptom taxonomy 捕获开发者观察到的现象：

- **Reproduction failure：** 无法复现 reported、official、paper、baseline 或 leaderboard 结果。
- **Success-rate drop or mismatch：** 成功率低于预期，在可比较运行之间不一致，或变为零。
- **Reward / score / metric mismatch：** reward、score、metric 或 leaderboard 值不同于预期值。
- **Rollout behavior anomaly：** 机器人或 agent 抖动、原地移动、产生零或接近零的动作、无法抓取物体，或所有 rollout 都失败。
- **Evaluation crash or failure：** evaluation、benchmark、rollout 或 environment reset 崩溃，或无法完成。
- **Evaluation instability or flakiness：** 在本应固定的条件下重复运行却产生不稳定结果。
- **Setup-sensitive result：** 结果在不同 task setting、camera setting、action step、dependency version、seed、simulator version 或 evaluation configuration 下发生显著变化。

### 5.2 Engineering Factors

factor taxonomy 捕获可能解释偏差的因素：

- **Seed or randomness：** seed 处理、非确定性、随机评测，或重复运行不稳定。
- **Reset or initial state：** 环境 reset 行为、复用环境状态、episode 初始化，或初始仿真状态。
- **Object / scene / task initialization：** 物体姿态、场景设置、目标位置、任务采样，或 first-episode initialization。
- **Simulator / physics / rendering：** 仿真器版本、MuJoCo / Isaac / Habitat 行为、物理变化、渲染后端，或 headless rendering。
- **Dependency / runtime environment：** Python、CUDA、driver、Docker、OS、package version，或 runtime environment drift。
- **Action / controller interface：** action schema、action scaling、action normalization、controller behavior、IK、gripper action、action dtype，或 action shape。
- **Observation / sensor / preprocessing：** camera pose、camera resolution、observation space、sensor configuration、image preprocessing、normalization，或 missing observations。
- **Checkpoint / config compatibility：** checkpoint mismatch、config mismatch、checkpoint-code mismatch，或 model loading incompatibility。
- **Evaluation protocol / metric：** success condition、metric definition、termination condition、episode length、normalization，或 protocol drift。
- **Evaluation script / harness：** eval script、benchmark wrapper、rollout script、environment lifecycle、manifest handling，或 evaluation command behavior。
- **CI / regression evaluation：** nightly benchmarks、continuous evaluation、leaderboard monitoring，或 regression benchmark infrastructure。
- **Data / dataset format：** dataset format、feature mismatch、missing data、video stream decoding、dataset-environment mismatch，或影响评测的数据加载问题。
- **Training / evaluation interaction：** evaluation 改变 training state、train/eval mode 没有恢复、BatchNorm 或 Dropout 状态被影响，或 evaluation 污染后续训练。
- **Unknown or not specified：** issue 报告了偏差，但没有提供足够证据进行 factor attribution。

## 6. EvalTriage 设计

EvalTriage 由五个集成组件组成：evidence taxonomy、evaluation manifest、factor-directed differential replay、factor attribution 和面向开发者行动的 diagnosis report。

### 6.1 Evaluation Manifest

每次评测运行都会记录一个结构化 manifest，用来捕获该运行的工程上下文。manifest 被设计用于回答一个具体问题：

> baseline run 和 current evaluation run 之间发生了什么变化？

manifest 记录：

- repository commit 和 code version；
- policy checkpoint 和 checkpoint checksum；
- checkpoint configuration；
- task suite、task id 和 task configuration；
- random seed 和 seed-handling policy；
- simulator version 和 build version；
- dependency lockfile；
- Python、CUDA、GPU、driver、OS 和 Docker environment；
- object initial pose 和 scene initialization metadata；
- robot embodiment 和 controller configuration；
- action schema、action scaling、action adaptor 和 action normalization；
- sensor configuration、camera pose、camera resolution 和 preprocessing configuration；
- evaluation command 和 evaluation script version；
- metric definition、success condition、termination condition 和 episode length；
- episode-level success / failure、reward、success rate 和 runtime logs。

manifest 不只是日志。它是 factor comparison、replay planning 和 diagnosis reporting 的基础。

### 6.2 Deviation Detection

EvalTriage 通过比较 current run 与 baseline run 或 baseline distribution 来检测评测偏差。比较方式可以包括：

- 绝对 success-rate 或 reward threshold；
- 相对于 baseline mean 或 confidence interval 的偏离；
- 与 reported、official、paper、baseline、previous 或 leaderboard result 的不匹配；
- episode-level anomaly signal；
- crash 或 incomplete rollout signal；
- repeated-run instability indicator。

检测输出是一个 deviation record，包含受影响的 benchmark、metric、task subset、episode trace 和 baseline comparison。

### 6.3 Factor-Directed Differential Replay

当检测到偏差时，EvalTriage 不会盲目多次重跑完整 benchmark。相反，它使用 manifest difference 和 deviation taxonomy 来选择一小组可疑因素，并执行 controlled replay。

代表性的 replay action 包括：

- 固定 code 和 checkpoint，同时改变 seed，以测试 seed-driven instability；
- 固定 seed，同时控制 object pose 或 scene initialization；
- 使用 baseline simulator 或 dependency environment replay，以测试 version drift；
- 使用 baseline action adaptor 或 action schema replay，以测试 action-interface mismatch；
- 使用 baseline sensor configuration 或 preprocessing pipeline replay，以测试 observation drift；
- 使用 baseline evaluation protocol、success condition、metric definition、termination condition 或 normalization replay；
- 使用 baseline checkpoint 或 baseline code replay，以测试 checkpoint-code compatibility；
- 当偏差局部化时，只 replay 受影响 task subset，而不是整个 benchmark。

目标不是穷举搜索。目标是 budget-aware diagnosis：基于 manifest 中已有的 factor evidence，优先运行信息量最大的 replay。

### 6.4 Factor Attribution

EvalTriage 将 replay outcome 转化为排序后的 factor diagnosis。归因过程考虑：

- baseline 和 current run 之间哪些因素发生了变化；
- 哪个 controlled replay 恢复了 baseline behavior；
- 哪些 factor change 增加或减少了 variance；
- 哪些 task、episode 或 behavior trace 受影响；
- 偏差是 stable、flaky、setup-sensitive 还是 localized。

归因输出不一定是单一 root cause。它是带有支持证据的可疑因素排序列表。例如：

1. action schema mismatch - high confidence；
2. checkpoint-code mismatch - medium confidence；
3. simulator version drift - low confidence；
4. semantic code regression - low confidence。

### 6.5 Diagnosis Report

EvalTriage 生成面向开发者行动的报告。报告包含：

- deviation status：likely flaky evaluation behavior、likely true regression、likely setup-sensitive deviation，或 evidence-insufficient unknown；
- affected benchmark、task subset 和 metric；
- baseline result 和 current result；
- suspicious factor ranking；
- 来自 manifest comparison 和 replay outcome 的证据；
- 推荐的后续行动。

示例报告：

```text
Status: likely setup-sensitive evaluation deviation
Observed deviation: success rate dropped from 74.6% to 60.0% on affected tasks
Most suspicious factors:
1. sensor configuration / camera masking: high confidence
2. observation preprocessing: medium confidence
3. policy regression: low confidence
Evidence:
- Camera blackout changed success rate while code and checkpoint were unchanged.
- Deviation concentrates on tasks requiring visual localization.
Recommended actions:
- Verify camera configuration and preprocessing.
- Re-run affected task subset with baseline sensor manifest.
- Check whether the checkpoint was trained under the same observation setup.
```

## 7. 实证证据挖掘

EvalTriage 包含一项针对开源具身 AI 和机器人学习项目中评测偏差的跨项目实证研究。目标是证明 evaluation deviation 和 evaluation-affecting factor 是真实存在、反复出现，并且具有具身场景特异性的。

候选项目包括：

- LeRobot；
- LIBERO；
- OpenVLA 和 OpenVLA-OFT；
- vla-evaluation-harness；
- Habitat-Sim 和 Habitat-Lab；
- ManiSkill 和 ManiSkill-Learn；
- CALVIN；
- RLBench；
- robosuite；
- MetaWorld；
- Isaac Lab；
- SimplerEnv。

实证研究从 GitHub issues、PR discussions、release notes、benchmark documentation 和 evaluation-related discussions 中挖掘：

- 无法复现的 benchmark result；
- fixed-seed evaluation 仍然不稳定；
- official checkpoint result 无法复现；
- action schema 或 action adaptor 问题；
- 影响结果的 simulator version change；
- object initialization 或 seeded object-position 问题；
- dependency 或 runtime drift；
- nightly regression CI 或 benchmark roadmap discussions；
- IK、controller、joint-limit 或 gripper 问题；
- sensor 或 camera-pose 问题；
- evaluation protocol、metric、termination 或 normalization 问题。

挖掘到的证据用于构建 taxonomy、动机化诊断问题，并设计真实的 fault injection case。

## 8. 实验设计

EvalTriage 通过 repeated evaluation runs 和 controlled fault injection 进行评估。主要实验平台是具有可用 benchmark、checkpoint 和 task suite 的具身 AI 评测流水线，例如 LeRobot + LIBERO，以及 ManiSkill 或相关环境中的 manipulation benchmark。

每个实验 case 记录：

- baseline manifest 和 current manifest；
- baseline result 和 current result；
- episode-level outcomes；
- injected 或 observed factor change；
- replay configuration；
- expected deviation type；
- expected factor category；
- EvalTriage diagnosis result；
- diagnosis cost。

可控故障注入包括：

- seed-handling bug；
- object pose not fixed；
- simulator version drift；
- dependency version drift；
- action scaling change；
- action adaptor semantic change；
- task configuration change；
- sensor configuration change；
- evaluation protocol 或 metric change；
- checkpoint-code mismatch；
- semantic code regression。

Baselines 包括：

- single-run judgment；
- fixed-seed evaluation；
- 使用 majority vote 或 mean result 的 rerun-k；
- 使用 mean、variance、confidence interval 或 fixed threshold 的 naive statistical gate；
- 不使用 manifest、replay 或 attribution 的 original benchmark script；
- 不使用 differential replay 的 manifest-diff heuristic；
- 移除 selected manifest fields、replay、attribution 或 episode-level evidence 的 EvalTriage ablated variants。

Evaluation metrics 包括：

- flaky deviation precision、recall 和 F1；
- true regression precision、recall 和 F1；
- unknown rate；
- unknown / abstention correctness；
- false alarm rate；
- missed regression rate；
- Top-1 factor attribution accuracy；
- Top-3 factor attribution accuracy；
- factor ranking 的 MRR；
- rerun count；
- GPU hours；
- wall-clock diagnosis time；
- diagnosis latency；
- pipeline overhead；
- 开发者对 diagnosis report usefulness 的评分。

## 9. 预期贡献

EvalTriage 的贡献包括：

1. **问题定义。** 将 evaluation deviation diagnosis 定义为具身 AI 评测流水线特有的软件工程问题。
2. **实证 taxonomy。** 从跨项目证据中归纳具身场景特有的 evaluation deviation symptoms 和 engineering factors taxonomy。
3. **Evaluation manifest。** 引入结构化 manifest，用于捕获 benchmark 和 evaluation run 的工程上下文。
4. **Factor-directed differential replay。** 提出一种 budget-aware replay 策略，有选择地控制可疑因素，而不是盲目重跑 benchmark。
5. **Factor attribution 和 diagnosis reports。** 对可能原因排序，并生成面向开发者行动的推荐。
6. **可控评估。** 使用 repeated runs 和 controlled fault injection 评估诊断准确率与成本。

## 10. 预期发现

预期发现包括：

- 具身 AI 评测偏差具有传统 OSS CI flaky-test detection 难以覆盖的 failure modes。
- Fixed seeds 和 rerun-k 并不足够，因为它们可以识别不稳定性，但无法解释其原因。
- 基于 manifest 的 differential replay 能提高区分 flaky evaluation behavior、true regression、setup-sensitive deviation 和 evidence-insufficient unknown cases 的能力。
- 许多 evaluation deviation 可以归因到反复出现的工程因素，例如 object initialization、simulator drift、action interface mismatch、sensor configuration drift、checkpoint-code mismatch 或 evaluation protocol drift。
- EvalTriage 可以减少不必要重跑和人工调试工作，并比原始 benchmark logs 提供更可操作的诊断。

## 11. 范围和非目标

EvalTriage 不旨在提升策略性能，也不提出新的具身 AI benchmark。它也不替代 benchmark harness。相反，它通过诊断 benchmark、evaluation 或 rollout 结果为何发生变化，来补充现有评测流水线。

EvalTriage 不是通用 CI 系统。它关注 post-deviation triage 问题：当观测到 evaluation deviation 后，判断该偏差是 flaky、true regression，还是 setup-sensitive engineering factor 导致；当证据不足时，EvalTriage 应拒绝过度归因，并指出最值得补采的证据。
