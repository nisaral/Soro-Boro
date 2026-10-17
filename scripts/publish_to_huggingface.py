"""Upload the staged releases, or check that the required files exist.

    python scripts/publish_to_huggingface.py --dry-run
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"
BUNDLES = {
    "soro-kev-4b": "model",
    "soro-kev-0.8b": "model",
    "soro-universal-tool-harness": "dataset",
}
REQUIRED = {
    "soro-kev-4b": ["head.pt", "adapter_model.safetensors", "adapter_config.json", "config.json", "temperature.json", "README.md"],
    "soro-kev-0.8b": ["head.pt", "adapter_model.safetensors", "adapter_config.json", "config.json", "temperature.json", "README.md"],
    "soro-universal-tool-harness": ["train.jsonl", "val_zeroshot.jsonl", "val_external_human.jsonl", "README.md"],
}


def check(folder: Path, names: list[str]) -> list[str]:
    missing = []
    for name in names:
        path = folder / name
        if not path.is_file() or path.stat().st_size <= 0:
            missing.append(name)
    return missing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hf-username", default="nisaralll")
    parser.add_argument("--token", default=os.environ.get("HF_TOKEN"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    failures = []
    for name, kind in BUNDLES.items():
        folder = RELEASES / name
        missing = check(folder, REQUIRED[name])
        repo = f"{args.hf_username}/{name}"
        if missing:
            failures.append(f"{repo}: missing or empty {missing}")
            print(f"FAIL {repo} ({kind}) {missing}")
        else:
            print(f"OK   {repo} ({kind}) {folder}")
    if failures:
        raise SystemExit("\n".join(failures))
    if args.dry_run:
        print("dry-run passed")
        return
    from huggingface_hub import HfApi
    api = HfApi(token=args.token)
    for name, kind in BUNDLES.items():
        repo = f"{args.hf_username}/{name}"
        api.create_repo(repo, repo_type=kind, exist_ok=True)
        api.upload_folder(folder_path=str(RELEASES / name), repo_id=repo, repo_type=kind)
        print("uploaded", repo)


if __name__ == "__main__":
    main()
