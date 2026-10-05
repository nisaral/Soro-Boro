"""Download key agent submissions with rate-limit friendly concurrency."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

REPO_ID = "harborframework/terminal-bench-2-leaderboard"
LOCAL_DIR = Path("data/tb2_leaderboard")

KEY_SUBMISSIONS = [
    # GPT-5.3-Codex
    "Droid__GPT-5.3-Codex",
    "OpenSage__GPT-5.3-Codex",
    "Mux__GPT-5.3-Codex",
    "Terminus2__GPT-5.3-Codex",
    # Gemini 3.1 Pro
    "Forge__Gemini-3.1-Pro-Preview",
    "Judy__Gemini-3.1-Pro-Preview",
    "Gemini_CLI__Gemini-3.1-Pro-Preview",
    "Terminus-KIRA__Gemini-3.1-Pro-Preview",
    # Claude Opus 4.6
    "Droid__Claude-Opus-4.6",
    "Capy__Claude-Opus-4.6",
    "Terminus2__Claude-Opus-4.6",
]


def download_file(rf: str):
    rel_parts = Path(rf).parts[3:]
    local_dest = LOCAL_DIR.joinpath(*rel_parts)
    if not local_dest.exists() or local_dest.stat().st_size == 0:
        p = hf_hub_download(REPO_ID, rf, repo_type="dataset")
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        local_dest.write_bytes(Path(p).read_bytes())
    return str(local_dest)


def main():
    api = HfApi()
    for sub in KEY_SUBMISSIONS:
        sub_dir = LOCAL_DIR / sub
        existing_results = [r for r in sub_dir.glob("**/result.json") if len(r.relative_to(sub_dir).parts) > 2]
        if len(existing_results) >= 440:
            print(f"Skipping {sub}: already has {len(existing_results)} per-task results.", flush=True)
            continue

        print(f"Processing {sub} (currently {len(existing_results)} files)...", flush=True)
        sub_remote = f"submissions/terminal-bench/2.0/{sub}"
        try:
            items = list(api.list_repo_tree(REPO_ID, path_in_repo=sub_remote, repo_type="dataset", recursive=True))
            rfiles = [f.path for f in items if f.path.endswith("result.json") or f.path.endswith("metadata.yaml")]
            print(f"  Found {len(rfiles)} files. Downloading...", flush=True)

            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(download_file, rf) for rf in rfiles]
                done = 0
                errors = 0
                for fut in as_completed(futures):
                    try:
                        fut.result()
                        done += 1
                    except Exception as e:
                        errors += 1
                        time.sleep(0.5)

            current = len([r for r in sub_dir.glob("**/result.json") if len(r.relative_to(sub_dir).parts) > 2])
            print(f"  Done {sub}: {current} files ready (errors: {errors}).", flush=True)
            time.sleep(1.0)
        except Exception as e:
            print(f"  Failed {sub}: {e}", flush=True)


if __name__ == "__main__":
    main()
