---

### 2. `flagship_spec.md` (Engineering RFC & Candidate Scoring)

```markdown
# Flagship Engineering RFC: Tutorial Hell Navigator for CS Students

**Project:** Tutorial Hell Navigator  
**Author:** Kumbham Nikhil  
**Status:** In Progress (Day 30 Foundation)  
**Target:** Phase 2 Capstone Anchor  

---

## 1. Problem Statement

Many computer science students and self-taught developers get trapped in "tutorial hell"—copying code line-by-line without understanding architectural decisions. When faced with a blank editor, unexpected Docker dependency errors, or designing a database schema, they freeze or abandon the project.

Generic AI assistants often worsen this problem by either dumping massive blocks of untested code or giving empty advice like "keep practicing" without milestone decomposition.

---

## 2. Candidate Project Scoring Matrix

| Evaluation Criteria | Candidate 1: Generic PDF Chatbot | Candidate 2: E-Commerce Support Bot | Candidate 3: Tutorial Hell Navigator (Selected) |
| :--- | :--- | :--- | :--- |
| **Reachable Real Users** | Low (Generic utility) | Low (No actual store client) | **High** (Peer CS undergraduates & active dev communities) |
| **Corpus Defensibility** | Low (Public documentation) | Medium (Fictional catalog) | **High** (Curated project blueprints, debugging failure trees, MLOps checklists) |
| **Painful Problem** | Low (Routine Q&A) | Medium (Repetitive FAQ lookup) | **High** (Blank-editor paralysis, project abandonment, lack of deployment proof) |
| **Measurable Success** | Ambiguous | Conversion rate (untestable) | **High** (80-question benchmark with explicit technical pass/fail criteria) |

---

## 3. Benchmark Architecture (`gold_set.json`)

The system is evaluated against an 80-question benchmark spanning 12 domains:
1. Full-Stack Getting Started (`GS-01` – `GS-08`)
2. Projects & Independent Building (`GS-09` – `GS-16`)
3. Debugging & Developer Tooling (`GS-17` – `GS-24`)
4. AI & ML Engineering (`GS-25` – `GS-32`)
5. GitHub Portfolio & Resumes (`GS-33` – `GS-40`)
6. Study Habits & Career Decisions (`GS-41` – `GS-50`)
7. Data Structures & Algorithms (`GS-51` – `GS-60`)
8. Competitive Programming & TLE Diagnostics (`GS-61` – `GS-65`)
9. Core CS Fundamentals: OS, DBMS & Networking (`GS-66` – `GS-72`)
10. Coding Interviews & Assessment Triage (`GS-73` – `GS-80`)

### Passing Criteria Schema
* **Expected Rubric:** Must contain exact CLI commands, file trees, Big-O stack derivations, or schema contracts.
* **Negative Constraints:** Fails immediately if it suggests copy-pasting full solutions without explanation, ignores security vulnerabilities, or gives vague generalities.

---

## 4. Planned Retrieval Pipeline (Phase 2 Milestones)