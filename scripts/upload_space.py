#!/usr/bin/env python3
"""Upload releases/soro-kev-space to Hugging Face Spaces."""

import os
import sys
from huggingface_hub import HfApi

TOKEN = os.environ.get("HF_TOKEN")
SPACE_ID = sys.argv[1] if len(sys.argv) > 1 else "nisaralll/soro-kev-router"

def upload():
    api = HfApi(token=TOKEN)
    print(f"Uploading releases/soro-kev-space to {SPACE_ID}...")
    api.upload_folder(
        folder_path="releases/soro-kev-space",
        repo_id=SPACE_ID,
        repo_type="space",
    )
    print(f"Successfully uploaded to https://huggingface.co/spaces/{SPACE_ID}")

if __name__ == "__main__":
    upload()
