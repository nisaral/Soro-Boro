"""System-One Soro-Kev Decision Model Training Loop.

Trains dual linear pointer projection heads + LoRA adapter on Qwen/Qwen2.5-0.5B (or Qwen3-0.6B)
using Reinforcement Learning from Contrastive Distillation (RLCD) with Permutation Invariance,
Brier Proper Scoring calibration, and periodic Split Conformal Validation.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from soro.routing.conformal import conformal_quantile, _wilson
from soro.routing.kev_model import (
    MockCausalBackbone,
    SoroKevModel,
    save_soro_kev_checkpoint,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT_DIR / "data" / "soro_kev_dataset"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "runs" / "soro_kev_run"


class RLCDLoss(nn.Module):
    """Reinforcement Learning from Contrastive Distillation with Brier + JSD Invariance."""

    def __init__(self, brier_lambda: float = 0.25, jsd_lambda: float = 0.30):
        super().__init__()
        self.brier_lambda = brier_lambda
        self.jsd_lambda = jsd_lambda

    def forward(
        self,
        route_logits: torch.Tensor,
        route_gold_idx: int,
        perm_logits: torch.Tensor,
        perm_to_route_perm: list[int],
        aux_losses: list[torch.Tensor] | None = None,
    ) -> tuple[torch.Tensor, dict[str, float]]:
        # 1. Cross-Entropy Loss on tool_route
        p_route = F.softmax(route_logits, dim=-1)
        ce_loss = -torch.log(torch.clamp(p_route[route_gold_idx], min=1e-9))

        # Auxiliary question losses (arg_mapping, missing_required, is_mutation)
        if aux_losses:
            for l_aux in aux_losses:
                ce_loss = ce_loss + l_aux

        # 2. Brier Proper Scoring Penalty (penalizes uncalibrated overconfidence)
        num_options = route_logits.shape[-1]
        gold_one_hot = torch.zeros(num_options, device=route_logits.device)
        gold_one_hot[route_gold_idx] = 1.0
        brier_loss = torch.mean((p_route - gold_one_hot) ** 2)

        # 3. Permutation-Invariance JSD Loss (Jensen-Shannon Divergence)
        p_perm_aligned = F.softmax(perm_logits, dim=-1)[perm_to_route_perm]

        p_safe = torch.clamp(p_route, min=1e-9)
        q_safe = torch.clamp(p_perm_aligned, min=1e-9)
        m = 0.5 * (p_safe + q_safe)
        log_m = torch.log(m)
        kl1 = torch.sum(p_safe * (torch.log(p_safe) - log_m))
        kl2 = torch.sum(q_safe * (torch.log(q_safe) - log_m))
        jsd_loss = torch.clamp(0.5 * (kl1 + kl2), min=0.0)

        total_loss = ce_loss + self.brier_lambda * brier_loss + self.jsd_lambda * jsd_loss
        is_hit = (torch.argmax(route_logits).item() == route_gold_idx)

        metrics = {
            "loss_total": float(total_loss.item()),
            "loss_ce": float(ce_loss.item()),
            "loss_brier": float(brier_loss.item()),
            "loss_jsd": float(jsd_loss.item()),
            "prob_gold": float(p_route[route_gold_idx].item()),
            "hit": 1.0 if is_hit else 0.0,
        }
        return total_loss, metrics


def run_split_conformal_val(
    model: SoroKevModel,
    val_records: list[dict[str, Any]],
    cal_size: int = 300,
    alpha: float = 0.10,
) -> dict[str, Any]:
    """Run split conformal validation on held-out zero-shot records."""
    model.eval()
    cal_records = val_records[:cal_size]
    test_records = val_records[cal_size:]

    # Calibration Phase: compute non-conformity scores
    nonconf_scores: list[float] = []
    with torch.no_grad():
        for r in cal_records:
            state = r["state"]
            q_dict = r["questions"]
            q_route = q_dict["tool_route"]
            gold = q_route["label"]
            logits, keys = model.score_choice_sequence(
                state, q_route.get("instructions", ""), q_route["criteria"]
            )
            probs = F.softmax(logits, dim=-1).cpu().tolist()
            p_gold = probs[keys.index(gold)] if gold in keys else 0.0
            nonconf_scores.append(1.0 - p_gold)

    q_hat = conformal_quantile(np.array(nonconf_scores, dtype=np.float64), alpha=alpha)
    threshold = max(0.0, 1.0 - q_hat)

    # Test Phase: evaluate empirical coverage and set size
    correct = 0
    covered = 0
    set_sizes: list[int] = []

    with torch.no_grad():
        for r in test_records:
            state = r["state"]
            q_dict = r["questions"]
            q_route = q_dict["tool_route"]
            gold = q_route["label"]
            logits, keys = model.score_choice_sequence(
                state, q_route.get("instructions", ""), q_route["criteria"]
            )
            probs = F.softmax(logits, dim=-1).cpu().tolist()
            pred_key = keys[int(torch.argmax(logits).item())]
            if pred_key == gold:
                correct += 1

            p_set = [keys[i] for i, p in enumerate(probs) if p >= threshold]
            sz = len(p_set)
            set_sizes.append(sz)
            if gold in p_set:
                covered += 1

    n_test = len(test_records)
    lo, hi = _wilson(covered, n_test)
    singletons = sum(1 for s in set_sizes if s == 1)

    model.train()
    return {
        "val_route_acc": correct / n_test if n_test else 0.0,
        "empirical_coverage": covered / n_test if n_test else 0.0,
        "wilson_ci": [lo, hi],
        "mean_set_size": float(np.mean(set_sizes)) if set_sizes else 0.0,
        "singleton_rate": singletons / n_test if n_test else 0.0,
        "q_hat": float(q_hat),
        "threshold": float(threshold),
    }


def get_cosine_lr(step: int, total_steps: int, warmup_steps: int, lr: float, min_lr: float = 1e-6) -> float:
    if step < warmup_steps:
        return lr * float(step + 1) / float(max(1, warmup_steps))
    progress = float(step - warmup_steps) / float(max(1, total_steps - warmup_steps))
    return min_lr + 0.5 * (lr - min_lr) * (1.0 + math.cos(math.pi * progress))


def main():
    parser = argparse.ArgumentParser(description="Train Soro-Kev System-One Decision Model")
    parser.add_argument("--profile", type=str, default="cpu_smoke", choices=["cpu_smoke", "kaggle_t4", "a6000"])
    parser.add_argument("--data-dir", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-0.5B")
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--eval-every", type=int, default=500)
    args = parser.parse_args()

    print(f"=== Initializing Soro-Kev Training (Profile: {args.profile} | Model: {args.base_model}) ===")

    out_path = Path(args.output_dir)
    data_path = Path(args.data_dir)
    train_file = data_path / "train.jsonl"
    val_file = data_path / "val_zeroshot.jsonl"

    if not train_file.exists():
        raise FileNotFoundError(f"Dataset not found at {train_file}. Run build_universal_dataset.py first.")

    train_records = []
    with train_file.open(encoding="utf-8") as f:
        for line in f:
            train_records.append(json.loads(line))

    val_records = []
    if val_file.exists():
        with val_file.open(encoding="utf-8") as f:
            for line in f:
                val_records.append(json.loads(line))

    is_smoke = (args.profile == "cpu_smoke")
    if is_smoke:
        train_records = train_records[:20]
        val_records = val_records[:40]
        total_steps = 2
    else:
        total_steps = len(train_records) * args.epochs

    device = "cuda" if torch.cuda.is_available() and not is_smoke else "cpu"
    print(f"Loaded {len(train_records)} train records | {len(val_records)} zero-shot val records | Device: {device}")

    model = SoroKevModel(model_name=args.base_model, use_mock=is_smoke)
    model.to(device)
    loss_fn = RLCDLoss(brier_lambda=0.25, jsd_lambda=0.30)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)

    warmup_steps = 1 if is_smoke else 100
    best_val_score = -1.0
    best_q_hat = 0.90
    step_idx = 0
    t0 = time.time()

    running_loss = 0.0
    running_ce = 0.0
    running_brier = 0.0
    running_jsd = 0.0
    running_hits = 0.0
    running_gold_p = 0.0

    print(f"Starting training loop ({total_steps} steps | Profile: {args.profile})...")

    optimizer.zero_grad()

    while step_idx < total_steps:
        r = train_records[step_idx % len(train_records)]
        state = r["state"]
        q_dict = r["questions"]

        # Current learning rate schedule
        cur_lr = get_cosine_lr(step_idx, total_steps, warmup_steps, args.lr)
        for pg in optimizer.param_groups:
            pg["lr"] = cur_lr

        # Forward pass on tool_route and permuted tool_route
        q_route = q_dict["tool_route"]
        q_perm = q_dict["tool_route_perm"]

        route_logits, route_keys = model.score_choice_sequence(
            state, q_route.get("instructions", ""), q_route["criteria"]
        )
        perm_logits, perm_keys = model.score_choice_sequence(
            state, q_perm.get("instructions", ""), q_perm["criteria"]
        )

        gold_label = q_route["label"]
        gold_idx = route_keys.index(gold_label) if gold_label in route_keys else 0
        perm_to_route = [perm_keys.index(k) for k in route_keys]

        # Auxiliary branches
        aux_losses = []
        if "arg_mapping" in q_dict:
            q_arg = q_dict["arg_mapping"]
            arg_logits, arg_keys = model.score_choice_sequence(
                state, q_arg.get("instructions", ""), q_arg["criteria"]
            )
            arg_gold = q_arg["label"]
            arg_gold_idx = arg_keys.index(arg_gold) if arg_gold in arg_keys else 0
            p_arg = F.softmax(arg_logits, dim=-1)
            aux_losses.append(-torch.log(torch.clamp(p_arg[arg_gold_idx], min=1e-9)))

        if "missing_required" in q_dict:
            q_miss = q_dict["missing_required"]
            miss_logits = model.score_binary(state)
            miss_gold_idx = 1 if q_miss["label"] == "yes" else 0
            p_miss = F.softmax(miss_logits, dim=-1)
            aux_losses.append(-torch.log(torch.clamp(p_miss[miss_gold_idx], min=1e-9)))

        if "is_mutation" in q_dict:
            q_mut = q_dict["is_mutation"]
            mut_logits = model.score_binary(state)
            mut_gold_idx = 1 if q_mut["label"] == "yes" else 0
            p_mut = F.softmax(mut_logits, dim=-1)
            aux_losses.append(-torch.log(torch.clamp(p_mut[mut_gold_idx], min=1e-9)))

        # Composite RLCD loss
        loss, m = loss_fn(route_logits, gold_idx, perm_logits, perm_to_route, aux_losses=aux_losses)
        scaled_loss = loss / args.grad_accum
        scaled_loss.backward()

        running_loss += m["loss_total"]
        running_ce += m["loss_ce"]
        running_brier += m["loss_brier"]
        running_jsd += m["loss_jsd"]
        running_hits += m["hit"]
        running_gold_p += m["prob_gold"]

        grad_norm = 0.0
        if (step_idx + 1) % args.grad_accum == 0 or is_smoke:
            grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0).item())
            optimizer.step()
            optimizer.zero_grad()

        step_idx += 1

        # Periodic logging every 50 steps (or on smoke steps)
        if step_idx % 50 == 0 or is_smoke:
            n_sub = 50 if step_idx >= 50 else step_idx
            speed = n_sub / max(time.time() - t0, 0.001)
            print(
                f"Step {step_idx:05d}/{total_steps} | "
                f"Loss: {running_loss / n_sub:.4f} (CE: {running_ce / n_sub:.4f}, Brier: {running_brier / n_sub:.4f}, JSD: {running_jsd / n_sub:.6f}) | "
                f"Train Route Acc: {running_hits / n_sub * 100:.1f}% | "
                f"Gold Prob: {running_gold_p / n_sub:.3f} | "
                f"Grad Norm: {grad_norm:.2f} | "
                f"Speed: {speed:.1f} it/s"
            )
            running_loss = running_ce = running_brier = running_jsd = running_hits = running_gold_p = 0.0
            t0 = time.time()

        # Periodic split conformal validation
        if (step_idx % args.eval_every == 0 or step_idx == total_steps) and len(val_records) >= 10:
            print(f"--- Running Split Conformal Validation (Step {step_idx}) ---")
            val_res = run_split_conformal_val(model, val_records, cal_size=min(300, len(val_records) // 2))
            print(
                f"Zero-Shot Route Acc: {val_res['val_route_acc'] * 100:.2f}% | "
                f"Coverage: {val_res['empirical_coverage'] * 100:.2f}% (Wilson: [{val_res['wilson_ci'][0]*100:.1f}%, {val_res['wilson_ci'][1]*100:.1f}%]) | "
                f"Mean |S|: {val_res['mean_set_size']:.2f} | "
                f"Singleton Rate: {val_res['singleton_rate'] * 100:.2f}% | "
                f"q_hat: {val_res['q_hat']:.4f}"
            )
            score = val_res["val_route_acc"] + val_res["singleton_rate"]
            if score > best_val_score:
                best_val_score = score
                best_q_hat = val_res["q_hat"]
                print(f"--> New best model found! Saving checkpoint to {out_path}...")
                save_soro_kev_checkpoint(model, out_path, q_hat=best_q_hat)

    print(f"=== Training Complete! Saving final checkpoint to {out_path} ===")
    save_soro_kev_checkpoint(model, out_path, q_hat=best_q_hat)
    print("Checkpoint saved successfully: head.pt + config.json + temperature.json.")


if __name__ == "__main__":
    main()
