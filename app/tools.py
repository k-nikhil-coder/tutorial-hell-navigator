from typing import Dict, Any, List

ERROR_CATALOG: List[Dict[str, Any]] = [
    {
        "keywords": ["psycopg2", "libpq", "pg_config"],
        "error_name": "Missing psycopg2 build headers",
        "root_cause": "psycopg2 compiles from C source and needs PostgreSQL development headers (libpq-dev) and gcc in the environment.",
        "fix": "Install build dependencies in your Dockerfile before pip install, or use psycopg2-binary for local dev.",
        "cli_remediation": "RUN apt-get update && apt-get install -y libpq-dev gcc",
    },
    {
        "keywords": ["cors", "access-control-allow-origin", "preflight"],
        "error_name": "CORS preflight blocked",
        "root_cause": "The browser blocked a cross-origin request because the API is missing Access-Control-Allow-Origin response headers.",
        "fix": "Add CORSMiddleware to your FastAPI app with your frontend's origin whitelisted.",
        "cli_remediation": "from fastapi.middleware.cors import CORSMiddleware\napp.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])",
    },
    {
        "keywords": ["modulenotfounderror", "importerror", "no module named"],
        "error_name": "ModuleNotFoundError / Broken Python Path",
        "root_cause": "The package is missing from the active virtualenv or the workspace root isn't on PYTHONPATH.",
        "fix": "Activate your virtualenv, install dependencies, and make sure PYTHONPATH points to the project root.",
        "cli_remediation": "source .venv/bin/activate  # or .\\.venv\\Scripts\\Activate.ps1\npip install -r requirements.txt\nexport PYTHONPATH=.",
    },
    {
        "keywords": ["docker", "daemon", "docker.sock", "connection refused"],
        "error_name": "Docker daemon unavailable",
        "root_cause": "Docker Desktop is closed or the current user doesn't have permissions to write to /var/run/docker.sock.",
        "fix": "Start Docker Desktop or start the background docker systemd service.",
        "cli_remediation": "sudo systemctl start docker",
    },
    {
        "keywords": ["jwt", "expiredsignatureerror", "decode error", "token"],
        "error_name": "JWT signature expired or invalid",
        "root_cause": "The access token has expired or was signed with a different SECRET_KEY or algorithm.",
        "fix": "Catch ExpiredSignatureError with a 401 status and ensure the backend reads SECRET_KEY from the environment.",
        "cli_remediation": "try:\n    payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])\nexcept jwt.ExpiredSignatureError:\n    raise HTTPException(status_code=401, detail='Token expired')",
    },
    {
        "keywords": ["sqlite", "database is locked", "operationalerror"],
        "error_name": "SQLite concurrent write lock",
        "root_cause": "SQLite locks the database file during writes. Multi-threaded or async requests in FastAPI cause contention.",
        "fix": "Enable WAL mode or use check_same_thread=False for prototyping; migrate to PostgreSQL for production.",
        "cli_remediation": "create_engine('sqlite:///./app.db', connect_args={'check_same_thread': False})",
    },
    {
        "keywords": ["merge conflict", "detached head", "git pull"],
        "error_name": "Git merge conflict",
        "root_cause": "Local and remote branches made different changes to the same lines of code.",
        "fix": "Check git status, open the conflicting files to resolve markers (<<<<, ====, >>>>), then add and commit.",
        "cli_remediation": "git status\n# resolve markers in editor\ngit add <file>\ngit commit -m 'Resolve merge conflict'",
    },
    {
        "keywords": ["tle", "time limit exceeded", "maximum recursion depth", "recursionerror"],
        "error_name": "Time Limit Exceeded (TLE) / Recursion limit",
        "root_cause": "The solution has O(N^2) or exponential complexity on large inputs, or hits Python's default recursion limit (1000).",
        "fix": "Use memoization (@lru_cache) or switch to an iterative approach with hash maps to reduce complexity to O(N).",
        "cli_remediation": "from functools import lru_cache\n@lru_cache(maxsize=None)\ndef solve(...):",
    },
    {
        "keywords": ["eaddrinuse", "port already in use", "8000"],
        "error_name": "Port already in use (EADDRINUSE)",
        "root_cause": "Another uvicorn or development process is already bound to port 8000.",
        "fix": "Terminate the existing process or start the server on a different port like 8001.",
        "cli_remediation": "# macOS/Linux: lsof -ti:8000 | xargs kill -9\n# Windows: netstat -ano | findstr :8000; taskkill /PID <PID> /F",
    },
]

PROJECT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "fastapi": {
        "title": "FastAPI Microservice from Scratch",
        "duration_days": 7,
        "milestones": [
            {"day": 1, "name": "Pydantic Schemas & Settings", "focus": "Config, schemas, validation"},
            {"day": 2, "name": "Database & ORM / Migrations", "focus": "SQLAlchemy 2.0 async + Alembic"},
            {"day": 3, "name": "CRUD Endpoints & Dependency Injection", "focus": "Routers, status codes, get_db dependency"},
            {"day": 4, "name": "Authentication & JWT", "focus": "OAuth2PasswordBearer, password hashing, token validation"},
            {"day": 5, "name": "Error Handling & Logging", "focus": "Custom exception handlers, structured JSON logging"},
            {"day": 6, "name": "Automated Testing", "focus": "pytest + httpx.AsyncClient + test database"},
            {"day": 7, "name": "Docker & Multi-Stage Deployment", "focus": "Dockerfile, docker-compose, health check"},
        ],
    },
    "rag": {
        "title": "Eval-Driven RAG Engine",
        "duration_days": 7,
        "milestones": [
            {"day": 1, "name": "Gold Benchmark Definition", "focus": "Curate 50-80 question test set with rubrics"},
            {"day": 2, "name": "Document Chunking & Ingestion", "focus": "Recursive text splitter, metadata preservation"},
            {"day": 3, "name": "Dense & Sparse Indexing", "focus": "Qdrant vector store + BM25 keyword index"},
            {"day": 4, "name": "Hybrid Retrieval & Reranker", "focus": "Reciprocal Rank Fusion (RRF) + cross-encoder"},
            {"day": 5, "name": "Structured Generation & Tools", "focus": "Pydantic output validation + fallback handling"},
            {"day": 6, "name": "LLM-as-a-Judge Evaluation Pipeline", "focus": "Automated scoring against gold benchmark"},
            {"day": 7, "name": "Async FastAPI API & SSE Streaming", "focus": "Real-time token streaming + load testing"},
        ],
    },
    "fullstack": {
        "title": "Full-Stack Web App (FastAPI + React)",
        "duration_days": 7,
        "milestones": [
            {"day": 1, "name": "Monorepo Setup & OpenAPI Contract", "focus": "Directory structure, FastAPI skeleton, Swagger UI"},
            {"day": 2, "name": "Database Schema & Models", "focus": "PostgreSQL, SQLAlchemy, migration scripts"},
            {"day": 3, "name": "Core REST Endpoints", "focus": "FastAPI routers with full CRUD & status codes"},
            {"day": 4, "name": "React Frontend Shell & Routing", "focus": "Vite + React, React Router, Tailwind/UI library"},
            {"day": 5, "name": "API Integration & State Management", "focus": "React Query / fetch, loading and error states"},
            {"day": 6, "name": "Auth Flow & Protected Routes", "focus": "JWT in httpOnly cookies or auth header"},
            {"day": 7, "name": "Docker Compose Orchestration", "focus": "Compose file with frontend, backend, and database"},
        ],
    },
    "dsa": {
        "title": "7-Day Technical Interview Prep",
        "duration_days": 7,
        "milestones": [
            {"day": 1, "name": "Two-Pointers & Sliding Window", "focus": "Array & string traversal, O(N) space optimizations"},
            {"day": 2, "name": "Hash Maps & Prefix Sums", "focus": "O(1) lookups, subarray sum problems"},
            {"day": 3, "name": "Stack, Monotonic Stack & Queues", "focus": "Parentheses matching, Next Greater Element"},
            {"day": 4, "name": "Binary Search & Variants", "focus": "Rotated arrays, binary search on answer space"},
            {"day": 5, "name": "Trees & BFS/DFS", "focus": "Tree traversals, level order, LCA, path sum"},
            {"day": 6, "name": "Dynamic Programming Fundamentals", "focus": "1D DP, memoization vs tabulation, knapsack"},
            {"day": 7, "name": "Graphs & Topological Sort", "focus": "Adjacency lists, cycle detection, course schedule"},
        ],
    },
}

BLUEPRINTS: Dict[str, Dict[str, Any]] = {
    "clean_architecture": {
        "system_type": "Clean Architecture / Domain-Driven FastAPI",
        "directory_tree": """
app/
├── core/
│   ├── config.py         # App settings & env loading
│   └── security.py       # Hashing & JWT tokens
├── domain/
│   └── models.py         # Business entities (dataclasses/Pydantic)
├── repositories/
│   ├── base.py           # Abstract repository interface
│   └── user_repo.py      # SQLAlchemy DB implementation
├── services/
│   └── user_service.py   # Business logic & domain rules
├── api/
│   ├── v1/
│   │   ├── endpoints/    # Route handlers
│   │   └── router.py     # Aggregated v1 router
│   └── dependencies.py   # FastAPI dependency injection (db session)
├── schemas/
│   └── user_schema.py    # Request/response validation
└── main.py               # App factory and middleware
""",
        "layer_responsibilities": "Routers call services, services call repositories, domain entities remain independent of the database.",
    },
    "rag_engine": {
        "system_type": "Eval-Driven Hybrid RAG Pipeline",
        "directory_tree": """
rag/
├── ingestion/
│   ├── loaders.py        # Markdown/PDF document loaders
│   └── chunker.py        # Semantic chunking
├── indexing/
│   ├── vector_store.py   # Dense vector index (Qdrant)
│   └── bm25_index.py     # Sparse lexical index
├── retrieval/
│   ├── hybrid.py         # Reciprocal Rank Fusion (RRF)
│   └── reranker.py       # Cross-encoder reranker
├── synthesis/
│   ├── prompt.py         # Grounded prompt templates
│   └── client.py         # LLM client with tools & structured outputs
├── eval/
│   ├── gold_set.json     # Deterministic evaluation questions
│   └── runner.py         # Automated evaluation scoring
└── api/
    └── main.py           # FastAPI service with SSE streaming
""",
        "layer_responsibilities": "Retrieval finds the top relevant contexts; synthesis generates grounded answers without hallucinating.",
    },
}


def search_error_catalog(error_signature: str) -> Dict[str, Any]:
    """Search known error catalog for fixes and CLI commands."""
    sig_lower = error_signature.lower().strip()
    for entry in ERROR_CATALOG:
        if any(kw in sig_lower for kw in entry["keywords"]):
            return {
                "found": True,
                "fix": entry["fix"],
                "recommended_fix": entry["fix"],
                "error_name": entry["error_name"],
                "root_cause": entry["root_cause"],
                "cli_remediation": entry["cli_remediation"],
            }

    return {
        "found": False,
        "details": f"No direct match for '{error_signature}' in catalog. Check stack traces, isolate a minimal reproduction, and verify installed dependencies.",
    }


def get_project_milestones(topic: str) -> Dict[str, Any]:
    """Get a 7-day milestone roadmap for a project topic."""
    topic_lower = topic.lower().strip()
    for key, template in PROJECT_TEMPLATES.items():
        if key in topic_lower or topic_lower in key:
            return {
                "found": True,
                "topic": key,
                "milestones": [m["name"] for m in template["milestones"]],
                "template": template,
            }

    default_milestones = [
        {"day": 1, "name": "Problem Spec & Schemas", "focus": "Define inputs, outputs, and JSON/DB contracts"},
        {"day": 2, "name": "Core Engine / Logic", "focus": "Implement core algorithm in isolation"},
        {"day": 3, "name": "Persistence / Database", "focus": "Add data storage and migrations"},
        {"day": 4, "name": "API Layer / Interface", "focus": "Expose endpoints or CLI interface"},
        {"day": 5, "name": "Error Handling & Edge Cases", "focus": "Validate inputs and handle exceptions"},
        {"day": 6, "name": "Automated Testing", "focus": "Write unit and integration tests"},
        {"day": 7, "name": "Containerization & Deployment", "focus": "Docker, README, and demo run"},
    ]
    return {
        "found": False,
        "topic": topic,
        "milestones": [m["name"] for m in default_milestones],
        "template": {
            "title": f"7-Day Roadmap for {topic}",
            "duration_days": 7,
            "milestones": default_milestones,
        },
    }


def get_architecture_blueprint(system_type: str) -> Dict[str, Any]:
    """Get standard directory layout and layer boundaries for a project type."""
    sys_lower = system_type.lower().strip()
    for key, bp in BLUEPRINTS.items():
        if key in sys_lower or sys_lower in key:
            return {"found": True, "blueprint": bp}

    return {
        "found": False,
        "blueprint": BLUEPRINTS["clean_architecture"],
        "note": f"Using clean architecture template for {system_type}.",
    }


AVAILABLE_TOOLS = [
    search_error_catalog,
    get_project_milestones,
    get_architecture_blueprint,
]

TOOLS_DICT = {fn.__name__: fn for fn in AVAILABLE_TOOLS}
