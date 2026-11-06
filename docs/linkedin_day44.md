# Day 44 LinkedIn Post

Day 44 of my 100-Day AI Sprint.

My eval used to report a "100% pass rate." It only checked format, so it said nothing about whether the advice was right. Today I tried to measure correctness.

What I did:
• Graded 50 question/answer pairs by hand on four yes/no checks: faithful to the retrieved docs, citations point to real chunks, code free of known bad patterns, follows the rules (including refusing out-of-scope questions).
• Built a judge that scores the same pairs and compared it to my grades.

The result:
• First run: 84% agreement, kappa 0.63.
• I then changed the judge's rules and it hit 100%. That number is worthless: I tuned it on the same 50 pairs I scored it on.
• Of the 16 FAILs, 0 were real model outputs and 16 were bad answers I wrote to test the judge.

What it can't do: it doesn't run any commands. It catches patterns I already know about (deprecated imports, f-string SQL, CORS wildcard with credentials). It can't tell me whether a command actually works.

Tomorrow: 30 new pairs, graded blind before I run the judge. I freeze the judge, run it once, and that's the number I trust. Thanks to the commenter on Day 43 who told me to grade first.

How do you check an LLM judge without fooling yourself?
