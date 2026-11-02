"""
eval/spans_to_chunks.py

Module and CLI script to map answer spans to chunk IDs for any chunk size.
"""

from scripts.spans_to_chunks import (
    get_chunks_for_size,
    find_chunks_covering_span,
    map_spans_to_chunk_ids,
    main,
)

if __name__ == "__main__":
    main()
