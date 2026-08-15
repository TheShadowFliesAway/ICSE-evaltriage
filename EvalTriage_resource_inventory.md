# EvalTriage 当前资源与环境清单

更新时间：2026-06-27 01:03 CST

本文档记录当前 EvalTriage 实验前资源、conda 环境、关键路径和已验证状态。原则仍然是：项目代码和文档放在 `/home/ubuntu/zjx/EvalTriage`，大资源、checkpoint、cache、assets 和 run 输出放在 `/data/project/zjx`。

## 1. 总体目录

```text
/home/ubuntu/zjx/EvalTriage
  项目文档、实验计划、后续 wrapper / scripts

/home/ubuntu/zjx/lerobot
  LeRobot 源码安装目录
  当前 commit: 6a788fbd

/data/project/zjx
  cache/
  checkpoints/
  assets/
  datasets/
  runs/
  logs/
```

当前磁盘占用：

```text
/data/project/zjx/cache        8.5G
/data/project/zjx/checkpoints  6.6G
/data/project/zjx/assets       408M
/data/project/zjx/datasets     12G
/data/project/zjx/runs         144K
/data/project/zjx/logs         24K
```

## 2. 已下载资源

### 2.1 LeRobot / LIBERO policy checkpoint

只下载了核心实验 policy：

```text
/data/project/zjx/checkpoints/lerobot/pi0_libero_finetuned_v044
```

关键文件：

```text
7011548640  model.safetensors
7668        policy_preprocessor_step_5_normalizer_processor.safetensors
7668        policy_postprocessor_step_0_unnormalizer_processor.safetensors
5629        train_config.json
4033        README.md
2191        config.json
1881        policy_preprocessor.json
1519        .gitattributes
660         policy_postprocessor.json
```

未下载：

```text
lerobot/pi0_libero_base
```

原因：当前实验计划只需要 `lerobot/pi0_libero_finetuned_v044`，base policy 不进入核心矩阵。

### 2.2 LIBERO runtime assets

LIBERO benchmark 运行所需 assets 已下载：

```text
/data/project/zjx/assets/libero/assets
```

当前状态：

```text
大小：408M
文件数：1174
来源：lerobot/libero-assets
```

这些 assets 是 LeRobot + LIBERO evaluation 的运行时资源，不是 demonstration / training dataset。

### 2.3 LIBERO config

项目使用本地 LIBERO config，不写 `~/.libero/config.yaml`：

```text
/data/project/zjx/assets/libero/config/config.yaml
```

内容：

```yaml
assets: /data/project/zjx/assets/libero/assets
bddl_files: /home/ubuntu/anaconda3/envs/evaltriage-lr/lib/python3.12/site-packages/libero/libero/bddl_files
datasets: /data/project/zjx/assets/libero/datasets
init_states: /home/ubuntu/anaconda3/envs/evaltriage-lr/lib/python3.12/site-packages/libero/libero/init_files
```

注意：`hf-libero` 的 `get_assets_path()` 默认优先找包内 `libero/libero/assets`，找不到会尝试自动下载到 home cache。为避免资源写到 `~/.cache/libero`，已在 `evaltriage-lr` 环境内建立 symlink：

```text
/home/ubuntu/anaconda3/envs/evaltriage-lr/lib/python3.12/site-packages/libero/libero/assets
  -> /data/project/zjx/assets/libero/assets
```

运行 LeRobot + LIBERO 时仍建议设置：

```bash
export LIBERO_CONFIG_PATH=/data/project/zjx/assets/libero/config
```

### 2.4 ManiSkill assets

目录已创建：

```text
/data/project/zjx/assets/maniskill
```

当前大小很小是正常的。已确认以下任务的 ManiSkill `DATA_GROUPS` 为空，不需要通过 `mani_skill.utils.download_asset` 额外下载 task assets：

```text
PickCube-v1           []
StackCube-v1          []
PegInsertionSide-v1   []
PushCube-v1           []
```

这些任务已经通过 env reset smoke。

### 2.5 Dataset / data-format fault 资源

已补充当前最终主线需要的 dataset / data-format fault 资源：

```text
/data/project/zjx/datasets/lerobot/libero_10_image
```

当前状态：

```text
大小：12G
parquet 文件数：148
来源：lerobot/libero_10_image
```

关键 metadata：

```text
/data/project/zjx/datasets/lerobot/libero_10_image/meta/info.json
/data/project/zjx/datasets/lerobot/libero_10_image/meta/stats.json
/data/project/zjx/datasets/lerobot/libero_10_image/meta/tasks.parquet
```

未下载完整 `HuggingFaceVLA/libero`。原因：该数据集约 32.5G，当前最终主线使用 LeRobot 格式的 `lerobot/libero_10_image` 来实现 dataset/data-format fault；完整 `HuggingFaceVLA/libero` 不进入核心矩阵。

未下载其他 benchmark external-validity 资源，例如 CALVIN、RLBench、MetaWorld 额外 policy/assets。原因：当前 ICSE 主线先以 LeRobot + LIBERO 和 ManiSkill 支撑。

### 2.6 PaliGemma tokenizer / processor cache

PI0 preprocessor 会使用 `google/paligemma-3b-pt-224` tokenizer。已预取 tokenizer/config 小文件，未下载该 gated model 的 10.9G 权重：

```text
/data/project/zjx/cache/huggingface/assets/google-paligemma-3b-pt-224-tokenizer
```

关键文件：

```text
17549604  tokenizer.json
4264023   tokenizer.model
39968     tokenizer_config.json
699       preprocessor_config.json
607       special_tokens_map.json
24        added_tokens.json
```

## 3. Conda 环境

### 3.1 evaltriage-lr

路径：

```text
/home/ubuntu/anaconda3/envs/evaltriage-lr
```

用途：

```text
LeRobot + LIBERO policy evaluation
```

当前关键版本：

```text
python       3.12.13
lerobot      0.5.2
libero       /home/ubuntu/anaconda3/envs/evaltriage-lr/lib/python3.12/site-packages/libero/__init__.py
torch        2.11.0+cu126
torchvision  0.26.0+cu126
torchcodec   0.11.1+cu126
cuda         available=True, torch CUDA=12.6
```

说明：

- LeRobot 是源码 editable install，源码在 `/home/ubuntu/zjx/lerobot`。
- PyTorch 已从默认 CUDA 13 wheel 切换到 CUDA 12.6 wheel，以匹配机器驱动。

### 3.2 evaltriage-ms

路径：

```text
/home/ubuntu/anaconda3/envs/evaltriage-ms
```

用途：

```text
ManiSkill controlled injection
```

当前关键版本：

```text
python       3.11.15
mani_skill   3.0.1
torch        2.12.1+cu126
cuda         available=True, torch CUDA=12.6
```

### 3.3 evaltriage-lr-mujoco37

路径：

```text
/home/ubuntu/anaconda3/envs/evaltriage-lr-mujoco37
```

用途：

```text
LeRobot + LIBERO simulator/runtime drift 对照环境
```

当前关键版本：

```text
python       3.12.13
lerobot      0.5.2
libero       /home/ubuntu/anaconda3/envs/evaltriage-lr-mujoco37/lib/python3.12/site-packages/libero/__init__.py
mujoco       3.7.0
torch        2.11.0+cu126
cuda         available=True, torch CUDA=12.6
```

说明：

- 该环境从 `evaltriage-lr` clone 后只将 `mujoco` 降为 `3.7.0`。
- 原始 `evaltriage-lr` 仍保持 `mujoco 3.8.1`，未被污染。

## 4. 运行时环境变量

不要写入全局 shell 配置。每次准备或运行 EvalTriage 时，在当前 session 设置：

```bash
export HF_HOME=/data/project/zjx/cache/huggingface
export HF_HUB_CACHE=/data/project/zjx/cache/huggingface/hub
export HUGGINGFACE_HUB_CACHE=/data/project/zjx/cache/huggingface/hub
export HF_XET_CACHE=/data/project/zjx/cache/huggingface/xet
export HF_ASSETS_CACHE=/data/project/zjx/cache/huggingface/assets
export TORCH_HOME=/data/project/zjx/cache/torch
export XDG_CACHE_HOME=/data/project/zjx/cache
export PIP_CACHE_DIR=/data/project/zjx/cache/pip
export MS_ASSET_DIR=/data/project/zjx/assets/maniskill
export LIBERO_CONFIG_PATH=/data/project/zjx/assets/libero/config
export MUJOCO_GL=egl
export CUDA_VISIBLE_DEVICES=0
```

如果需要 Hugging Face 认证，临时设置：

```bash
export HF_TOKEN="<临时填写你的 HF token>"
```

下载或认证完成后清理：

```bash
unset HF_TOKEN
```

本文档不保存真实 token。

## 5. 验证结果

### 5.1 LeRobot / LIBERO import 与 CUDA

已验证：

```text
import lerobot ok
import libero ok
torch.cuda.is_available() == True
```

LIBERO runtime path：

```text
config assets:  /data/project/zjx/assets/libero/assets
runtime assets: /home/ubuntu/anaconda3/envs/evaltriage-lr/lib/python3.12/site-packages/libero/libero/assets
resolved:       /data/project/zjx/assets/libero/assets
```

### 5.2 LIBERO environment reset smoke

已验证：

```text
suite: libero_goal
task_ids: [0]
obs_type: pixels_agent_pos
observation size: 128 x 128
reset: ok
pixels: image, image2
```

说明：这个 smoke 验证了 LIBERO assets、bddl files、init states、MuJoCo EGL 渲染路径可以贯通。

### 5.3 Full lerobot-eval policy smoke

已成功运行 1 episode 的 `lerobot-eval` smoke：

```text
/data/project/zjx/runs/evaltriage/smoke_lerobot_eval_gpu0_20260627_004843
```

关键设置：

```text
CUDA_VISIBLE_DEVICES=0
policy.compile_model=false
policy.gradient_checkpointing=false
eval.use_async_envs=false
env.task=libero_goal
env.task_ids=[0]
eval.n_episodes=1
```

验证结果：

```text
exit_code: 0
eval_info.json: exists
logs.txt: contains "End of eval"
model load: All keys loaded successfully
overall.avg_sum_reward: 1.0
overall.avg_max_reward: 1.0
overall.pc_success: 100.0
overall.n_episodes: 1
overall.eval_s: 9.702047348022461
video: /data/project/zjx/runs/evaltriage/smoke_lerobot_eval_gpu0_20260627_004843/videos/libero_goal_0/eval_episode_0.mp4
```

说明：

- 之前未完成的 smoke 是 `/data/project/zjx/runs/evaltriage/smoke_libero_assets_20260627_000043/logs.txt`，停在 `Making policy` 后终止。
- 当前成功 smoke 通过固定 GPU0、关闭 `torch.compile`、关闭 gradient checkpointing 和使用同步 env 解决。

### 5.4 ManiSkill smoke

已验证：

```text
PickCube-v1          gym.make + reset ok
StackCube-v1         gym.make + reset ok
PegInsertionSide-v1  gym.make + reset ok
PushCube-v1          gym.make + reset ok
```

## 6. 当前资源是否满足实验计划

根据 `EvalTriage_experiment_plan.md`：

- LeRobot + LIBERO primary policy：满足。
- LIBERO suites `libero_spatial`、`libero_object`、`libero_goal`、`libero_10` 的 runtime assets：满足。
- ManiSkill tasks `PickCube`、`StackCube`、`PegInsertion`、`PushCube`：满足。
- `lerobot-eval` 1 episode policy smoke：满足。
- dataset / data-format fault 核心数据集：满足，已下载 `lerobot/libero_10_image`。
- simulator/runtime drift 对照环境：满足，已创建 `evaltriage-lr-mujoco37`。
- `pi0_libero_base`：未下载，且核心实验不需要。
- 完整 `HuggingFaceVLA/libero`：未下载，当前核心实验不需要。
- 其他 benchmark external-validity 资源：未下载，当前核心实验不需要。

如果后续将 external validity 扩展到其他 policy 或 benchmark，再单独补充对应 checkpoint、assets 或 Docker / conda 环境。

## 7. 重要注意事项

- 运行 LIBERO 相关 Python 时必须设置 `LIBERO_CONFIG_PATH=/data/project/zjx/assets/libero/config`，否则 `libero` 可能尝试读取或创建 `~/.libero/config.yaml`。
- 当前 `evaltriage-lr` 环境内的 LIBERO assets symlink 是必要修复，不要删除。
- 如果重建 `evaltriage-lr` 环境，需要重新建立该 symlink，或 patch `hf-libero` 的 `get_assets_path()` 逻辑。
- 不要把 HF token 写入 markdown、shell 启动文件或 git。
- 当前 GPU 0 基本空闲，GPU 1 有其他用户进程占用；正式评测前应显式设置 `CUDA_VISIBLE_DEVICES=0`。
- `lerobot-eval` 跑 PI0 时建议显式设置 `--policy.compile_model=false` 和 `--eval.use_async_envs=false`，避免 smoke 阶段卡在 policy 初始化或异步环境调试上。
- 真实 HF token 只应作为临时环境变量使用；本文档只保留占位符。

## 8. 已生成 inventory 文件

```text
/data/project/zjx/logs/resource_inventory_20260626_234610.txt
/data/project/zjx/logs/resource_inventory_final_20260626_234714.txt
/data/project/zjx/logs/resource_inventory_complete_20260627_000604.txt
```

其中 `resource_inventory_complete_20260627_000604.txt` 是补齐 LIBERO assets 后的最新完整清单。

本 markdown 是 2026-06-27 01:03 CST 后的当前状态摘要；后续如需固定机器可复现实验包，建议再生成新的 `/data/project/zjx/logs/resource_inventory_*.txt` 快照。
