# Day 45 LinkedIn Post

Day 45 of my 100-Day AI Sprint.

Yesterday my eval judge hit 100% agreement. I called that number worthless because I tuned the rules on the same 50 pairs I scored it on.

Today I ran the blind test I promised:

What I did:
• Generated 30 fresh pairs from live model outputs (none from the test set, none repeated from yesterday).
• Kept 15 untouched and injected one defect into the other 15.
• Picked defect families before running the judge, including bugs it has no rules for: CLI flag typos (`--relod`), wrong default ports (Postgres on 3306), claims contradicting the cited chunk, and missing prerequisite steps.
• Shuffled blind, graded all 30 by hand, and committed `hand_grades.json` to GitHub before running the judge.
• Froze the judge (`git tag judge-frozen-d45`) and ran it once. Zero rule edits afterward.

The result:
• Agreement collapsed from 100% to 46.7% (14 of 30).
• Cohen's kappa: -0.067 (worse than random guessing).
• Wilson 95% interval: [30.2%, 63.9%].

Why it broke:
1. False alarms on clean code (73% of untouched outputs failed): The judge checks shell command prefixes, so it flagged valid multi-line Python snippets (`from fastapi import...`) and YAML configs as "unrecognized executables." It also penalized correct out-of-scope refusals as errors.
2. Blind to novel bugs (40% missed on unmodeled defects): It caught 4/4 defects it had regex rules for (SQL injection, BaseSettings, CORS wildcard), but passed right over misspelled flags and wrong ports because it doesn't execute commands or understand semantics.

I also fixed the retrieval ceiling:
On Day 43, retrieval scored 45.2%. Root-cause analysis showed 3 source files containing 17 questions were never indexed in the 8-file build. I rebuilt the index from all 10 files (97 chunks), added an automated pytest asserting every gold span exists in the index, and re-ran the dev split: Hit@3 reached 93.5% (29/31, MRR 0.82). The test split remains sealed.

The lesson: static regexes and token overlap cannot substitute for a sandbox runner. A heuristic judge tuned on its own test cases only measures how well you memorized your own bug list.

Code, blind dataset, and calibration reports: https://github.com/k-nikhil-coder/tutorial-hell-navigator

How do you grade LLM code output when regexes fail?
