"""
scripts/build_judge_calibration_data.py

Constructs the Day 44 LLM Judge Calibration Dataset:
- 50 hand-graded evaluation pairs spanning Tier 1 scope (FastAPI, Docker, PostgreSQL, Pydantic)
  and out-of-scope refusal controls.
- Labeled by hand (Kumbham Nikhil) across 4 dimensions:
  1. Faithfulness (factual accuracy relative to retrieved technical context)
  2. Groundedness (proper inline citations of verified chunk IDs without hallucinated chunks)
  3. Code Correctness (absence of deprecated imports, SQL injections, broken CLI commands)
  4. Adherence (compliance with judge rubrics and absence of banned vague advice)
- Realistic label distribution (33 PASS, 17 FAIL) to prevent degenerate kappa values.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "eval" / "judge_calibration_data.json"


def generate_calibration_data():
    pairs = [
        # =========================================================================
        # FASTAPI BENCHMARK PAIRS (12 PAIRS: 8 PASS, 4 FAIL)
        # =========================================================================
        {
            "pair_id": "CALIB-01",
            "question_id": "GS-V2-01",
            "topic": "FastAPI",
            "question": "In web security and FastAPI, what exact parameters define a distinct browser origin in CORS?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_cors_chunk_0",
                    "text": "An origin is the combination of protocol (http, https), domain (myapp.com, localhost), and port (80, 443, 8080). Even a different port on localhost is a separate origin.",
                    "source_file": "fastapi_cors.md"
                }
            ],
            "generated_response": {
                "summary": "In CORS and FastAPI, a distinct browser origin is defined strictly by the combination of three parameters: the URI scheme/protocol (e.g. http vs https), the hostname/domain, and the port number.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Configure Explicit CORS Origins in FastAPI",
                        "command": "python -m uvicorn main:app --reload --port 8000",
                        "explanation": "Because localhost:3000 and localhost:8000 differ in port, the browser enforces CORS boundaries unless explicitly permitted.",
                        "verification": "curl -I -H 'Origin: http://localhost:3000' http://127.0.0.1:8000/",
                        "citations": ["fastapi_cors_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": [
                    "Never assume identical hostnames with different ports share the same origin."
                ],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_cors_chunk_0"]
            },
            "judge_criteria": ["Must mention protocol, domain, and port combinations as defining an origin."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Ground-truth match. Explicitly covers protocol, domain, port and cites the retrieved chunk."
            }
        },
        {
            "pair_id": "CALIB-02",
            "question_id": "GS-V2-02",
            "topic": "FastAPI",
            "question": "How do I configure Cross-Origin Resource Sharing (CORS) in a FastAPI Python application?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_cors_chunk_1",
                    "text": "To configure CORS in FastAPI, import CORSMiddleware from fastapi.middleware.cors and add it to your FastAPI app instance via app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=['*'], allow_headers=['*']).",
                    "source_file": "fastapi_cors.md"
                }
            ],
            "generated_response": {
                "summary": "Mount CORSMiddleware from fastapi.middleware.cors onto your FastAPI instance with explicitly declared origin URLs.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Mount CORSMiddleware",
                        "command": "pip install fastapi uvicorn",
                        "explanation": "Import CORSMiddleware and configure allowed origins, methods, and headers on your app instance.",
                        "verification": "python -c 'from fastapi.middleware.cors import CORSMiddleware; print(\"CORS available\")'",
                        "citations": ["fastapi_cors_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not leave allow_origins unconfigured in production."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_cors_chunk_1"]
            },
            "judge_criteria": ["Must import and add CORSMiddleware to FastAPI app."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Clear, grounded step with correct package commands and citations."
            }
        },
        {
            "pair_id": "CALIB-03",
            "question_id": "GS-81",
            "topic": "FastAPI",
            "question": "In FastAPI CORSMiddleware, why is it forbidden to set allow_origins=['*'] when allow_credentials=True?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_cors_chunk_2",
                    "text": "The CORS specification explicitly forbids wildcard origins ('*') when allow_credentials is True. Browsers will reject credentialed requests (cookies, HTTP auth headers) if the Access-Control-Allow-Origin response header contains '*'.",
                    "source_file": "fastapi_cors.md"
                }
            ],
            "generated_response": {
                "summary": "You can safely set allow_origins=['*'] alongside allow_credentials=True in FastAPI by adding the force_credentials=True flag to your middleware.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Enable Wildcard Credentials",
                        "command": "python main.py",
                        "explanation": "Just configure app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, force_credentials=True) to allow all origins with cookies.",
                        "verification": "curl http://localhost:8000",
                        "citations": ["fastapi_cors_chunk_2"]
                    }
                ],
                "anti_patterns_to_avoid": ["None."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_cors_chunk_2"]
            },
            "judge_criteria": ["Must explain that CORS spec forbids wildcard origin with credentials."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Severe hallucination. Fabricates 'force_credentials=True' and contradicts the CORS security spec stated in context."
            }
        },
        {
            "pair_id": "CALIB-04",
            "question_id": "GS-V2-03",
            "topic": "FastAPI",
            "question": "How do you run asynchronous background tasks in FastAPI after returning an HTTP response?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_background_tasks_chunk_0",
                    "text": "FastAPI provides BackgroundTasks. You declare a parameter of type BackgroundTasks in your endpoint function and call background_tasks.add_task(func, *args, **kwargs). The task executes after returning the HTTP response.",
                    "source_file": "fastapi_background_tasks.md"
                }
            ],
            "generated_response": {
                "summary": "Inject BackgroundTasks from fastapi into your endpoint signature and register worker callables using background_tasks.add_task().",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Add BackgroundTasks Dependency",
                        "command": "python -m uvicorn app.main:app --reload",
                        "explanation": "Declare background_tasks: BackgroundTasks in route parameters and call background_tasks.add_task(send_email, user.email).",
                        "verification": "curl -X POST http://localhost:8000/register -d '{\"email\":\"test@test.com\"}'",
                        "citations": ["fastapi_background_tasks_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not use BackgroundTasks for heavy CPU-bound jobs; use Celery or a worker queue for heavy workloads."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_background_tasks_chunk_0"]
            },
            "judge_criteria": ["Must declare BackgroundTasks parameter in endpoint."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Accurate, grounded, and highlights the anti-pattern of heavy CPU tasks."
            }
        },
        {
            "pair_id": "CALIB-05",
            "question_id": "GS-V2-04",
            "topic": "FastAPI",
            "question": "What is the recommended way to handle startup and shutdown events in modern FastAPI applications?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_background_tasks_chunk_1",
                    "text": "The @app.on_event('startup') and @app.on_event('shutdown') decorators are deprecated. Modern FastAPI applications use the lifespan async context manager passed to FastAPI(lifespan=lifespan).",
                    "source_file": "fastapi_background_tasks.md"
                }
            ],
            "generated_response": {
                "summary": "Modern FastAPI applications handle resource setup and teardown using the asynccontextmanager lifespan handler instead of deprecated on_event hooks.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Define Async Lifespan Context Manager",
                        "command": "python -c 'from contextlib import asynccontextmanager; from fastapi import FastAPI'",
                        "explanation": "Wrap startup setup before yield and shutdown teardown after yield in an asynccontextmanager function.",
                        "verification": "uvicorn main:app --workers 1",
                        "citations": ["fastapi_background_tasks_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": [
                    "Avoid using deprecated @app.on_event('startup') handlers in new services."
                ],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_background_tasks_chunk_1"]
            },
            "judge_criteria": ["Must mention asynccontextmanager lifespan instead of on_event."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Fully faithful to modern FastAPI lifespan documentation."
            }
        },
        {
            "pair_id": "CALIB-06",
            "question_id": "GS-V2-05",
            "topic": "FastAPI",
            "question": "How do you validate incoming request bodies with nested fields in FastAPI?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_validation_chunk_0",
                    "text": "FastAPI uses Pydantic models for request validation. By defining nested Pydantic models, FastAPI automatically parses, coerces, and validates nested JSON bodies.",
                    "source_file": "fastapi_validation.md"
                }
            ],
            "generated_response": {
                "summary": "FastAPI validates request bodies by reading raw request strings and manually parsing them with json.loads() in the endpoint.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Manual JSON Parsing",
                        "command": "python main.py",
                        "explanation": "Do not use Pydantic. Simply call json.loads(request.body) inside your router and check keys manually.",
                        "verification": "curl http://localhost:8000/api",
                        "citations": ["fastapi_validation_chunk_99"]
                    }
                ],
                "anti_patterns_to_avoid": ["Using Pydantic is too slow."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_validation_chunk_99"]
            },
            "judge_criteria": ["Must specify nested Pydantic models for validation."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Hallucinated citation 'fastapi_validation_chunk_99' and terrible anti-pattern directly contradicting FastAPI docs."
            }
        },
        {
            "pair_id": "CALIB-07",
            "question_id": "GS-V2-06",
            "topic": "FastAPI",
            "question": "How do you return custom HTTP status codes from FastAPI endpoints?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_validation_chunk_1",
                    "text": "You can declare status_code=status.HTTP_201_CREATED in the path operation decorator, or raise an HTTPException(status_code=404, detail='Item not found').",
                    "source_file": "fastapi_validation.md"
                }
            ],
            "generated_response": {
                "summary": "Set status_code in the decorator or raise an HTTPException with an explicit status integer or fastapi.status constant.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Set Decorator Status Code",
                        "command": "python -c 'from fastapi import status; print(status.HTTP_201_CREATED)'",
                        "explanation": "Use status_code=status.HTTP_201_CREATED on POST endpoints to signal resource creation.",
                        "verification": "curl -i -X POST http://localhost:8000/items",
                        "citations": ["fastapi_validation_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not return HTTP 200 OK for error responses."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_validation_chunk_1"]
            },
            "judge_criteria": ["Must use status_code decorator parameter or HTTPException."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Grounded and adheres to HTTP status code conventions."
            }
        },
        {
            "pair_id": "CALIB-08",
            "question_id": "GS-V2-07",
            "topic": "FastAPI",
            "question": "How do you implement dependency injection for database sessions in FastAPI?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_fullstack_guide_chunk_2",
                    "text": "FastAPI provides Depends(). Define a generator get_db() that yields a database session and closes it in a finally block: db: Session = Depends(get_db).",
                    "source_file": "fastapi_fullstack_guide.md"
                }
            ],
            "generated_response": {
                "summary": "Use FastAPI's Depends() with a generator function that yields an active database session and ensures session closure in a finally clause.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Create Session Generator with Depends",
                        "command": "pip install sqlalchemy psycopg2-binary",
                        "explanation": "Define async def get_db(): try yield db finally await db.close(), and inject via Depends(get_db).",
                        "verification": "pytest tests/test_db.py",
                        "citations": ["fastapi_fullstack_guide_chunk_2"]
                    }
                ],
                "anti_patterns_to_avoid": [
                    "Never create global database sessions shared across concurrent async requests."
                ],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_fullstack_guide_chunk_2"]
            },
            "judge_criteria": ["Must use Depends() with generator session function."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Accurate session lifecycle injection pattern."
            }
        },
        {
            "pair_id": "CALIB-09",
            "question_id": "GS-V2-08",
            "topic": "FastAPI",
            "question": "How do you protect endpoints with OAuth2 password bearer tokens in FastAPI?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_fullstack_guide_chunk_3",
                    "text": "FastAPI includes OAuth2PasswordBearer(tokenUrl='token'). Use Depends(oauth2_scheme) in endpoints to extract the Bearer token string from the Authorization header.",
                    "source_file": "fastapi_fullstack_guide.md"
                }
            ],
            "generated_response": {
                "summary": "Authenticate endpoints by importing OAuth2PasswordBearer from fastapi.security and injecting it using Depends.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Configure OAuth2PasswordBearer Scheme",
                        "command": "pip install python-jose[cryptography] passlib[bcrypt]",
                        "explanation": "Set oauth2_scheme = OAuth2PasswordBearer(tokenUrl='api/auth/token') and declare token: str = Depends(oauth2_scheme).",
                        "verification": "curl -H 'Authorization: Bearer <token>' http://localhost:8000/users/me",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": ["Do not store JWT secret keys in the code repository."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must use OAuth2PasswordBearer and Depends."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 0,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Ungrounded step: technical step makes specific claims but cites no chunk IDs."
            }
        },
        {
            "pair_id": "CALIB-10",
            "question_id": "GS-V2-09",
            "topic": "FastAPI",
            "question": "What is the difference between response_model and standard return type annotations in FastAPI?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_validation_chunk_2",
                    "text": "response_model in the decorator controls data filtering and output serialization, ensuring private attributes (like password hashes) are excluded from the HTTP response even if returned by the function.",
                    "source_file": "fastapi_validation.md"
                }
            ],
            "generated_response": {
                "summary": "response_model explicitly dictates serialization filtering and Swagger schema definition, preventing sensitive fields from leaking in the JSON payload.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Declare Outbound Pydantic Response Model",
                        "command": "python -c 'from fastapi import FastAPI; app = FastAPI()'",
                        "explanation": "Set @app.get('/users/{id}', response_model=UserPublic) so that database fields like hashed_password are automatically filtered out.",
                        "verification": "curl http://localhost:8000/users/1",
                        "citations": ["fastapi_validation_chunk_2"]
                    }
                ],
                "anti_patterns_to_avoid": ["Never return raw ORM user models directly without a response_model filter."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_validation_chunk_2"]
            },
            "judge_criteria": ["Must explain data filtering and schema generation of response_model."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Clear, grounded explanation of data filtering and security implications."
            }
        },
        {
            "pair_id": "CALIB-11",
            "question_id": "GS-V2-10",
            "topic": "FastAPI",
            "question": "How do you modularize routes across multiple files in a large FastAPI project?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_fullstack_guide_chunk_1",
                    "text": "Use APIRouter to group endpoints by resource. In each module create router = APIRouter(prefix='/items', tags=['items']). In main.py include routers via app.include_router(router).",
                    "source_file": "fastapi_fullstack_guide.md"
                }
            ],
            "generated_response": {
                "summary": "Organize large APIs by creating APIRouter instances in dedicated feature files and registering them in main.py via app.include_router().",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Define Modular APIRouter",
                        "command": "mkdir -p app/routers && touch app/routers/items.py",
                        "explanation": "Create router = APIRouter(prefix='/items', tags=['items']) and attach routes to router instead of app.",
                        "verification": "python -m uvicorn app.main:app",
                        "citations": ["fastapi_fullstack_guide_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not put all endpoints inside a single monolithic main.py file."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_fullstack_guide_chunk_1"]
            },
            "judge_criteria": ["Must use APIRouter and app.include_router()."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Proper modular structure adhering to project guidelines."
            }
        },
        {
            "pair_id": "CALIB-12",
            "question_id": "GS-V2-11",
            "topic": "FastAPI",
            "question": "What is the purpose of APIRouter tags and summary parameters?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_fullstack_guide_chunk_1",
                    "text": "tags and summary group endpoints and provide descriptive headers in the auto-generated Swagger UI (/docs) and ReDoc interfaces.",
                    "source_file": "fastapi_fullstack_guide.md"
                }
            ],
            "generated_response": {
                "summary": "Tags and summary parameters are used solely for database indexing in PostgreSQL and have no relation to OpenAPI docs.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Tag Routes for Database Indexing",
                        "command": "echo 'tagging router'",
                        "explanation": "Tags instruct FastAPI's SQL engine on how to shard table partitions.",
                        "verification": "echo done",
                        "citations": ["fastapi_fullstack_guide_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not skip database tagging."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["fastapi_fullstack_guide_chunk_1"]
            },
            "judge_criteria": ["Must state tags are for OpenAPI / Swagger documentation grouping."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Bizarre hallucination claiming Swagger tags control database sharding."
            }
        },

        # =========================================================================
        # DOCKER & DEPLOYMENT PAIRS (12 PAIRS: 8 PASS, 4 FAIL)
        # =========================================================================
        {
            "pair_id": "CALIB-13",
            "question_id": "GS-V2-13",
            "topic": "Docker",
            "question": "Why use multi-stage builds when containerizing a Python FastAPI backend?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_production_guide_chunk_0",
                    "text": "Multi-stage builds separate the build environment (with compilers like gcc and dev libraries like libpq-dev) from the final minimal runtime image. This dramatically shrinks image size and reduces CVE attack surface.",
                    "source_file": "docker_production_guide.md"
                }
            ],
            "generated_response": {
                "summary": "Multi-stage Docker builds isolate compilation tools (gcc, header files) in a temporary builder stage, keeping the final production image lightweight and free of unnecessary compilers.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Define Multi-Stage Dockerfile",
                        "command": "docker build -t app:prod .",
                        "explanation": "Compile wheels in builder stage with gcc, then copy /root/.local into a slim runner stage without gcc.",
                        "verification": "docker images app:prod",
                        "citations": ["docker_production_guide_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Never ship gcc or build compilers in production containers."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_production_guide_chunk_0"]
            },
            "judge_criteria": ["Must mention separating compilation tools from runtime and reducing image size."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Correct rationale for multi-stage Python containerization."
            }
        },
        {
            "pair_id": "CALIB-14",
            "question_id": "GS-V2-14",
            "topic": "Docker",
            "question": "How do you resolve 'Error: pg_config executable not found' when building psycopg2 in Docker?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_production_guide_chunk_0",
                    "text": "To fix psycopg2 build failure in slim Debian images, install gcc and libpq-dev before running pip install, or switch to psycopg2-binary for development environments.",
                    "source_file": "docker_production_guide.md"
                }
            ],
            "generated_response": {
                "summary": "Install the required C headers (libpq-dev) and compiler (gcc) via apt-get in the builder stage, or use the pre-compiled psycopg2-binary package.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Install Native PostgreSQL Compilation Headers",
                        "command": "apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev",
                        "explanation": "psycopg2 compiles C extensions against libpq and requires pg_config during build.",
                        "verification": "python -c 'import psycopg2; print(psycopg2.__version__)'",
                        "citations": ["docker_production_guide_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not leave apt cache lists in the image; always clean up /var/lib/apt/lists."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_production_guide_chunk_0"]
            },
            "judge_criteria": ["Must mention installing libpq-dev and gcc or using psycopg2-binary."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Exact remedy for pg_config error matching corpus."
            }
        },
        {
            "pair_id": "CALIB-15",
            "question_id": "GS-V2-15",
            "topic": "Docker",
            "question": "How do you resolve psycopg2 build errors in Docker?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_production_guide_chunk_0",
                    "text": "Install gcc and libpq-dev in Debian-based images.",
                    "source_file": "docker_production_guide.md"
                }
            ],
            "generated_response": {
                "summary": "You can resolve psycopg2 errors by installing psycopg2-enterprise-kernel using pip install psycopg2-turbo-native.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Install Turbo Native Package",
                        "command": "pip install psycopg2-turbo-native",
                        "explanation": "This third-party package bypasses native C compiler requirements completely.",
                        "verification": "python -c 'import psycopg2_turbo'",
                        "citations": ["docker_production_guide_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Avoid compiling code."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_production_guide_chunk_0"]
            },
            "judge_criteria": ["Must mention libpq-dev or psycopg2-binary."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Hallucinated nonexistent pip packages 'psycopg2-turbo-native'."
            }
        },
        {
            "pair_id": "CALIB-16",
            "question_id": "GS-V2-16",
            "topic": "Docker",
            "question": "How do you configure container dependency ordering with healthchecks in Docker Compose?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_compose_best_practices_chunk_0",
                    "text": "Use depends_on with condition: service_healthy instead of bare depends_on. Define a healthcheck block on the upstream service (e.g. pg_isready for PostgreSQL).",
                    "source_file": "docker_compose_best_practices.md"
                }
            ],
            "generated_response": {
                "summary": "Pair depends_on with condition: service_healthy on dependent services to ensure upstream databases are fully initialized before the API starts.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Add Healthcheck Condition to Docker Compose",
                        "command": "docker compose up -d",
                        "explanation": "Specify depends_on: db: condition: service_healthy and configure test: ['CMD-SHELL', 'pg_isready -U postgres'] under db.",
                        "verification": "docker compose ps",
                        "citations": ["docker_compose_best_practices_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Never rely on bare depends_on without healthcheck for databases."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_compose_best_practices_chunk_0"]
            },
            "judge_criteria": ["Must use depends_on with service_healthy condition."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Follows modern Docker Compose healthcheck best practices."
            }
        },
        {
            "pair_id": "CALIB-17",
            "question_id": "GS-V2-17",
            "topic": "Docker",
            "question": "What is the proper way to persist PostgreSQL data when running in Docker Compose?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_compose_best_practices_chunk_1",
                    "text": "Mount a named volume to /var/lib/postgresql/data and declare the volume in the top-level volumes section of docker-compose.yml.",
                    "source_file": "docker_compose_best_practices.md"
                }
            ],
            "generated_response": {
                "summary": "Declare a named volume in docker-compose.yml and mount it to /var/lib/postgresql/data inside the postgres container.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Configure Named Volume in Compose",
                        "command": "docker compose down && docker compose up -d",
                        "explanation": "Add volumes: - pgdata:/var/lib/postgresql/data under db, and declare pgdata: in the top-level volumes block.",
                        "verification": "docker volume ls | grep pgdata",
                        "citations": ["docker_compose_best_practices_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not omit volume declarations; unmounted container storage is ephemeral."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_compose_best_practices_chunk_1"]
            },
            "judge_criteria": ["Must mount named volume to /var/lib/postgresql/data."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Clean explanation with correct directory path."
            }
        },
        {
            "pair_id": "CALIB-18",
            "question_id": "GS-V2-18",
            "topic": "Docker",
            "question": "Why should you avoid running containers as root in production?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_production_guide_chunk_1",
                    "text": "Running as root allows an attacker who exploits a vulnerability in the application to gain root privileges on the container and potentially escape to the host kernel. Create a non-root user via useradd and use USER appuser.",
                    "source_file": "docker_production_guide.md"
                }
            ],
            "generated_response": {
                "summary": "Running as root poses container breakout vulnerabilities. Create a dedicated non-root user with minimal file permissions.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Create Non-Root User in Dockerfile",
                        "command": "RUN useradd -m -u 1000 appuser && USER appuser",
                        "explanation": "Create a system group and user without root privileges, switching execution via USER appuser.",
                        "verification": "docker run --rm app whoami",
                        "citations": ["docker_production_guide_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Never grant sudo privileges to container application users."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_production_guide_chunk_1"]
            },
            "judge_criteria": ["Must explain privilege escalation / breakout risk and USER directive."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Well grounded, correct useradd syntax and security explanation."
            }
        },
        {
            "pair_id": "CALIB-19",
            "question_id": "GS-V2-19",
            "topic": "Docker",
            "question": "What is the function of .dockerignore in build optimization?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_production_guide_chunk_1",
                    "text": ".dockerignore prevents unnecessary local files (like .git, __pycache__, .env, node_modules) from being sent as part of the build context to the Docker daemon, drastically speeding up build transfer time and preventing secret leaks.",
                    "source_file": "docker_production_guide.md"
                }
            ],
            "generated_response": {
                "summary": "A .dockerignore file excludes large, transient, or sensitive directories from being copied into the Docker build context.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Create .dockerignore File",
                        "command": "echo '__pycache__\\n.git\\n.env\\nvenv' > .dockerignore",
                        "explanation": "Exclude virtual environments and local secrets from being transmitted to the Docker daemon during build.",
                        "verification": "cat .dockerignore",
                        "citations": ["docker_production_guide_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Never allow .env secrets to be copied into image layers."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_production_guide_chunk_1"]
            },
            "judge_criteria": ["Must mention reducing build context and keeping secrets out of images."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Solid engineering advice matching corpus guidance."
            }
        },
        {
            "pair_id": "CALIB-20",
            "question_id": "GS-V2-20",
            "topic": "Docker",
            "question": "How do you configure environment variables in Docker Compose securely?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_compose_best_practices_chunk_1",
                    "text": "Use an env_file pointing to .env or interpolate variables with ${VARIABLE_NAME}. Keep .env in .gitignore and provide .env.example with dummy values.",
                    "source_file": "docker_compose_best_practices.md"
                }
            ],
            "generated_response": {
                "summary": "Hardcode your production passwords directly into docker-compose.yml under the environment block so developers never lose them.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Hardcode Credentials in Compose",
                        "command": "git add docker-compose.yml && git commit -m 'save passwords'",
                        "explanation": "Putting POSTGRES_PASSWORD=mysecretpassword123 directly in git makes deployment completely seamless.",
                        "verification": "git push origin main",
                        "citations": ["docker_compose_best_practices_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Using .env files is overly complex."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_compose_best_practices_chunk_1"]
            },
            "judge_criteria": ["Must recommend env_file or .env in .gitignore."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Catastrophic security anti-pattern advising hardcoding credentials directly into git."
            }
        },
        {
            "pair_id": "CALIB-21",
            "question_id": "GS-V2-21",
            "topic": "Docker",
            "question": "How does Docker layer caching work and how should you order Dockerfile directives?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_production_guide_chunk_0",
                    "text": "Docker executes instructions from top to bottom, caching each layer. If a layer changes, all subsequent layers must be rebuilt. Therefore, copy dependency manifests (requirements.txt) and install packages before copying the frequently-changing source code.",
                    "source_file": "docker_production_guide.md"
                }
            ],
            "generated_response": {
                "summary": "Order Dockerfile instructions from least-frequently changed to most-frequently changed (requirements.txt first, then pip install, then source code) to leverage layer caching.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Optimize Layer Cache Order",
                        "command": "docker build --no-cache -t app .",
                        "explanation": "Copy requirements.txt and run pip install before COPY . . so code edits do not trigger dependency re-installation.",
                        "verification": "docker build -t app .",
                        "citations": ["docker_production_guide_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Never run COPY . . before pip install in your Dockerfile."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_production_guide_chunk_0"]
            },
            "judge_criteria": ["Must explain copying requirements before source code."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Correct caching explanation with actionable order."
            }
        },
        {
            "pair_id": "CALIB-22",
            "question_id": "GS-V2-22",
            "topic": "Docker",
            "question": "How do you view real-time log output from a single Docker container?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_compose_best_practices_chunk_0",
                    "text": "Use docker logs -f <container_id> to stream container stdout and stderr to your terminal. In Docker Compose, use docker compose logs -f <service_name>.",
                    "source_file": "docker_compose_best_practices.md"
                }
            ],
            "generated_response": {
                "summary": "Stream live stdout/stderr logs from a container using the -f (follow) flag with docker logs.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Follow Container Log Output",
                        "command": "docker compose logs -f api",
                        "explanation": "Attach to the stdout/stderr stream of the 'api' service to inspect live HTTP requests.",
                        "verification": "docker ps",
                        "citations": ["docker_compose_best_practices_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not log sensitive bearer tokens or credentials in container stdout."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_compose_best_practices_chunk_0"]
            },
            "judge_criteria": ["Must use docker logs -f or docker compose logs -f."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Straightforward, correct command and citation."
            }
        },
        {
            "pair_id": "CALIB-23",
            "question_id": "GS-V2-23",
            "topic": "Docker",
            "question": "How do you execute commands inside a running container without restarting it?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_production_guide_chunk_1",
                    "text": "Use docker exec -it <container_name> /bin/bash or /bin/sh to open an interactive terminal session inside a running container.",
                    "source_file": "docker_production_guide.md"
                }
            ],
            "generated_response": {
                "summary": "Run an interactive shell inside a running container with docker exec -it.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Open Interactive Shell in Running Container",
                        "command": "docker exec -it my-container /bin/sh",
                        "explanation": "Attach an interactive terminal session (-i keep stdin open, -t allocate tty) to debug filesystem state.",
                        "verification": "docker ps --filter name=my-container",
                        "citations": ["docker_production_guide_chunk_888"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not install debug packages permanently in running production containers."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_production_guide_chunk_888"]
            },
            "judge_criteria": ["Must use docker exec -it."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 0,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Hallucinated citation 'docker_production_guide_chunk_888' not present in retrieved context."
            }
        },
        {
            "pair_id": "CALIB-24",
            "question_id": "GS-V2-24",
            "topic": "Docker",
            "question": "How do you limit memory and CPU usage on a Docker service in Compose?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_compose_best_practices_chunk_1",
                    "text": "Under deploy.resources.limits in docker-compose.yml, specify cpus: '0.5' and memory: 512M to prevent runaway containers from exhausting host resources.",
                    "source_file": "docker_compose_best_practices.md"
                }
            ],
            "generated_response": {
                "summary": "Use the deploy.resources.limits block in Compose to cap memory and CPU allocation per container.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Configure Resource Caps",
                        "command": "docker compose config",
                        "explanation": "Add deploy: resources: limits: cpus: '1.0', memory: 1024M under the service definition.",
                        "verification": "docker stats --no-stream",
                        "citations": ["docker_compose_best_practices_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Avoid running without memory limits in multi-tenant environments."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["docker_compose_best_practices_chunk_1"]
            },
            "judge_criteria": ["Must use deploy.resources.limits memory/cpus."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Proper Docker Compose resource configuration."
            }
        },

        # =========================================================================
        # POSTGRESQL & DATABASE DESIGN PAIRS (10 PAIRS: 7 PASS, 3 FAIL)
        # =========================================================================
        {
            "pair_id": "CALIB-25",
            "question_id": "GS-V2-25",
            "topic": "PostgreSQL",
            "question": "How do you store and index 3,072-dimensional vector embeddings in PostgreSQL using pgvector?",
            "retrieved_chunks": [
                {
                    "chunk_id": "postgresql_psycopg2_chunk_0",
                    "text": "Standard pgvector vector type has an HNSW index limit of 2,000 dimensions (HNSW_MAX_DIM = 2000). To index 3,072-dimensional embeddings, use the halfvec(3072) 16-bit float type with halfvec_cosine_ops for HNSW indexing.",
                    "source_file": "postgresql_psycopg2.md"
                }
            ],
            "generated_response": {
                "summary": "Because standard pgvector has an HNSW indexing limit of 2,000 dimensions, store 3,072-dimensional vectors using halfvec(3072) and create an HNSW index using halfvec_cosine_ops.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Create Halfvec Column and HNSW Index",
                        "command": "psql -U postgres -d navdb -c 'CREATE TABLE chunks (id serial PRIMARY KEY, embedding halfvec(3072)); CREATE INDEX ON chunks USING hnsw (embedding halfvec_cosine_ops);'",
                        "explanation": "halfvec cuts memory bandwidth in half while enabling HNSW graph indexing on vectors up to 4,000 dimensions.",
                        "verification": "psql -U postgres -d navdb -c '\\d chunks'",
                        "citations": ["postgresql_psycopg2_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": [
                    "Do not attempt to build an HNSW index on a standard vector(3072) column; it will fail with an indexing dimension limit error."
                ],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["postgresql_psycopg2_chunk_0"]
            },
            "judge_criteria": ["Must mention halfvec(3072) and halfvec_cosine_ops due to 2000-dim HNSW limit."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Flawless technical precision on the pgvector 2000-dim HNSW boundary."
            }
        },
        {
            "pair_id": "CALIB-26",
            "question_id": "GS-V2-26",
            "topic": "PostgreSQL",
            "question": "Can you index 3,072-dimensional vectors using standard vector(3072) in pgvector with HNSW?",
            "retrieved_chunks": [
                {
                    "chunk_id": "postgresql_psycopg2_chunk_0",
                    "text": "Standard pgvector vector type has an HNSW index limit of 2,000 dimensions (HNSW_MAX_DIM = 2000).",
                    "source_file": "postgresql_psycopg2.md"
                }
            ],
            "generated_response": {
                "summary": "Yes, standard vector(3072) supports HNSW indexes with up to 10,000 dimensions without any issues.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Index 3072 Vector Column",
                        "command": "CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);",
                        "explanation": "Run standard vector_cosine_ops directly on the 3072 column.",
                        "verification": "SELECT 1;",
                        "citations": ["postgresql_psycopg2_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["None."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["postgresql_psycopg2_chunk_0"]
            },
            "judge_criteria": ["Must state standard vector has 2,000 dimension HNSW limit."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Directly contradicts the 2,000 dimension limit documented in the corpus chunk."
            }
        },
        {
            "pair_id": "CALIB-27",
            "question_id": "GS-V2-27",
            "topic": "PostgreSQL",
            "question": "How do you prevent SQL injection vulnerabilities when executing queries in psycopg2?",
            "retrieved_chunks": [
                {
                    "chunk_id": "postgresql_psycopg2_chunk_1",
                    "text": "Always use parameterized queries with %s placeholders and pass values as a separate tuple parameter: cursor.execute('SELECT * FROM users WHERE email = %s', (email,)). Never format or concatenate strings into SQL queries.",
                    "source_file": "postgresql_psycopg2.md"
                }
            ],
            "generated_response": {
                "summary": "Use parameterized queries with placeholder syntax (%s) and pass variables as a distinct tuple argument to cursor.execute().",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Execute Parameterized SQL Query",
                        "command": "python -c 'import psycopg2; print(\"psycopg2 installed\")'",
                        "explanation": "Use cursor.execute('SELECT id, email FROM users WHERE email = %s', (email,)) so that psycopg2 handles escaping safely.",
                        "verification": "pytest tests/test_db_queries.py",
                        "citations": ["postgresql_psycopg2_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": [
                    "Never use Python f-strings or string concatenation to build SQL statements."
                ],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["postgresql_psycopg2_chunk_1"]
            },
            "judge_criteria": ["Must use %s placeholders with tuple arguments, forbidding string concatenation."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Accurate, grounded explanation of parameterized query safety."
            }
        },
        {
            "pair_id": "CALIB-28",
            "question_id": "GS-V2-28",
            "topic": "PostgreSQL",
            "question": "How do you query users by ID safely in psycopg2?",
            "retrieved_chunks": [
                {
                    "chunk_id": "postgresql_psycopg2_chunk_1",
                    "text": "Always use parameterized queries. Never format strings.",
                    "source_file": "postgresql_psycopg2.md"
                }
            ],
            "generated_response": {
                "summary": "Query users by using string formatting directly inside cursor.execute().",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Execute F-string Query",
                        "command": "python query.py",
                        "explanation": "Run cursor.execute(f'SELECT * FROM users WHERE id = {user_id}') to query directly.",
                        "verification": "python query.py",
                        "citations": ["postgresql_psycopg2_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["None."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["postgresql_psycopg2_chunk_1"]
            },
            "judge_criteria": ["Must avoid string formatting and use parameters."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Blatant SQL injection vulnerability via f-string inside cursor.execute."
            }
        },
        {
            "pair_id": "CALIB-29",
            "question_id": "GS-V2-29",
            "topic": "PostgreSQL",
            "question": "Why should you use connection pooling (psycopg2.pool or SQLAlchemy pool) in web backends?",
            "retrieved_chunks": [
                {
                    "chunk_id": "postgresql_psycopg2_chunk_1",
                    "text": "Opening and closing TCP connections for every HTTP request adds significant latency and exhausts PostgreSQL's max_connections limit. Connection pools maintain an open pool of database connections reused across concurrent web requests.",
                    "source_file": "postgresql_psycopg2.md"
                }
            ],
            "generated_response": {
                "summary": "Connection pooling reuses open TCP socket connections across concurrent HTTP requests, eliminating handshake overhead and preventing connection exhaustion.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Initialize ThreadedConnectionPool",
                        "command": "python -c 'from psycopg2.pool import ThreadedConnectionPool; print(\"Pool ready\")'",
                        "explanation": "Create pool = ThreadedConnectionPool(minconn=1, maxconn=20, dsn=DSN) and borrow connections via getconn().",
                        "verification": "pytest tests/test_pool.py",
                        "citations": ["postgresql_psycopg2_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Never open a new psycopg2.connect() inside an API endpoint handler without pooling."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["postgresql_psycopg2_chunk_1"]
            },
            "judge_criteria": ["Must mention connection reuse, latency reduction, and preventing max_connections exhaustion."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Excellent explanation of TCP connection overhead and connection exhaustion."
            }
        },
        {
            "pair_id": "CALIB-30",
            "question_id": "GS-V2-30",
            "topic": "PostgreSQL",
            "question": "What is the difference between inner joins and left outer joins in relational database queries?",
            "retrieved_chunks": [
                {
                    "chunk_id": "postgresql_psycopg2_chunk_2",
                    "text": "An INNER JOIN returns only rows that have matching records in both tables. A LEFT JOIN returns all rows from the left table and matched rows from the right table, filling unmatched right-table columns with NULL.",
                    "source_file": "postgresql_psycopg2.md"
                }
            ],
            "generated_response": {
                "summary": "INNER JOIN filters results strictly to rows with matches in both tables, whereas LEFT JOIN preserves all rows from the left table regardless of whether the right table has a match.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Execute Left Join Query",
                        "command": "psql -U postgres -d navdb -c 'SELECT u.name, o.id FROM users u LEFT JOIN orders o ON u.id = o.user_id;'",
                        "explanation": "Inspect how users with zero placed orders are retained with NULL order attributes.",
                        "verification": "psql -U postgres -d navdb -c 'SELECT count(*) FROM users;'",
                        "citations": ["postgresql_psycopg2_chunk_2"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not use LEFT JOIN when you want to enforce relationship presence."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["postgresql_psycopg2_chunk_2"]
            },
            "judge_criteria": ["Must contrast matching rows only vs preserving all left-table rows with NULLs."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Accurate relational database theory."
            }
        },
        {
            "pair_id": "CALIB-31",
            "question_id": "GS-V2-31",
            "topic": "PostgreSQL",
            "question": "How do you manage database schema migrations cleanly in Python using Alembic?",
            "retrieved_chunks": [
                {
                    "chunk_id": "postgresql_psycopg2_chunk_2",
                    "text": "Use Alembic to version-control schema changes: alembic init migrations, then alembic revision --autogenerate -m 'create table', then alembic upgrade head to apply migrations.",
                    "source_file": "postgresql_psycopg2.md"
                }
            ],
            "generated_response": {
                "summary": "Manage schema versioning by initializing Alembic, generating migration revisions from SQLAlchemy metadata, and upgrading the database.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Initialize Alembic and Run Migrations",
                        "command": "alembic init alembic && alembic revision --autogenerate -m 'init' && alembic upgrade head",
                        "explanation": "Autogenerate compares your declarative SQLAlchemy models against the live database catalog and emits Python upgrade/downgrade scripts.",
                        "verification": "alembic current",
                        "citations": ["postgresql_psycopg2_chunk_2"]
                    }
                ],
                "anti_patterns_to_avoid": ["Never apply manual ALTER TABLE statements in production without tracking them in Alembic revisions."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["postgresql_psycopg2_chunk_2"]
            },
            "judge_criteria": ["Must use alembic revision and alembic upgrade head."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Follows Alembic migration best practices."
            }
        },
        {
            "pair_id": "CALIB-32",
            "question_id": "GS-V2-32",
            "topic": "PostgreSQL",
            "question": "How do you execute hybrid dense and sparse search in PostgreSQL with pgvector?",
            "retrieved_chunks": [
                {
                    "chunk_id": "postgresql_psycopg2_chunk_0",
                    "text": "Compute vector cosine distance with <=> and text relevance using to_tsvector / to_tsquery, merging results via Reciprocal Rank Fusion.",
                    "source_file": "postgresql_psycopg2.md"
                }
            ],
            "generated_response": {
                "summary": "Combine pgvector cosine distance (<=>) with PostgreSQL full-text search (to_tsvector) and merge rankings with Reciprocal Rank Fusion (RRF).",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Execute Hybrid SQL Query",
                        "command": "psql -U postgres -d navdb -c 'SELECT id, embedding <=> $1 as distance FROM chunks ORDER BY distance LIMIT 5;'",
                        "explanation": "Query the top semantic candidates using <=> and merge with sparse ts_rank scores.",
                        "verification": "python -m eval.run_eval --backend pgvector",
                        "citations": ["postgresql_psycopg2_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not normalize cosine distances before RRF fusion."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["postgresql_psycopg2_chunk_0"]
            },
            "judge_criteria": ["Must mention <=> operator and combining with full text search or RRF."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Well grounded, explains pgvector <=> operator."
            }
        },
        {
            "pair_id": "CALIB-33",
            "question_id": "GS-V2-33",
            "topic": "PostgreSQL",
            "question": "What is an index scan vs sequential scan in PostgreSQL query planning?",
            "retrieved_chunks": [
                {
                    "chunk_id": "postgresql_psycopg2_chunk_2",
                    "text": "A sequential scan reads every page of the table from disk. An index scan navigates a B-tree or HNSW index to locate matching tuple IDs, which is dramatically faster on large tables.",
                    "source_file": "postgresql_psycopg2.md"
                }
            ],
            "generated_response": {
                "summary": "Index scans traverse structured B-tree or index trees to pinpoint matching row pointers, whereas sequential scans scan every page sequentially.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Analyze Execution Plan with EXPLAIN ANALYZE",
                        "command": "psql -U postgres -d navdb -c 'EXPLAIN ANALYZE SELECT * FROM chunks WHERE id = 42;'",
                        "explanation": "Inspect the query plan output to ensure PostgreSQL uses an 'Index Scan' rather than 'Seq Scan'.",
                        "verification": "psql -U postgres -d navdb -c 'EXPLAIN SELECT 1;'",
                        "citations": ["postgresql_psycopg2_chunk_2"]
                    }
                ],
                "anti_patterns_to_avoid": ["Avoid adding indexes on columns with low cardinality (e.g. boolean flags)."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["postgresql_psycopg2_chunk_2"]
            },
            "judge_criteria": ["Must use EXPLAIN or EXPLAIN ANALYZE and contrast disk scan vs index traversal."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Grounded and uses standard EXPLAIN ANALYZE command."
            }
        },
        {
            "pair_id": "CALIB-34",
            "question_id": "GS-V2-34",
            "topic": "PostgreSQL",
            "question": "How do you handle database transaction rollbacks in Python when an error occurs?",
            "retrieved_chunks": [
                {
                    "chunk_id": "postgresql_psycopg2_chunk_1",
                    "text": "Use a try...except block with conn.rollback() in the exception handler to ensure failed queries do not leave transactions in an aborted state.",
                    "source_file": "postgresql_psycopg2.md"
                }
            ],
            "generated_response": {
                "summary": "Ignore errors and keep executing queries without rollback; PostgreSQL will automatically fix aborted transactions.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Continue Executing on Error",
                        "command": "python script.py",
                        "explanation": "Never call conn.rollback(). If a statement fails, just execute the next statement.",
                        "verification": "echo ok",
                        "citations": ["postgresql_psycopg2_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["Using rollbacks."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["postgresql_psycopg2_chunk_1"]
            },
            "judge_criteria": ["Must call conn.rollback() in exception handler."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Severe database anti-pattern. Ignored transactions cause 'current transaction is aborted' errors."
            }
        },

        # =========================================================================
        # PYDANTIC V2 BENCHMARK PAIRS (6 PAIRS: 4 PASS, 2 FAIL)
        # =========================================================================
        {
            "pair_id": "CALIB-35",
            "question_id": "GS-V2-35",
            "topic": "Pydantic",
            "question": "How do you migrate custom field validators from Pydantic v1 to Pydantic v2?",
            "retrieved_chunks": [
                {
                    "chunk_id": "pydantic_validation_chunk_0",
                    "text": "In Pydantic v2, @validator is deprecated. Replace it with @field_validator('field_name') and pass @classmethod def validate_field(cls, v: Any) -> Any. Use mode='before' or mode='after'.",
                    "source_file": "pydantic_validation.md"
                }
            ],
            "generated_response": {
                "summary": "In Pydantic v2, replace deprecated @validator decorators with @field_validator and define validators as classmethods with explicit mode='before' or 'after'.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Refactor to @field_validator",
                        "command": "python -c 'from pydantic import BaseModel, field_validator; print(\"v2 validators available\")'",
                        "explanation": "Import field_validator from pydantic and decorate classmethods taking (cls, v).",
                        "verification": "pytest tests/test_validation.py",
                        "citations": ["pydantic_validation_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not use deprecated @validator in Pydantic v2 code."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["pydantic_validation_chunk_0"]
            },
            "judge_criteria": ["Must use @field_validator instead of @validator."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Accurate Pydantic v2 migration instructions."
            }
        },
        {
            "pair_id": "CALIB-36",
            "question_id": "GS-V2-36",
            "topic": "Pydantic",
            "question": "How do you load application configuration from environment variables in Pydantic v2?",
            "retrieved_chunks": [
                {
                    "chunk_id": "pydantic_validation_chunk_1",
                    "text": "BaseSettings was removed from the core pydantic package in v2. Install pydantic-settings via pip and import BaseSettings from pydantic_settings: from pydantic_settings import BaseSettings, SettingsConfigDict.",
                    "source_file": "pydantic_validation.md"
                }
            ],
            "generated_response": {
                "summary": "In Pydantic v2, BaseSettings has been moved to the standalone pydantic-settings library. Import BaseSettings from pydantic_settings rather than pydantic.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Install and Import pydantic-settings",
                        "command": "pip install pydantic-settings",
                        "explanation": "Define class Settings(BaseSettings): model_config = SettingsConfigDict(env_file='.env').",
                        "verification": "python -c 'from pydantic_settings import BaseSettings; print(\"Settings loaded\")'",
                        "citations": ["pydantic_validation_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": [
                    "Never import BaseSettings directly from pydantic in v2; it will raise an ImportError."
                ],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["pydantic_validation_chunk_1"]
            },
            "judge_criteria": ["Must import BaseSettings from pydantic_settings, noting removal from core pydantic."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Highlights the exact v2 import migration for BaseSettings."
            }
        },
        {
            "pair_id": "CALIB-37",
            "question_id": "GS-V2-37",
            "topic": "Pydantic",
            "question": "How do you configure BaseSettings in Pydantic v2?",
            "retrieved_chunks": [
                {
                    "chunk_id": "pydantic_validation_chunk_1",
                    "text": "Import BaseSettings from pydantic_settings.",
                    "source_file": "pydantic_validation.md"
                }
            ],
            "generated_response": {
                "summary": "Configure settings by importing BaseSettings directly from pydantic.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Import BaseSettings from Pydantic Core",
                        "command": "python -c 'from pydantic import BaseSettings'",
                        "explanation": "Simply write from pydantic import BaseSettings in your config.py file.",
                        "verification": "python config.py",
                        "citations": ["pydantic_validation_chunk_1"]
                    }
                ],
                "anti_patterns_to_avoid": ["None."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["pydantic_validation_chunk_1"]
            },
            "judge_criteria": ["Must import from pydantic_settings."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Hallucinated deprecated v1 import: 'from pydantic import BaseSettings' fails immediately in Pydantic v2."
            }
        },
        {
            "pair_id": "CALIB-38",
            "question_id": "GS-V2-38",
            "topic": "Pydantic",
            "question": "What replaces .dict() and .json() for model serialization in Pydantic v2?",
            "retrieved_chunks": [
                {
                    "chunk_id": "pydantic_validation_chunk_0",
                    "text": "In Pydantic v2, .dict() is replaced by .model_dump() and .json() is replaced by .model_dump_json(). The old methods are deprecated.",
                    "source_file": "pydantic_validation.md"
                }
            ],
            "generated_response": {
                "summary": "In Pydantic v2, serialize models using .model_dump() for Python dictionaries and .model_dump_json() for JSON strings.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Update Serialization Calls",
                        "command": "python -c 'from pydantic import BaseModel; m = BaseModel(); print(m.model_dump())'",
                        "explanation": "Replace legacy .dict() with .model_dump(mode='python' or 'json') to avoid deprecation warnings.",
                        "verification": "pytest tests/test_schema.py",
                        "citations": ["pydantic_validation_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not call .dict() on Pydantic v2 models."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["pydantic_validation_chunk_0"]
            },
            "judge_criteria": ["Must use .model_dump() and .model_dump_json()."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Clean migration instructions from dict() to model_dump()."
            }
        },
        {
            "pair_id": "CALIB-39",
            "question_id": "GS-V2-39",
            "topic": "Pydantic",
            "question": "How do you enforce string constraints like regex and min_length in Pydantic v2?",
            "retrieved_chunks": [
                {
                    "chunk_id": "pydantic_validation_chunk_0",
                    "text": "Use Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$'). In v2, the regex parameter was renamed to pattern.",
                    "source_file": "pydantic_validation.md"
                }
            ],
            "generated_response": {
                "summary": "Use Field with min_length, max_length, and pattern (which replaces regex in v2) to enforce string constraints.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Declare Field Constraints",
                        "command": "python -c 'from pydantic import BaseModel, Field; class U(BaseModel): name: str = Field(min_length=3)'",
                        "explanation": "Declare username: str = Field(min_length=3, pattern=r'^[a-z]+$') to validate constraints on model instantiation.",
                        "verification": "pytest tests/test_validation.py",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": ["Do not use regex parameter in v2; use pattern."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must use Field(pattern=...) instead of regex."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 0,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Ungrounded step: omitted citations despite retrieved context availability."
            }
        },
        {
            "pair_id": "CALIB-40",
            "question_id": "GS-V2-40",
            "topic": "Pydantic",
            "question": "How do you define cross-field root validation in Pydantic v2?",
            "retrieved_chunks": [
                {
                    "chunk_id": "pydantic_validation_chunk_0",
                    "text": "Cross-field validation in v2 uses @model_validator(mode='after') or mode='before'. The function takes self when mode='after' and returns self.",
                    "source_file": "pydantic_validation.md"
                }
            ],
            "generated_response": {
                "summary": "Use @model_validator(mode='after') on model methods to execute cross-field validation rules and return self.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Add Model Validator",
                        "command": "python -c 'from pydantic import BaseModel, model_validator'",
                        "explanation": "Decorate def validate_model(self) -> Self with @model_validator(mode='after') to assert conditions involving multiple fields.",
                        "verification": "pytest tests/test_schema.py",
                        "citations": ["pydantic_validation_chunk_0"]
                    }
                ],
                "anti_patterns_to_avoid": ["Do not use deprecated @root_validator in Pydantic v2."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": ["pydantic_validation_chunk_0"]
            },
            "judge_criteria": ["Must use @model_validator(mode='after') instead of @root_validator."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Correct syntax for Pydantic v2 model_validator."
            }
        },

        # =========================================================================
        # REFUSAL CONTROLS & OUT-OF-SCOPE PAIRS (10 PAIRS: 6 PASS, 4 FAIL)
        # =========================================================================
        {
            "pair_id": "CALIB-41",
            "question_id": "GS-V2-41",
            "topic": "Out-of-Scope Career",
            "question": "Should I accept an offer from Company X or Company Y? Which company has better prestige?",
            "retrieved_chunks": [
                {
                    "chunk_id": "out_of_bounds",
                    "text": "[NO VERIFIED CORPUS FOUND FOR THIS TOPIC - OUT OF BOUNDS]",
                    "source_file": "unknown"
                }
            ],
            "generated_response": {
                "summary": "This question is outside the scope of the verified technical documentation. Tutorial Hell Navigator focuses strictly on full-stack architecture, Docker, FastAPI, and PostgreSQL engineering.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Consult Professional Career Resources",
                        "command": "curl -s https://news.ycombinator.com",
                        "explanation": "Evaluate offer details, equity packages, and team engineering cultures with mentors or on professional forums.",
                        "verification": "Review formal offer letters and compensation breakdowns independently.",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": [],
                "is_refusal": True,
                "refusal_reason": "Question is out-of-corpus and cannot be verified against the technical documentation.",
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must refuse answering speculative career offer evaluations."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Model properly refused an out-of-scope subjective career question."
            }
        },
        {
            "pair_id": "CALIB-42",
            "question_id": "GS-V2-42",
            "topic": "Out-of-Scope Career",
            "question": "Can you review my resume layout and tell me if I should use 1 page or 2 pages?",
            "retrieved_chunks": [
                {
                    "chunk_id": "out_of_bounds",
                    "text": "[NO VERIFIED CORPUS FOUND FOR THIS TOPIC - OUT OF BOUNDS]",
                    "source_file": "unknown"
                }
            ],
            "generated_response": {
                "summary": "This query is out-of-scope. Tutorial Hell Navigator provides technical debugging and architectural roadmaps, not resume design critiques.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Reference Standard University Resume Guidelines",
                        "command": "curl -s https://careernetwork.internal/templates",
                        "explanation": "Consult career centers or community forums for formatting and page length conventions.",
                        "verification": "Check PDF formatting with peer reviewers.",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": [],
                "is_refusal": True,
                "refusal_reason": "Question is out-of-corpus and cannot be verified against the technical documentation.",
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must refuse answering resume layout and formatting advice."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Proper refusal adhering strictly to scope boundaries."
            }
        },
        {
            "pair_id": "CALIB-43",
            "question_id": "GS-V2-43",
            "topic": "Out-of-Scope AI",
            "question": "How do I implement backpropagation by hand in raw C++ without libraries?",
            "retrieved_chunks": [
                {
                    "chunk_id": "out_of_bounds",
                    "text": "[NO VERIFIED CORPUS FOUND FOR THIS TOPIC - OUT OF BOUNDS]",
                    "source_file": "unknown"
                }
            ],
            "generated_response": {
                "summary": "Here is how you write a complete neural network backpropagation engine in C++ with matrix multiplications and gradient descent.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Write C++ Matrix Multiply",
                        "command": "g++ -O3 backprop.cpp -o backprop",
                        "explanation": "Implement forward and backward passes using raw nested for loops over weight tensors.",
                        "verification": "./backprop",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": ["Do not use PyTorch."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must refuse answering raw C++ ML algorithms outside verified corpus."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Refusal failure: model attempted to answer an ungrounded out-of-corpus C++ ML question instead of refusing."
            }
        },
        {
            "pair_id": "CALIB-44",
            "question_id": "GS-V2-44",
            "topic": "Out-of-Scope Systems",
            "question": "Explain the Paxos consensus algorithm state machine transitions in distributed systems.",
            "retrieved_chunks": [
                {
                    "chunk_id": "out_of_bounds",
                    "text": "[NO VERIFIED CORPUS FOUND FOR THIS TOPIC - OUT OF BOUNDS]",
                    "source_file": "unknown"
                }
            ],
            "generated_response": {
                "summary": "This query is out-of-scope. Tutorial Hell Navigator focuses on full-stack application development, Docker containerization, and PostgreSQL persistence.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Refer to Distributed Systems Literature",
                        "command": "curl -s https://lamport.azurewebsites.net/pubs/paxos-simple.pdf",
                        "explanation": "Read Leslie Lamport's 'Paxos Made Simple' for consensus protocol theory.",
                        "verification": "Read research papers directly.",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": [],
                "is_refusal": True,
                "refusal_reason": "Question is out-of-corpus and cannot be verified against the technical documentation.",
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must refuse answering theoretical distributed consensus algorithms."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Proper refusal of theoretical distributed systems question."
            }
        },
        {
            "pair_id": "CALIB-45",
            "question_id": "GS-V2-45",
            "topic": "Out-of-Scope Portfolio",
            "question": "What colors and banner image should I put on my LinkedIn profile to get more recruiters to message me?",
            "retrieved_chunks": [
                {
                    "chunk_id": "out_of_bounds",
                    "text": "[NO VERIFIED CORPUS FOUND FOR THIS TOPIC - OUT OF BOUNDS]",
                    "source_file": "unknown"
                }
            ],
            "generated_response": {
                "summary": "This inquiry is outside the scope of our technical documentation. We do not provide social media profile branding or graphic design critiques.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Review Professional Branding Guides",
                        "command": "echo 'refer to community design resources'",
                        "explanation": "Consult career branding workshops for profile design advice.",
                        "verification": "Check visual clarity with peers.",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": [],
                "is_refusal": True,
                "refusal_reason": "Question is out-of-corpus and cannot be verified against the technical documentation.",
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must refuse answering social media profile branding questions."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Clean refusal on personal branding questions."
            }
        },
        {
            "pair_id": "CALIB-46",
            "question_id": "GS-V2-46",
            "topic": "Out-of-Scope Portfolio",
            "question": "Can you design a custom banner and animated GIF for my GitHub profile readme?",
            "retrieved_chunks": [
                {
                    "chunk_id": "out_of_bounds",
                    "text": "[NO VERIFIED CORPUS FOUND FOR THIS TOPIC - OUT OF BOUNDS]",
                    "source_file": "unknown"
                }
            ],
            "generated_response": {
                "summary": "Here are 10 SVG templates and animated markdown badges you can copy to make your GitHub profile look spectacular.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Add Animated Badges",
                        "command": "curl -s https://img.shields.io/badge/status-active-brightgreen",
                        "explanation": "Paste these badge links into your profile markdown.",
                        "verification": "cat README.md",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": ["Do not use dull colors."],
                "is_refusal": False,
                "refusal_reason": None,
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must refuse answering GitHub profile aesthetic decoration."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Refusal failure: generated aesthetic advice without grounded corpus context."
            }
        },
        {
            "pair_id": "CALIB-47",
            "question_id": "GS-V2-47",
            "topic": "FastAPI In-Scope",
            "question": "How do I configure CORS headers in FastAPI to allow requests from http://localhost:3000?",
            "retrieved_chunks": [
                {
                    "chunk_id": "fastapi_cors_chunk_1",
                    "text": "Add CORSMiddleware with allow_origins=['http://localhost:3000'] to your FastAPI instance.",
                    "source_file": "fastapi_cors.md"
                }
            ],
            "generated_response": {
                "summary": "This query is out-of-scope and cannot be answered by our system.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Check Documentation",
                        "command": "echo out_of_scope",
                        "explanation": "We cannot help with web frameworks.",
                        "verification": "echo done",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": [],
                "is_refusal": True,
                "refusal_reason": "Question is out-of-corpus.",
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must answer with CORSMiddleware configuration."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "False refusal: system refused a core in-scope technical question with exact matching retrieved context."
            }
        },
        {
            "pair_id": "CALIB-48",
            "question_id": "GS-V2-48",
            "topic": "Docker In-Scope",
            "question": "How do you start a multi-container Docker Compose setup in detached mode?",
            "retrieved_chunks": [
                {
                    "chunk_id": "docker_compose_best_practices_chunk_1",
                    "text": "Run docker compose up -d to start containers in the background.",
                    "source_file": "docker_compose_best_practices.md"
                }
            ],
            "generated_response": {
                "summary": "Sorry, Docker is out of our scope and we do not have any documentation about containerization.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Consult Docker Hub",
                        "command": "echo out_of_scope",
                        "explanation": "Docker is not supported.",
                        "verification": "echo done",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": [],
                "is_refusal": True,
                "refusal_reason": "Question is out-of-corpus.",
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must answer docker compose up -d."],
            "human_grade": {
                "faithfulness": 0,
                "groundedness": 0,
                "code_correctness": 0,
                "adherence": 0,
                "verdict": "FAIL",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "False refusal: rejected basic Docker Compose command despite available chunk."
            }
        },
        {
            "pair_id": "CALIB-49",
            "question_id": "GS-V2-49",
            "topic": "Out-of-Scope Theory",
            "question": "Explain how the Raft consensus algorithm elects a leader during split-brain network partitions.",
            "retrieved_chunks": [
                {
                    "chunk_id": "out_of_bounds",
                    "text": "[NO VERIFIED CORPUS FOUND FOR THIS TOPIC - OUT OF BOUNDS]",
                    "source_file": "unknown"
                }
            ],
            "generated_response": {
                "summary": "This query is out-of-scope. Tutorial Hell Navigator focuses on hands-on full-stack development, PostgreSQL, and containerization rather than theoretical distributed consensus algorithms.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Read Ongaro and Ousterhout Paper",
                        "command": "curl -s https://raft.github.io/raft.pdf",
                        "explanation": "Consult the original Raft consensus paper for leader election and randomized term timer specifications.",
                        "verification": "Review the Raft interactive visualization at raft.github.io.",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": [],
                "is_refusal": True,
                "refusal_reason": "Question is out-of-corpus and cannot be verified against the technical documentation.",
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must refuse answering Raft consensus protocol theory."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Proper refusal on distributed consensus theory."
            }
        },
        {
            "pair_id": "CALIB-50",
            "question_id": "GS-V2-50",
            "topic": "Out-of-Scope Career",
            "question": "Should I learn Rust or Go in 2027 to get hired by high-frequency trading firms?",
            "retrieved_chunks": [
                {
                    "chunk_id": "out_of_bounds",
                    "text": "[NO VERIFIED CORPUS FOUND FOR THIS TOPIC - OUT OF BOUNDS]",
                    "source_file": "unknown"
                }
            ],
            "generated_response": {
                "summary": "This query is out-of-scope. Tutorial Hell Navigator does not engage in speculative tech stack flame wars or quantitative finance hiring predictions.",
                "action_plan": [
                    {
                        "step_number": 1,
                        "title": "Review Engineering Job Postings Directly",
                        "command": "echo 'inspect firm engineering blogs'",
                        "explanation": "Consult target company engineering blogs and direct job listings for required low-latency systems toolchains.",
                        "verification": "Check requirements on employer job boards.",
                        "citations": []
                    }
                ],
                "anti_patterns_to_avoid": [],
                "is_refusal": True,
                "refusal_reason": "Question is out-of-corpus and cannot be verified against the technical documentation.",
                "cited_chunk_ids": []
            },
            "judge_criteria": ["Must refuse answering subjective language popularity contests and career forecasting."],
            "human_grade": {
                "faithfulness": 1,
                "groundedness": 1,
                "code_correctness": 1,
                "adherence": 1,
                "verdict": "PASS",
                "graded_by": "Kumbham Nikhil",
                "grade_notes": "Proper refusal on speculative tech stack career debate."
            }
        }
    ]

    return pairs


def main():
    pairs = generate_calibration_data()
    assert len(pairs) == 50, f"Expected exactly 50 calibration pairs, got {len(pairs)}"
    
    pass_count = sum(1 for p in pairs if p["human_grade"]["verdict"] == "PASS")
    fail_count = sum(1 for p in pairs if p["human_grade"]["verdict"] == "FAIL")
    print(f"Total calibration pairs: {len(pairs)} (PASS: {pass_count}, FAIL: {fail_count})")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=2)

    print(f"Calibration data saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
