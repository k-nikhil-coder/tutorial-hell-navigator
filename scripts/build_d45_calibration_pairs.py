import json
import random
import copy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "eval" / "raw_model_responses_d45.json", "r", encoding="utf-8") as f:
    raw_data = {item["question_id"]: item for item in json.load(f)}

with open(PROJECT_ROOT / "eval" / "gold_benchmark_v2.json", "r", encoding="utf-8") as f:
    gold_map = {item["id"]: item for item in json.load(f)}

# 15 INJECTED PAIRS AND 15 UNTOUCHED PAIRS
# Selected questions:
INJECTED_CONFIG = {
    # 1. wrong_cli_flag_spelling (No judge rule)
    "GS-V2-01": {
        "family": "wrong_cli_flag_spelling",
        "has_judge_rule": False,
        "description": "Wrong CLI flag spelling '--relod' instead of '--reload' in uvicorn command.",
        "mutate": lambda resp: _inject_cli_flag(resp, "--reload", "--relod")
    },
    # 2. wrong_cli_flag_spelling (No judge rule)
    "GS-V2-16": {
        "family": "wrong_cli_flag_spelling",
        "has_judge_rule": False,
        "description": "Wrong CLI flag spelling '--detatch' instead of '--detach' in docker compose command.",
        "mutate": lambda resp: _inject_cli_flag(resp, "-d", "--detatch")
    },
    # 3. wrong_default_port (No judge rule)
    "GS-V2-25": {
        "family": "wrong_default_port",
        "has_judge_rule": False,
        "description": "States PostgreSQL listens by default on port 3306 (MySQL default) instead of 5432.",
        "mutate": lambda resp: _inject_text_replace(resp, "5432", "3306 (PostgreSQL default port)")
    },
    # 4. wrong_default_port (No judge rule)
    "GS-V2-04": {
        "family": "wrong_default_port",
        "has_judge_rule": False,
        "description": "Claims FastAPI/uvicorn runs by default on port 5000 (Flask default) instead of 8000.",
        "mutate": lambda resp: _inject_text_replace(resp, "8000", "5000")
    },
    # 5. claim_contradicts_cited_chunk (No judge rule)
    "GS-V2-02": {
        "family": "claim_contradicts_cited_chunk",
        "has_judge_rule": False,
        "description": "Contradicts cited chunk by claiming distinct ports on localhost share the same origin.",
        "mutate": lambda resp: _inject_cors_port_contradiction(resp)
    },
    # 6. claim_contradicts_cited_chunk (No judge rule)
    "GS-V2-14": {
        "family": "claim_contradicts_cited_chunk",
        "has_judge_rule": False,
        "description": "Contradicts Docker documentation by claiming Compose ports mapping syntax is CONTAINER:HOST.",
        "mutate": lambda resp: _inject_docker_ports_contradiction(resp)
    },
    # 7. real_but_irrelevant_chunk_id (No judge rule)
    "GS-V2-37": {
        "family": "real_but_irrelevant_chunk_id",
        "has_judge_rule": False,
        "description": "Cites a real but completely irrelevant chunk ID (docker_compose_best_practices_sweep384_chunk_0) for Pydantic validation.",
        "mutate": lambda resp: _inject_irrelevant_chunk(resp, "docker_compose_best_practices_sweep384_chunk_0")
    },
    # 8. real_but_irrelevant_chunk_id (No judge rule)
    "GS-V2-19": {
        "family": "real_but_irrelevant_chunk_id",
        "has_judge_rule": False,
        "description": "Cites a real but completely irrelevant chunk ID (fastapi_cors_sweep384_chunk_3) for Docker ignore files.",
        "mutate": lambda resp: _inject_irrelevant_chunk(resp, "fastapi_cors_sweep384_chunk_3")
    },
    # 9. missing_required_step (No judge rule)
    "GS-V2-28": {
        "family": "missing_required_step",
        "has_judge_rule": False,
        "description": "Missing prerequisite dependency installation step ('pip install psycopg2-binary'), plan runs broken python script immediately.",
        "mutate": lambda resp: _inject_missing_step(resp)
    },
    # 10. wrong_http_status_code (No judge rule)
    "GS-V2-36": {
        "family": "wrong_http_status_code",
        "has_judge_rule": False,
        "description": "Claims FastAPI request validation errors return HTTP 200 OK with body instead of HTTP 422.",
        "mutate": lambda resp: _inject_text_replace(resp, "422", "200 OK")
    },
    # 11. deprecated_import_basesettings (Judge has rule)
    "GS-V2-38": {
        "family": "deprecated_import_basesettings",
        "has_judge_rule": True,
        "description": "Uses deprecated Pydantic v1 import 'from pydantic import BaseSettings'.",
        "mutate": lambda resp: _inject_text_prepend(resp, "from pydantic import BaseSettings\n")
    },
    # 12. sql_injection_fstring (Judge has rule)
    "GS-V2-27": {
        "family": "sql_injection_fstring",
        "has_judge_rule": True,
        "description": "Uses vulnerable Python f-string formatting in SQL execute command.",
        "mutate": lambda resp: _inject_fstring_sql(resp)
    },
    # 13. cors_wildcard_with_credentials (Judge has rule)
    "GS-V2-05": {
        "family": "cors_wildcard_with_credentials",
        "has_judge_rule": True,
        "description": "Configures wildcard allow_origins=['*'] with allow_credentials=True.",
        "mutate": lambda resp: _inject_cors_wildcard_credentials(resp)
    },
    # 14. hallucinated_chunk_id (Judge has rule)
    "GS-V2-18": {
        "family": "hallucinated_chunk_id",
        "has_judge_rule": True,
        "description": "Cites hallucinated, non-existent chunk ID 'docker_turbo_volume_chunk_99'.",
        "mutate": lambda resp: _inject_hallucinated_chunk(resp, "docker_turbo_volume_chunk_99")
    },
    # 15. refusal_gate_leak_false_answer (Judge has rule)
    "GS-V2-48": {
        "family": "refusal_gate_leak_false_answer",
        "has_judge_rule": True,
        "description": "Out-of-scope query answered with invented ungrounded advice instead of proper refusal.",
        "mutate": lambda resp: _inject_leaked_answer_on_oos(resp)
    },
}

# Mutation helpers
def _inject_cli_flag(resp, old_flag, new_flag):
    r = copy.deepcopy(resp)
    for step in r["action_plan"]:
        if step.get("command"):
            if old_flag in step["command"]:
                step["command"] = step["command"].replace(old_flag, new_flag)
            else:
                step["command"] += f" {new_flag}"
            break
    return r

def _inject_text_replace(resp, old_txt, new_txt):
    r = copy.deepcopy(resp)
    r["summary"] = r["summary"].replace(old_txt, new_txt)
    for step in r["action_plan"]:
        if step.get("explanation"):
            step["explanation"] = step["explanation"].replace(old_txt, new_txt)
        if step.get("command"):
            step["command"] = step["command"].replace(old_txt, new_txt)
        if step.get("verification"):
            step["verification"] = step["verification"].replace(old_txt, new_txt)
    return r

def _inject_cors_port_contradiction(resp):
    r = copy.deepcopy(resp)
    contradiction = " Note that different ports on localhost share the same origin under CORS, so localhost:3000 automatically grants origin access to localhost:8080 without explicit listing."
    r["summary"] += contradiction
    if r["action_plan"]:
        r["action_plan"][0]["explanation"] += contradiction
    return r

def _inject_docker_ports_contradiction(resp):
    r = copy.deepcopy(resp)
    contradiction = " Note: In Docker Compose, the port mapping syntax is CONTAINER_PORT:HOST_PORT, so specifying 80:8000 binds container port 80 to host port 8000."
    r["summary"] += contradiction
    if r["action_plan"]:
        r["action_plan"][0]["explanation"] += contradiction
    return r

def _inject_irrelevant_chunk(resp, irrelevant_chunk_id):
    r = copy.deepcopy(resp)
    r["cited_chunk_ids"] = [irrelevant_chunk_id]
    for step in r["action_plan"]:
        step["citations"] = [irrelevant_chunk_id]
    return r

def _inject_missing_step(resp):
    r = copy.deepcopy(resp)
    # Filter out pip install step if present, or delete prerequisite
    if len(r["action_plan"]) > 1:
        r["action_plan"] = [r["action_plan"][-1]]
    r["action_plan"][0]["step_number"] = 1
    r["action_plan"][0]["command"] = "python -c 'import psycopg2; conn=psycopg2.connect(dbname=\"test\"); print(\"connected\")'"
    r["action_plan"][0]["explanation"] = "Directly run the Python psycopg2 connection script without installing psycopg2 or psycopg2-binary in your virtual environment."
    return r

def _inject_text_prepend(resp, code_line):
    r = copy.deepcopy(resp)
    if r["action_plan"]:
        cmd = r["action_plan"][0].get("command") or ""
        r["action_plan"][0]["command"] = code_line + cmd
        r["action_plan"][0]["explanation"] = f"Using {code_line.strip()} for environment configuration."
    return r

def _inject_fstring_sql(resp):
    r = copy.deepcopy(resp)
    if r["action_plan"]:
        r["action_plan"][0]["command"] = "cursor.execute(f\"SELECT * FROM users WHERE email = '{user_email}'\")"
        r["action_plan"][0]["explanation"] = "Construct the database query using direct Python f-string interpolation for the user input parameter."
    return r

def _inject_cors_wildcard_credentials(resp):
    r = copy.deepcopy(resp)
    if r["action_plan"]:
        r["action_plan"][0]["command"] = "app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True)"
        r["action_plan"][0]["explanation"] = "Permit all origins using the wildcard '*' while enabling allow_credentials=True for session cookies."
    return r

def _inject_hallucinated_chunk(resp, fake_id):
    r = copy.deepcopy(resp)
    r["cited_chunk_ids"] = [fake_id]
    if r["action_plan"]:
        r["action_plan"][0]["citations"] = [fake_id]
    return r

def _inject_leaked_answer_on_oos(resp):
    r = copy.deepcopy(resp)
    r["is_refusal"] = False
    r["refusal_reason"] = None
    r["summary"] = "Here is the step-by-step guidance to train a PyTorch diffusion model on multi-GPU clusters."
    r["action_plan"] = [{
        "step_number": 1,
        "title": "Launch Distributed Diffusion Training",
        "command": "python -m torch.distributed.run --nproc_per_node=4 train_diffusion.py --batch-size 64",
        "explanation": "Execute distributed data parallel training across 4 GPUs for the latent diffusion model.",
        "verification": "nvidia-smi",
        "citations": ["pytorch_diffusion_sweep384_chunk_0"]
    }]
    r["cited_chunk_ids"] = ["pytorch_diffusion_sweep384_chunk_0"]
    return r

def build_datasets():
    # Build the 30 pairs
    pairs_list = []
    injection_records = {}

    for qid, item in raw_data.items():
        is_injected = qid in INJECTED_CONFIG
        raw_resp = item["raw_response"]
        gold_q = gold_map[qid]

        if is_injected:
            cfg = INJECTED_CONFIG[qid]
            final_resp = cfg["mutate"](raw_resp)
            defect_family = cfg["family"]
            defect_desc = cfg["description"]
            has_rule = cfg["has_judge_rule"]
            expected_v = "FAIL"
        else:
            final_resp = copy.deepcopy(raw_resp)
            defect_family = None
            defect_desc = "Untouched real model output"
            has_rule = None
            expected_v = "PASS"

        pairs_list.append({
            "question_id": qid,
            "topic": item["topic"],
            "question": item["question"],
            "retrieved_chunks": item["retrieved_chunks"],
            "generated_response": final_resp,
            "judge_criteria": gold_q.get("expected_rubric", []),
            "_is_injected": is_injected,
            "_defect_family": defect_family,
            "_defect_description": defect_desc,
            "_has_judge_rule": has_rule,
            "_expected_verdict": expected_v,
        })

    # Shuffle deterministically with seed 45
    rng = random.Random(45)
    rng.shuffle(pairs_list)

    # Assign pair_ids D45-01 through D45-30
    blind_pairs = []
    secret_key = []

    for idx, p in enumerate(pairs_list, 1):
        pair_id = f"D45-{idx:02d}"
        
        # Secret key entry
        secret_key.append({
            "pair_id": pair_id,
            "question_id": p["question_id"],
            "topic": p["topic"],
            "is_injected": p["_is_injected"],
            "defect_family": p["_defect_family"],
            "defect_description": p["_defect_description"],
            "has_judge_rule": p["_has_judge_rule"],
            "expected_verdict": p["_expected_verdict"],
        })

        # Blind pair entry (strictly NO injection metadata or judge output)
        blind_pairs.append({
            "pair_id": pair_id,
            "question_id": p["question_id"],
            "topic": p["topic"],
            "question": p["question"],
            "retrieved_chunks": p["retrieved_chunks"],
            "generated_response": p["generated_response"],
            "judge_criteria": p["judge_criteria"],
        })

    # Save blind pairs
    pairs_path = PROJECT_ROOT / "eval" / "judge_day45_pairs.json"
    with open(pairs_path, "w", encoding="utf-8") as f:
        json.dump(blind_pairs, f, indent=2)

    # Save secret key
    key_path = PROJECT_ROOT / "eval" / "injection_key_d45.json"
    with open(key_path, "w", encoding="utf-8") as f:
        json.dump(secret_key, f, indent=2)

    print(f"Created {len(blind_pairs)} blind pairs in {pairs_path}")
    print(f"Created {len(secret_key)} secret key records in {key_path}")

    # Print summary
    injected_count = sum(1 for k in secret_key if k["is_injected"])
    untouched_count = sum(1 for k in secret_key if not k["is_injected"])
    no_rule_count = sum(1 for k in secret_key if k["is_injected"] and not k["has_judge_rule"])
    with_rule_count = sum(1 for k in secret_key if k["is_injected"] and k["has_judge_rule"])
    print(f"Total: {len(secret_key)} pairs | Untouched: {untouched_count} | Injected: {injected_count}")
    print(f"Injected families: {no_rule_count} without judge rule, {with_rule_count} with judge rule.")

if __name__ == "__main__":
    build_datasets()
