"""Runtime overlays for real LeRobot eval runs.

This module intentionally delegates rollout, metrics, videos, and eval_info.json
to the upstream ``lerobot-eval`` implementation. The overlay only changes the
requested runtime preprocessing before LeRobot constructs the env processors.
"""

from __future__ import annotations

import argparse
import json
import sys

import torch


def _split_overlay_args(argv: list[str]) -> tuple[list[str], list[str]]:
    if "--" not in argv:
        raise SystemExit("overlay worker requires '--' before lerobot-eval arguments")
    index = argv.index("--")
    return argv[:index], argv[index + 1 :]


def _patch_libero_image_flip(axis: str) -> None:
    from lerobot.processor.env_processor import LiberoProcessorStep
    from lerobot.utils.constants import OBS_IMAGES

    dims_by_axis = {
        "horizontal": [3],
        "vertical": [2],
        "both": [2, 3],
    }
    dims = dims_by_axis[axis]
    original = LiberoProcessorStep._process_observation

    def patched(self, observation):
        processed = original(self, observation)
        for key, value in list(processed.items()):
            if key.startswith(f"{OBS_IMAGES}.") and isinstance(value, torch.Tensor):
                processed[key] = torch.flip(value, dims=dims)
        return processed

    LiberoProcessorStep._process_observation = patched


def _patch_libero_image_blackout(value: float) -> None:
    from lerobot.processor.env_processor import LiberoProcessorStep
    from lerobot.utils.constants import OBS_IMAGES

    original = LiberoProcessorStep._process_observation

    def patched(self, observation):
        processed = original(self, observation)
        for key, tensor in list(processed.items()):
            if key.startswith(f"{OBS_IMAGES}.") and isinstance(tensor, torch.Tensor):
                processed[key] = torch.full_like(tensor, value)
        return processed

    LiberoProcessorStep._process_observation = patched


def _matches_state_key(key: str, targets: list[str]) -> bool:
    for target in targets:
        if key == target or key.startswith(f"{target}."):
            return True
    return False


def _patch_libero_state_blackout(keys: list[str], value: float) -> None:
    from lerobot.processor.env_processor import LiberoProcessorStep

    original = LiberoProcessorStep._process_observation

    def patched(self, observation):
        processed = original(self, observation)
        for key, tensor in list(processed.items()):
            if _matches_state_key(key, keys) and isinstance(tensor, torch.Tensor):
                processed[key] = torch.full_like(tensor, value)
        return processed

    LiberoProcessorStep._process_observation = patched


def _patch_libero_state_noise(keys: list[str], std: float) -> None:
    from lerobot.processor.env_processor import LiberoProcessorStep

    original = LiberoProcessorStep._process_observation

    def patched(self, observation):
        processed = original(self, observation)
        for key, tensor in list(processed.items()):
            if _matches_state_key(key, keys) and isinstance(tensor, torch.Tensor):
                processed[key] = tensor + torch.randn_like(tensor) * std
        return processed

    LiberoProcessorStep._process_observation = patched


def _patch_libero_state_key_drop(keys: list[str]) -> None:
    from lerobot.processor.env_processor import LiberoProcessorStep

    original = LiberoProcessorStep._process_observation

    def patched(self, observation):
        processed = original(self, observation)
        for key in list(processed):
            if _matches_state_key(key, keys):
                del processed[key]
        return processed

    LiberoProcessorStep._process_observation = patched


def _parse_keys(raw: str | None) -> list[str]:
    if not raw:
        raise SystemExit("state observation overlays require --keys")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = [item.strip() for item in raw.split(",") if item.strip()]
    if not isinstance(parsed, list) or not parsed or not all(isinstance(item, str) and item for item in parsed):
        raise SystemExit("--keys must be a non-empty JSON or comma-separated list of strings")
    return parsed


def _parse_permutation(raw: str | None) -> list[int]:
    if not raw:
        raise SystemExit("action.reorder_dimensions requires --permutation")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        try:
            parsed = [int(item.strip()) for item in raw.split(",") if item.strip()]
        except ValueError as exc:
            raise SystemExit("--permutation must be a JSON or comma-separated list of integers") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, int) for item in parsed):
        raise SystemExit("--permutation must be a JSON or comma-separated list of integers")
    return parsed


def _patch_action_drop_postprocessor() -> None:
    from lerobot.processor.pipeline import DataProcessorPipeline

    original = DataProcessorPipeline.__call__

    def patched(self, data):
        if getattr(self, "name", None) == "policy_postprocessor":
            return data
        return original(self, data)

    DataProcessorPipeline.__call__ = patched


def _patch_action_reorder_dimensions(permutation: list[int]) -> None:
    from lerobot.processor.pipeline import DataProcessorPipeline

    original = DataProcessorPipeline.__call__

    def patched(self, data):
        output = original(self, data)
        if getattr(self, "name", None) == "policy_postprocessor" and isinstance(output, torch.Tensor):
            if output.ndim < 2 or output.shape[-1] != len(permutation):
                raise RuntimeError(
                    f"action.reorder_dimensions expected action_dim={len(permutation)}, got shape={tuple(output.shape)}"
                )
            index = torch.tensor(permutation, device=output.device)
            return output.index_select(-1, index)
        return output

    DataProcessorPipeline.__call__ = patched


def _patch_semantic_bug_flag(flag: str) -> None:
    from lerobot.processor.pipeline import DataProcessorPipeline

    original = DataProcessorPipeline.__call__
    frozen: dict[str, torch.Tensor | None] = {"action": None}

    def patched(self, data):
        output = original(self, data)
        if getattr(self, "name", None) != "policy_postprocessor" or not isinstance(output, torch.Tensor):
            return output
        if output.shape[-1] < 1:
            raise RuntimeError(f"code.semantic_bug_flag expected a non-empty action tensor, got {tuple(output.shape)}")
        if flag == "zero_action_output":
            return torch.zeros_like(output)
        if flag == "freeze_first_action":
            if frozen["action"] is None:
                frozen["action"] = output.detach().clone()
            action = frozen["action"].to(device=output.device, dtype=output.dtype)
            if action.shape != output.shape:
                raise RuntimeError(
                    "code.semantic_bug_flag freeze_first_action saw changing action shapes: "
                    f"first={tuple(action.shape)} current={tuple(output.shape)}"
                )
            return action.clone()
        if flag == "translation_sign_flip":
            if output.shape[-1] < 3:
                raise RuntimeError(
                    f"translation_sign_flip requires at least 3 action dims, got {tuple(output.shape)}"
                )
            action = output.clone()
            action[..., :3] = -action[..., :3]
            return action
        if flag == "gripper_sign_flip":
            action = output.clone()
            action[..., -1] = -action[..., -1]
            return action
        raise RuntimeError(f"unsupported semantic bug flag: {flag}")

    DataProcessorPipeline.__call__ = patched


def main() -> None:
    overlay_args, lerobot_args = _split_overlay_args(sys.argv[1:])
    if lerobot_args and lerobot_args[0] == "lerobot-eval":
        lerobot_args = lerobot_args[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--overlay",
        required=True,
        choices=[
            "observation.image_flip",
            "observation.image_blackout",
            "observation.state_blackout",
            "observation.state_noise",
            "observation.state_key_drop",
            "action.drop_postprocessor",
            "action.reorder_dimensions",
            "code.semantic_bug_flag",
        ],
    )
    parser.add_argument("--axis", choices=["horizontal", "vertical", "both"])
    parser.add_argument("--value", type=float)
    parser.add_argument("--std", type=float)
    parser.add_argument("--keys")
    parser.add_argument("--permutation")
    parser.add_argument("--semantic-bug-flag")
    args = parser.parse_args(overlay_args)

    if args.overlay == "action.drop_postprocessor":
        _patch_action_drop_postprocessor()
    elif args.overlay == "action.reorder_dimensions":
        _patch_action_reorder_dimensions(_parse_permutation(args.permutation))
    elif args.overlay == "code.semantic_bug_flag":
        if args.semantic_bug_flag is None:
            raise SystemExit("code.semantic_bug_flag requires --semantic-bug-flag")
        _patch_semantic_bug_flag(args.semantic_bug_flag)
    elif args.overlay == "observation.image_flip":
        if args.axis is None:
            raise SystemExit("observation.image_flip requires --axis")
        _patch_libero_image_flip(args.axis)
    elif args.overlay == "observation.image_blackout":
        if args.value is None:
            raise SystemExit("observation.image_blackout requires --value")
        _patch_libero_image_blackout(args.value)
    elif args.overlay == "observation.state_blackout":
        if args.value is None:
            raise SystemExit("observation.state_blackout requires --value")
        _patch_libero_state_blackout(_parse_keys(args.keys), args.value)
    elif args.overlay == "observation.state_noise":
        if args.std is None or args.std <= 0:
            raise SystemExit("observation.state_noise requires positive --std")
        _patch_libero_state_noise(_parse_keys(args.keys), args.std)
    elif args.overlay == "observation.state_key_drop":
        _patch_libero_state_key_drop(_parse_keys(args.keys))

    from lerobot.scripts.lerobot_eval import main as lerobot_main

    sys.argv = ["lerobot-eval", *lerobot_args]
    lerobot_main()


if __name__ == "__main__":
    main()
