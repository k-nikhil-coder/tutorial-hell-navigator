import os
import sys
import time
from pathlib import Path
import requests

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

OUTPUT_DIR = Path("corpus/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Map desired local filenames to their raw GitHub Markdown URLs
FRAMEWORK_DOCS = {
    "fastapi_cors.md": "https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/cors.md",
    "fastapi_background_tasks.md": "https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/background-tasks.md",
    "pydantic_models.md": "https://raw.githubusercontent.com/pydantic/pydantic/main/docs/concepts/models.md",
    "pydantic_validation.md": "https://raw.githubusercontent.com/pydantic/pydantic/main/docs/concepts/validators.md",
    "docker_compose_best_practices.md": "https://raw.githubusercontent.com/docker/docs/main/content/manuals/compose/intro/features-uses.md",
}


def download_markdown_corpus():
    print(f"📥 Downloading {len(FRAMEWORK_DOCS)} framework documents...")
    headers = {"User-Agent": "TutorialHellNavigator-CorpusFetcher/1.0"}

    for filename, url in FRAMEWORK_DOCS.items():
        print(f"Fetching {filename}...")
        try:
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                file_path = OUTPUT_DIR / filename
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                print(f"  ✅ Saved to {file_path}")
            else:
                print(f"  ❌ Failed to fetch {filename}: HTTP {response.status_code}")

            # Sleep briefly to respect server limits
            time.sleep(1)

        except Exception as e:
            print(f"  🚨 Error fetching {filename}: {str(e)}")


if __name__ == "__main__":
    download_markdown_corpus()
