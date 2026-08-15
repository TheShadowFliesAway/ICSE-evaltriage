# EvalTriage RQ1 Evidence Tables

输入文件 SHA256：`9bf4305b083c87d05e3c9d13593887f789fd1716d979d98602a1aaf7e15b7672`

## 0. 当前结论

- RQ1 frozen input 为 `rq1_evidence.jsonl`，共 `473` 条 GitHub issue / PR evidence。
- 本次整理只做确定性统计和表格生成，不重新 mining，不重新调用 LLM。
- `unknown_or_not_specified` 有 `153` 条，占 `32.35%`；它不是无效样本，而是表示文本报告了 evaluation deviation，但缺少足够证据归因到具体 factor。
- 本文件用于论文 RQ1 结果小节、RQ2-RQ4 fault injection 设计和 artifact 复算。

## 1. Evidence Mining Pipeline

| Stage | Count |
| --- | --- |
| GitHub keyword mining candidates | 2714 |
| Stage-1 LLM relevance screening | 641 |
| Manual classification retained evidence records | 473 |

## 2. Evidence Role 分布

| Evidence Role | Count | Percent |
| --- | --- | --- |
| deviation_and_factor | 258 | 54.55% |
| deviation_only | 144 | 30.44% |
| factor_only | 71 | 15.01% |

## 3. Primary Deviation Symptom

| Primary Symptom | Count | Percent |
| --- | --- | --- |
| success_rate_drop_or_mismatch | 141 | 29.81% |
| evaluation_crash_or_failure | 114 | 24.10% |
| rollout_behavior_anomaly | 94 | 19.87% |
| unknown_or_not_applicable | 70 | 14.80% |
| setup_sensitive_result | 20 | 4.23% |
| evaluation_instability_or_flakiness | 16 | 3.38% |
| reward_score_metric_mismatch | 9 | 1.90% |
| reproduction_failure | 9 | 1.90% |

## 4. Primary Engineering Factor

| Primary Factor | Count | Percent |
| --- | --- | --- |
| unknown_or_not_specified | 153 | 32.35% |
| dependency_runtime_environment | 48 | 10.15% |
| simulator_physics_rendering | 43 | 9.09% |
| evaluation_script_harness | 36 | 7.61% |
| action_controller_interface | 34 | 7.19% |
| reset_or_initial_state | 28 | 5.92% |
| checkpoint_config_compatibility | 28 | 5.92% |
| observation_sensor_preprocessing | 27 | 5.71% |
| seed_or_randomness | 22 | 4.65% |
| object_scene_task_initialization | 14 | 2.96% |
| training_evaluation_interaction | 13 | 2.75% |
| evaluation_protocol_metric | 13 | 2.75% |
| data_dataset_format | 12 | 2.54% |
| ci_regression_evaluation | 2 | 0.42% |

## 5. Primary Affected Phase

| Primary Phase | Count | Percent |
| --- | --- | --- |
| rollout_execution | 169 | 35.73% |
| benchmark_or_eval_setup | 123 | 26.00% |
| environment_reset | 70 | 14.80% |
| runtime_or_dependency_setup | 28 | 5.92% |
| observation_processing | 25 | 5.29% |
| metric_computation | 18 | 3.81% |
| checkpoint_or_config_loading | 17 | 3.59% |
| data_loading_or_decoding | 9 | 1.90% |
| training_eval_boundary | 5 | 1.06% |
| ci_or_regression_testing | 5 | 1.06% |
| action_execution | 3 | 0.63% |
| unknown_or_not_specified | 1 | 0.21% |

## 6. Project Coverage

| Project | Repo | Total | Deviation+Factor | Deviation Only | Factor Only | Unknown Factor % |
| --- | --- | --- | --- | --- | --- | --- |
| LeRobot | huggingface/lerobot | 105 | 59 | 38 | 8 | 37.14% |
| MetaWorld | Farama-Foundation/Metaworld | 65 | 32 | 11 | 22 | 21.54% |
| ManiSkill | mani-skill/ManiSkill | 52 | 34 | 10 | 8 | 21.15% |
| Habitat-Lab | facebookresearch/habitat-lab | 47 | 26 | 14 | 7 | 34.04% |
| OpenVLA | openvla/openvla | 33 | 16 | 15 | 2 | 45.45% |
| robosuite | ARISE-Initiative/robosuite | 27 | 12 | 9 | 6 | 37.04% |
| SimplerEnv | simpler-env/SimplerEnv | 26 | 17 | 7 | 2 | 26.92% |
| Isaac Lab | isaac-sim/IsaacLab | 23 | 13 | 5 | 5 | 21.74% |
| OpenVLA-OFT | moojink/openvla-oft | 22 | 10 | 11 | 1 | 54.55% |
| LIBERO | Lifelong-Robot-Learning/LIBERO | 16 | 9 | 7 | 0 | 43.75% |
| Habitat-Sim | facebookresearch/habitat-sim | 14 | 7 | 4 | 3 | 28.57% |
| vla-evaluation-harness | allenai/vla-evaluation-harness | 14 | 12 | 2 | 0 | 14.29% |
| RLBench | stepjam/RLBench | 13 | 3 | 7 | 3 | 53.85% |
| CALVIN | mees/calvin | 11 | 4 | 4 | 3 | 36.36% |
| ManiSkill-Learn | haosulab/ManiSkill-Learn | 5 | 4 | 0 | 1 | 0.00% |

## 7. Top Symptom x Factor Cells

| Primary Symptom | Primary Factor | Count | Percent |
| --- | --- | --- | --- |
| success_rate_drop_or_mismatch | unknown_or_not_specified | 63 | 13.32% |
| rollout_behavior_anomaly | unknown_or_not_specified | 44 | 9.30% |
| evaluation_crash_or_failure | dependency_runtime_environment | 33 | 6.98% |
| evaluation_crash_or_failure | unknown_or_not_specified | 31 | 6.55% |
| rollout_behavior_anomaly | action_controller_interface | 21 | 4.44% |
| evaluation_crash_or_failure | evaluation_script_harness | 16 | 3.38% |
| unknown_or_not_applicable | reset_or_initial_state | 15 | 3.17% |
| success_rate_drop_or_mismatch | dependency_runtime_environment | 13 | 2.75% |
| success_rate_drop_or_mismatch | checkpoint_config_compatibility | 12 | 2.54% |
| evaluation_crash_or_failure | checkpoint_config_compatibility | 12 | 2.54% |
| rollout_behavior_anomaly | simulator_physics_rendering | 12 | 2.54% |
| unknown_or_not_applicable | seed_or_randomness | 10 | 2.11% |

## 8. RQ1 Factor 到 EvalTriage Case 的映射

| Factor | RQ1 Count | Planned Operator | Benchmark | Case Family | Coverage |
| --- | --- | --- | --- | --- | --- |
| unknown_or_not_specified | 153 | manifest.hide_factor_fields | LeRobot+LIBERO; ManiSkill | unknown | core_planned |
| dependency_runtime_environment | 48 | runtime.switch_mujoco_env | LeRobot+LIBERO | setup_sensitive_factor | core_planned |
| simulator_physics_rendering | 43 | runtime.switch_mujoco_env | LeRobot+LIBERO; ManiSkill | setup_sensitive_factor | core_planned |
| evaluation_script_harness | 36 | eval_protocol.change_episode_length; evaluation_script.modify_harness_flag | LeRobot+LIBERO; ManiSkill | setup_sensitive_factor; true_regression | core_planned |
| action_controller_interface | 34 | action.scale_multiplier; action.drop_postprocessor; action.reorder_dimensions | LeRobot+LIBERO; ManiSkill | setup_sensitive_factor | core_planned |
| checkpoint_config_compatibility | 28 | checkpoint.remove_processor_stats; checkpoint.config_feature_mismatch | LeRobot+LIBERO | setup_sensitive_factor | core_planned |
| reset_or_initial_state | 28 | reset.disable_fixed_init_state; restore_seed_or_init | LeRobot+LIBERO; ManiSkill | setup_sensitive_factor | core_planned |
| observation_sensor_preprocessing | 27 | observation.swap_camera_keys; observation.image_flip; observation.drop_image_key | LeRobot+LIBERO; ManiSkill | setup_sensitive_factor | core_planned |
| seed_or_randomness | 22 | rerun_same_manifest; restore_seed_or_init | LeRobot+LIBERO; ManiSkill | flaky; setup_sensitive_factor | core_planned |
| object_scene_task_initialization | 14 | reset.disable_fixed_init_state; maniskill.change_object_pose | ManiSkill | setup_sensitive_factor | core_planned |
| evaluation_protocol_metric | 13 | eval_protocol.change_episode_length; eval_protocol.change_success_aggregation | LeRobot+LIBERO; ManiSkill | setup_sensitive_factor | core_planned |
| training_evaluation_interaction | 13 | code.semantic_bug_flag; checkpoint.remove_processor_stats | LeRobot+LIBERO | setup_sensitive_factor; true_regression | planned_extension |
| data_dataset_format | 12 | dataset.remove_feature_column; dataset.corrupt_video_or_parquet_reference | LeRobot dataset | setup_sensitive_factor | core_planned |
| ci_regression_evaluation | 2 | code.semantic_bug_flag; evaltriage-aggregate regression report | Artifact/precomputed metrics | true_regression | supporting_context |

## 9. Representative Evidence

### unknown_or_not_specified (`n=153`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | MetaWorld | [github_pr::Farama-Foundation/Metaworld::91](https://github.com/Farama-Foundation/Metaworld/pull/91) | deviation_and_factor | success_rate_drop_or_mismatch | Since `random_init=True`, a test may fail occasionally |
| 2 | MetaWorld | [github_issue::Farama-Foundation/Metaworld::405](https://github.com/Farama-Foundation/Metaworld/issues/405) | deviation_and_factor | evaluation_crash_or_failure | Maximum path length issue was introduced with PR #401 |
| 3 | Habitat-Lab | [github_issue::facebookresearch/habitat-lab::87](https://github.com/facebookresearch/habitat-lab/issues/87) | deviation_and_factor | evaluation_crash_or_failure | This is because map size for planner is limited |

### dependency_runtime_environment (`n=48`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | SimplerEnv | [github_issue::simpler-env/SimplerEnv::6](https://github.com/simpler-env/SimplerEnv/issues/6) | deviation_and_factor | evaluation_crash_or_failure | I think I got the problem. Numpy recently released 2.0.0! ... so you just install a 1.26.4 numpy and the example.py works just fine. |
| 2 | LeRobot | [github_issue::huggingface/lerobot::2697](https://github.com/huggingface/lerobot/issues/2697) | deviation_and_factor | evaluation_crash_or_failure | An incorrect transformer version is used |
| 3 | OpenVLA-OFT | [github_issue::moojink/openvla-oft::12](https://github.com/moojink/openvla-oft/issues/12) | deviation_and_factor | success_rate_drop_or_mismatch | Therefore, you will need SDPA at test time to reproduce our results. |

### simulator_physics_rendering (`n=43`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | ManiSkill | [github_issue::mani-skill/ManiSkill::571](https://github.com/mani-skill/ManiSkill/issues/571) | deviation_and_factor | rollout_behavior_anomaly | I ended up narrowing down the wrist base / palm of the hands being the cause of the bug. |
| 2 | SimplerEnv | [github_issue::simpler-env/SimplerEnv::47](https://github.com/simpler-env/SimplerEnv/issues/47) | deviation_and_factor | evaluation_crash_or_failure | it has better support and less bugs related to rendering/gpus |
| 3 | ManiSkill | [github_issue::mani-skill/ManiSkill::1070](https://github.com/mani-skill/ManiSkill/issues/1070) | deviation_and_factor | evaluation_crash_or_failure | It turns out the net contact forces API has a bug when there is no contacts, a cuda kernel is launched incorrectly, eventually leading to some strange behavior like invalid memo... |

### evaluation_script_harness (`n=36`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | LIBERO | [github_issue::Lifelong-Robot-Learning/LIBERO::3](https://github.com/Lifelong-Robot-Learning/LIBERO/issues/3) | deviation_and_factor | evaluation_crash_or_failure | I resolve the problem by adding these two lines to venv.py. if multiprocessing.get_start_method(allow_none=True) != "spawn": multiprocessing.set_start_method("spawn", force=True) |
| 2 | CALVIN | [github_issue::mees/calvin::43](https://github.com/mees/calvin/issues/43) | deviation_and_factor | evaluation_crash_or_failure | The config has been updated and soon work now. |
| 3 | LeRobot | [github_issue::huggingface/lerobot::2850](https://github.com/huggingface/lerobot/issues/2850) | deviation_and_factor | success_rate_drop_or_mismatch | the number of unique environment initial states is effectively capped at n |

### action_controller_interface (`n=34`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | ManiSkill | [github_issue::mani-skill/ManiSkill::925](https://github.com/mani-skill/ManiSkill/issues/925) | deviation_and_factor | rollout_behavior_anomaly | There is a small issue with how we sent joint signals to the physx engine. |
| 2 | Isaac Lab | [github_issue::isaac-sim/IsaacLab::911](https://github.com/isaac-sim/IsaacLab/issues/911) | deviation_and_factor | rollout_behavior_anomaly | We don't read the robot's base pose for adjusting the geometric Jacobian and end-effector targets. |
| 3 | ManiSkill | [github_issue::mani-skill/ManiSkill::252](https://github.com/mani-skill/ManiSkill/issues/252) | deviation_and_factor | success_rate_drop_or_mismatch | in the current tfds maniskill dataset, we don't decouple translation and rotation actions when calculating the new tcp pose, while for other parts of the open-x-embodiment datas... |

### reset_or_initial_state (`n=28`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | MetaWorld | [github_issue::Farama-Foundation/Metaworld::39](https://github.com/Farama-Foundation/Metaworld/issues/39) | deviation_and_factor | evaluation_crash_or_failure | the initial object and goal positions are generated uniformly between the bounds of the observation space |
| 2 | robosuite | [github_issue::ARISE-Initiative/robosuite::787](https://github.com/ARISE-Initiative/robosuite/issues/787) | deviation_and_factor | success_rate_drop_or_mismatch | Setting hard_reset=False resolves the issue |
| 3 | MetaWorld | [github_issue::Farama-Foundation/Metaworld::24](https://github.com/Farama-Foundation/Metaworld/issues/24) | deviation_and_factor | reproduction_failure | a small fix: `args_kwargs[task_name]['kwargs']['random_init'] = False ` in ml1.py. That ensures that initial state and goal position are constant upon calling `env.reset()`. |

### checkpoint_config_compatibility (`n=28`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | LeRobot | [github_issue::huggingface/lerobot::1406](https://github.com/huggingface/lerobot/issues/1406) | deviation_and_factor | success_rate_drop_or_mismatch | caused this bug. It will convert "^language_model.model" to "model.language_model" and so on. |
| 2 | LeRobot | [github_issue::huggingface/lerobot::2246](https://github.com/huggingface/lerobot/issues/2246) | deviation_and_factor | evaluation_crash_or_failure | I take latest lerobot and revert the #1771 PR, and it work in this setup without the workaround. |
| 3 | LeRobot | [github_issue::huggingface/lerobot::674](https://github.com/huggingface/lerobot/issues/674) | deviation_and_factor | evaluation_crash_or_failure | We didn't push the pretrained models on the hub yet so it's pulling the old versions which don't work with this new config system. |

### observation_sensor_preprocessing (`n=27`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | ManiSkill | [github_issue::mani-skill/ManiSkill::93](https://github.com/mani-skill/ManiSkill/issues/93) | deviation_and_factor | success_rate_drop_or_mismatch | the user_solution.py file creates a dummy environment to process observations which includes adding the base_pose. This dummy environment is not the actual environment so there... |
| 2 | ManiSkill | [github_issue::mani-skill/ManiSkill::101](https://github.com/mani-skill/ManiSkill/issues/101) | deviation_and_factor | success_rate_drop_or_mismatch | the user_solution.py file creates a dummy environment to process observations which includes adding the base_pose... this dummy environment is not the actual environment so ther... |
| 3 | LeRobot | [github_issue::huggingface/lerobot::1007](https://github.com/huggingface/lerobot/issues/1007) | deviation_and_factor | evaluation_crash_or_failure | Add this to line 254 in control_loop lerobot/common/robot_devices/control_utils.py observation.update({"task":[single_task]}) |

### seed_or_randomness (`n=22`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | MetaWorld | [github_issue::Farama-Foundation/Metaworld::555](https://github.com/Farama-Foundation/Metaworld/issues/555) | deviation_and_factor | evaluation_instability_or_flakiness | However, if you call `reset(seed=seed)` you seed numpy separately (within the environment itself) which differs from the finite set of variations created at initialization. |
| 2 | MetaWorld | [github_pr::Farama-Foundation/Metaworld::370](https://github.com/Farama-Foundation/Metaworld/pull/370) | deviation_and_factor | evaluation_instability_or_flakiness | adds a new field, `seeded_rand_vec`, that allows for the desired behavior |
| 3 | MetaWorld | [github_issue::Farama-Foundation/Metaworld::437](https://github.com/Farama-Foundation/Metaworld/issues/437) | deviation_and_factor | evaluation_instability_or_flakiness | If you're using an environment within one of the benchmarks (ie MT10, or ML1) then you need to seed the creation of the benchmark not the individual environment. When you create... |

### object_scene_task_initialization (`n=14`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | ManiSkill | [github_issue::mani-skill/ManiSkill::892](https://github.com/mani-skill/ManiSkill/issues/892) | deviation_and_factor | success_rate_drop_or_mismatch | The environment states do not encode object geometry like object scale, it only ensures the poses are the same. |
| 2 | MetaWorld | [github_issue::Farama-Foundation/Metaworld::376](https://github.com/Farama-Foundation/Metaworld/issues/376) | deviation_and_factor | evaluation_crash_or_failure | This is because the `reset()` function of these environments sets `self.obj_init_pos` to `self.adjust_initObjPos(self.init_config['obj_init_pos'])` when `self.random_init` is False |
| 3 | ManiSkill-Learn | [github_issue::haosulab/ManiSkill-Learn::6](https://github.com/haosulab/ManiSkill-Learn/issues/6) | deviation_and_factor | evaluation_crash_or_failure | the error may come from the incomplete PartNet Mobility file under the running folder |

### training_evaluation_interaction (`n=13`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | ManiSkill | [github_issue::mani-skill/ManiSkill::882](https://github.com/mani-skill/ManiSkill/issues/882) | deviation_and_factor | success_rate_drop_or_mismatch | If you run the provided script directly, it sets demos=100 by default, meaning only 100 demonstrations are used for DP training. |
| 2 | OpenVLA | [github_issue::openvla/openvla::112](https://github.com/openvla/openvla/issues/112) | deviation_and_factor | success_rate_drop_or_mismatch | Solved the plateau issue by increasing the learning rate to 1e-4. |
| 3 | ManiSkill | [github_issue::mani-skill/ManiSkill::1016](https://github.com/mani-skill/ManiSkill/issues/1016) | deviation_and_factor | rollout_behavior_anomaly | the reward does not seem to use the z axis when success == False which could encourage the sub-optimal behavior. |

### evaluation_protocol_metric (`n=13`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | MetaWorld | [github_pr::Farama-Foundation/Metaworld::475](https://github.com/Farama-Foundation/Metaworld/pull/475) | deviation_and_factor | reward_score_metric_mismatch | This means that those envs indeed did not have correct reward calculation before, from what I understand. |
| 2 | MetaWorld | [github_issue::Farama-Foundation/Metaworld::50](https://github.com/Farama-Foundation/Metaworld/issues/50) | deviation_and_factor | success_rate_drop_or_mismatch | The proper way to count TotalEnvSteps is to include all calls to step() generated by the algorithm during training, so outer+inner loop. |
| 3 | MetaWorld | [github_issue::Farama-Foundation/Metaworld::208](https://github.com/Farama-Foundation/Metaworld/issues/208) | deviation_and_factor | reproduction_failure | ML1.test_tasks should only be 10. |

### data_dataset_format (`n=12`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | Habitat-Sim | [github_issue::facebookresearch/habitat-sim::692](https://github.com/facebookresearch/habitat-sim/issues/692) | deviation_and_factor | evaluation_crash_or_failure | There's an episode with an inf's for the starting position. |
| 2 | OpenVLA | [github_issue::openvla/openvla::304](https://github.com/openvla/openvla/issues/304) | deviation_and_factor | success_rate_drop_or_mismatch | I found out the problem was because there are 2 consecutive frames of image observation with the same robot states. |
| 3 | Habitat-Lab | [github_pr::facebookresearch/habitat-lab::539](https://github.com/facebookresearch/habitat-lab/pull/539) | deviation_and_factor | evaluation_crash_or_failure | this is because the code is using the old cached dataset – the logic for writing which has been updated. |

### ci_regression_evaluation (`n=2`)

| Rank | Project | Issue / PR | Role | Primary Symptom | Quote |
| --- | --- | --- | --- | --- | --- |
| 1 | ManiSkill | [github_issue::mani-skill/ManiSkill::77](https://github.com/mani-skill/ManiSkill/issues/77) | deviation_and_factor | success_rate_drop_or_mismatch | we have discovered the bug. The evaluation system has been updated now. |
| 2 | vla-evaluation-harness | [github_pr::allenai/vla-evaluation-harness::46](https://github.com/allenai/vla-evaluation-harness/pull/46) | deviation_and_factor | evaluation_crash_or_failure | checked out without `lfs: true` → got a pointer file |

## 10. 数据质量检查

| Check | Value |
| --- | --- |
| Total records | 473 |
| Unique candidate_id | 473 |
| Missing symptom_evidence_quote | 70 |
| Missing factor_evidence_quote | 144 |
| Missing phase_evidence_quote | 104 |
| Primary evidence_role sum | 473 |
| Primary deviation symptom sum | 473 |
| Primary factor category sum | 473 |
| Primary affected phase sum | 473 |

## 11. 输出文件

| File | Purpose |
| --- | --- |
| tables/rq1_evidence_index.csv | 一行一个 GitHub issue / PR evidence。 |
| tables/rq1_taxonomy_counts.csv | taxonomy 计数和百分比。 |
| tables/rq1_project_breakdown.csv | 项目 / repo 维度分布。 |
| tables/rq1_symptom_factor_matrix.csv | primary symptom x primary factor 交叉表。 |
| tables/rq1_factor_phase_matrix.csv | primary factor x primary affected phase 交叉表。 |
| tables/rq1_representative_evidence.csv | 每个 factor 的代表性 evidence。 |
| tables/rq1_case_mapping.csv | RQ1 factor 到 EvalTriage case/operator 的映射。 |
