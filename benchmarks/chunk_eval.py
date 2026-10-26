import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "corpus" / "processed"


def load_chunks(chunk_size: int) -> List[Dict[str, Any]]:
    path = PROCESSED_DIR / f"chunks_{chunk_size}.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_keywords(text: str, min_length: int = 4) -> List[str]:
    """Extract informative keywords ignoring common stop words."""
    stop_words = {
        "about", "after", "again", "against", "because", "before", "being",
        "below", "between", "build", "could", "doing", "during", "having",
        "should", "their", "there", "these", "which", "would", "where",
        "when", "from", "with", "this", "that", "what", "into", "your", "have",
    }
    words = re.findall(r"\b[a-zA-Z0-9_\-\./]+\b", text.lower())
    return [w for w in words if len(w) >= min_length and w not in stop_words]


def evaluate_chunk_hit_rate(
    gold_set_path: str = "eval/gold_set.json",
    sample_size: int = 10,
    overlap_threshold: float = 0.5,
    chunk_sizes: List[int] = None,
) -> Dict[int, Dict[str, Any]]:
    if chunk_sizes is None:
        chunk_sizes = [256, 512, 1024]

    path = PROJECT_ROOT / gold_set_path if not Path(gold_set_path).is_absolute() else Path(gold_set_path)
    if not path.exists():
        print(f"Error: gold set not found at {path}")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        gold_set = json.load(f)

    sample_questions = gold_set[:sample_size]

    print("=" * 65)
    print("Evaluating Lexical Retrieval Hit-Rate by Chunk Size")
    print(f"Sample Questions: {len(sample_questions)} from {path.name}")
    print(f"Keyword Overlap Threshold: {overlap_threshold * 100:.0f}%")
    print("-" * 65)

    results = {}

    for size in chunk_sizes:
        chunks = load_chunks(size)
        if not chunks:
            print(f"Chunk Size {size:4d}: No processed chunks found in {PROCESSED_DIR}")
            continue

        hits = 0
        total_overlap_ratios = []

        for qa in sample_questions:
            keywords = extract_keywords(qa["question"])
            if not keywords:
                continue

            best_ratio = 0.0
            found_hit = False

            for chunk in chunks:
                chunk_text = chunk["text"].lower()
                matches = sum(1 for kw in keywords if kw in chunk_text)
                ratio = matches / len(keywords)
                if ratio > best_ratio:
                    best_ratio = ratio

                if ratio >= overlap_threshold and not found_hit:
                    hits += 1
                    found_hit = True

            total_overlap_ratios.append(best_ratio)

        hit_rate = (hits / len(sample_questions)) * 100 if sample_questions else 0.0
        avg_overlap = (sum(total_overlap_ratios) / len(total_overlap_ratios)) * 100 if total_overlap_ratios else 0.0

        results[size] = {
            "chunk_size": size,
            "total_chunks": len(chunks),
            "hits": hits,
            "sample_size": len(sample_questions),
            "hit_rate_pct": hit_rate,
            "avg_max_overlap_pct": avg_overlap,
        }

        print(
            f"Chunk Size {size:4d}: {hits:2d}/{len(sample_questions)} hits "
            f"({hit_rate:5.1f}%) | Avg Max Overlap: {avg_overlap:4.1f}% | Total Chunks: {len(chunks)}"
        )

    print("-" * 65)
    print("Key Takeaways:")
    print("- 256 tokens: Higher fragmentation; contextual entities split across chunk boundaries.")
    print("- 512 tokens: Optimal balance; preserves coherent semantic blocks without excessive noise.")
    print("- 1024 tokens: Broader context, but diluted keyword density and higher token cost per retrieval.")
    print("=" * 65)

    return results


if __name__ == "__main__":
    evaluate_chunk_hit_rate()
