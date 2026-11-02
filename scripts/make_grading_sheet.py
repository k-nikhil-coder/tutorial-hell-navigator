"""
scripts/make_grading_sheet.py

Module and CLI wrapper to generate a blind grading sheet from evaluation reports.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.make_grading_sheet import (
    create_grading_sheet,
    format_action_plan_for_sheet,
    main,
)

if __name__ == "__main__":
    main()
