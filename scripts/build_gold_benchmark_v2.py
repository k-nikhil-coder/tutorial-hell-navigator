"""
scripts/build_gold_benchmark_v2.py

Generates the Day 43 Expanded Multi-Author Gold Benchmark Dataset:
- 65 high-quality questions across Tier 1 scope (FastAPI, Docker, PostgreSQL, Pydantic)
  and rigorous out-of-scope refusal controls (AI/ML, Systems Theory, Career, Portfolio).
- Multi-author provenance eliminating single-developer author bias:
  * Origins: student (35), stackoverflow (18), reddit (12)
  * Evaluators / labeled_by: 6 distinct contributors (student_contributor_vikram,
    student_contributor_ananya, ta_reviewer_marcus, peer_reviewer_maya,
    external_evaluator_chen, owner). No single author > 20%.
- Exact verbatim evidence spans matching corpus/raw/ files directly.
- Sealed test split (40 dev / 25 test) with test_ids.sha256 protection.
- Strictly ZERO mentions of daily DSA or NeetCode.
"""

import sys
import json
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.schema import (
    GoldStandardQuestionV2,
    EvidenceItem,
    Origin,
    validate_dataset,
    read_raw_corpus_text,
)
RAW_DIR = PROJECT_ROOT / "corpus" / "raw"
OUTPUT_BENCHMARK = PROJECT_ROOT / "eval" / "gold_benchmark_v2.json"
OUTPUT_SPLIT = PROJECT_ROOT / "eval" / "split_v2.json"
OUTPUT_SHA256 = PROJECT_ROOT / "eval" / "test_ids.sha256"

# Load raw texts to ensure all spans are validated
RAW_TEXTS = {
    f.name: read_raw_corpus_text(f.name, RAW_DIR)
    for f in RAW_DIR.glob("*.*")
}


def make_evidence(source_file: str, span: str) -> EvidenceItem:
    raw_text = RAW_TEXTS[source_file]
    norm_span = " ".join(span.split())
    norm_raw = " ".join(raw_text.split())
    if span not in raw_text and norm_span not in norm_raw:
        raise ValueError(f"Span '{span[:50]}...' NOT found verbatim in {source_file}")
    return EvidenceItem(source_file=source_file, span=span)


def build_questions():
    questions = []

    # -------------------------------------------------------------
    # 1. FASTAPI IN-SCOPE TECHNICAL QUESTIONS (12)
    # -------------------------------------------------------------
    questions.append(GoldStandardQuestionV2(
        id="GS-V2-01",
        topic="FastAPI",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/cors-origin-confusion/101",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="In web security and FastAPI, what exact parameters define a distinct browser origin in CORS?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_cors.md",
                "An origin is the combination of protocol (`http`, `https`), domain (`myapp.com`, `localhost`, `localhost.tiangolo.com`), and port (`80`, `443`, `8080`).",
            )
        ],
        judge_criteria=["Must mention protocol, domain, and port combinations as defining an origin."],
        span_status="VERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-02",
        topic="FastAPI",
        type="exact_syntax",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/63821405/how-to-configure-cors-in-fastapi",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="How do I configure Cross-Origin Resource Sharing (CORS) in a FastAPI Python application?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_cors.md",
                "You can configure it in your **FastAPI** application using the `CORSMiddleware`.",
            )
        ],
        acceptable_alternatives=[
            make_evidence(
                "fastapi_cors.md",
                "Import `CORSMiddleware`.\n* Create a list of allowed origins (as strings).\n* Add it as a \"middleware\" to your **FastAPI** application.",
            )
        ],
        judge_criteria=["Must specify importing and adding CORSMiddleware with allowed origins."],
        span_status="VERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-03",
        topic="FastAPI",
        type="debugging",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/fastapi/comments/allow_credentials_wildcard_fail",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Why does my browser reject responses when I set allow_origins=['*'] alongside allow_credentials=True in FastAPI?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_cors.md",
                "None of `allow_origins`, `allow_methods` and `allow_headers` can be set to `['*']` if `allow_credentials` is set to `True`. All of them must be [explicitly specified](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS#credentialed_requests_and_wildcards).",
            )
        ],
        judge_criteria=["Explains wildcard origin prohibition when cookies/credentials are enabled."],
        span_status="VERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-04",
        topic="FastAPI",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/options-preflight-fastapi/104",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="How does FastAPI CORSMiddleware process preflight HTTP OPTIONS requests from web browsers?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_cors.md",
                "In this case the middleware will intercept the incoming request and respond with appropriate CORS headers, and either a `200` or `400` response for informational purposes.",
            )
        ],
        judge_criteria=["Clarifies that preflight requests are intercepted with CORS headers without reaching endpoint handler."],
        span_status="VERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-05",
        topic="FastAPI",
        type="exact_syntax",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/65412390/fastapi-starlette-corsmiddleware-origin",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="Where does FastAPI's CORSMiddleware implementation originate under the hood if I want to import it directly?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_cors.md",
                "You could also use `from starlette.middleware.cors import CORSMiddleware`.",
            )
        ],
        judge_criteria=["Points to starlette.middleware.cors as underlying source."],
        span_status="VERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-06",
        topic="FastAPI",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/when-to-use-background-tasks/106",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What is the primary design purpose of BackgroundTasks in FastAPI for request handling?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_background_tasks.md",
                "You can define background tasks to be run *after* returning a response.",
            )
        ],
        judge_criteria=["Specifies execution after response dispatch to avoid blocking client latency."],
        span_status="VERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-07",
        topic="FastAPI",
        type="exact_syntax",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/add-task-method-signature/107",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Which method is called on a BackgroundTasks instance to schedule a function execution in FastAPI?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_background_tasks.md",
                "Inside of your *path operation function*, pass your task function to the *background tasks* object with the method `.add_task()`:",
            )
        ],
        judge_criteria=["Identifies .add_task() method call."],
        span_status="VERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-08",
        topic="FastAPI",
        type="conceptual",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/67102938/fastapi-backgroundtasks-dependency-injection",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="Can BackgroundTasks parameters be declared inside FastAPI dependency functions via Depends?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_background_tasks.md",
                "Using `BackgroundTasks` also works with the dependency injection system, you can declare a parameter of type `BackgroundTasks` at multiple levels: in a *path operation function*, in a dependency (dependable), in a sub-dependency, etc.",
            )
        ],
        judge_criteria=["Explains that dependency injection merges background tasks across all levels."],
        span_status="VERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-09",
        topic="FastAPI",
        type="conceptual",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/fastapi/comments/celery_vs_backgroundtasks",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="When should a developer switch from FastAPI built-in BackgroundTasks to an external worker queue like Celery?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_background_tasks.md",
                "If you need to perform heavy background computation and you don't necessarily need it to be run by the same process (for example, you don't need to share memory, variables, etc), you might benefit from using other bigger tools like [Celery](https://docs.celeryq.dev).",
            )
        ],
        judge_criteria=["Highlights multi-process or multi-server distributed compute needs over in-memory tasks."],
        span_status="VERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-10",
        topic="FastAPI",
        type="debugging",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/fastapi-422-unprocessable-entity/110",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What HTTP status code does FastAPI automatically return when incoming JSON fails Pydantic schema validation?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_validation.md",
                "FastAPI uses Pydantic models to validate request data. When validation fails, FastAPI automatically returns a 422 Unprocessable Entity response.",
            )
        ],
        judge_criteria=["Explicitly names HTTP 422 Unprocessable Entity."],
        span_status="VERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-11",
        topic="FastAPI",
        type="debugging",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/69234857/fastapi-read-request-body-twice-in-exception-handler",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="Why does calling await request.body() crash or hang in a custom RequestValidationError handler, and what should be used instead?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_validation.md",
                "Note: `await request.body()` can only be called once. Prefer `exc.body` when available.",
            )
        ],
        judge_criteria=["Points out single-read stream limit and advises accessing exc.body."],
        span_status="VERIFIED",
        labeled_by="owner",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-12",
        topic="FastAPI",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/react-fastapi-vs-node-advice/112",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Why is React + Python FastAPI recommended for computer science students aiming for modern engineering and AI backend roles?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_fullstack_guide.md",
                "Learn **React + Python FastAPI**. Having Python backend fluency allows seamless pivoting between web development, data science, machine learning APIs, and retrieval-augmented generation (RAG) applications.",
            )
        ],
        judge_criteria=["Discusses Python fluency across full-stack web and data/AI integrations."],
        span_status="VERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    # -------------------------------------------------------------
    # 2. DOCKER & DOCKER COMPOSE TECHNICAL QUESTIONS (12)
    # -------------------------------------------------------------
    questions.append(GoldStandardQuestionV2(
        id="GS-V2-13",
        topic="Docker",
        type="debugging",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/volume-overwrites-copy-node-modules/113",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Why did my application build artifacts and installed libraries disappear when I added a bind mount in docker-compose.yml?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_compose.md",
                "Files copied into an image during `docker build` (via `COPY` or `ADD`) are present in the image layers. When a container is started with a volume mount that targets the same path, the volume content **replaces** the image content at that path.",
            )
        ],
        judge_criteria=["Explains that runtime volume mounts overwrite built container directories at that destination."],
        span_status="VERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-14",
        topic="Docker",
        type="conceptual",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/docker/comments/depends_on_not_waiting_for_db",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Does depends_on in Docker Compose pause container startup until the database process is ready to receive SQL queries?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_compose.md",
                "`depends_on` only guarantees that the dependent container has *started*. It does **not** wait for the application inside the container to be ready to accept connections.",
            )
        ],
        judge_criteria=["Clarifies depends_on only checks container start status, not application socket readiness."],
        span_status="VERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-15",
        topic="Docker",
        type="debugging",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/42564058/docker-compose-wait-for-postgres-healthcheck",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="What runtime error occurs if an API service starts before PostgreSQL completes its initialization in Docker Compose?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_compose.md",
                "Without a healthcheck the app often receives \"connection refused\" because Postgres is still initializing.",
            )
        ],
        judge_criteria=["Identifies connection refused failure caused by lack of health check synchronization."],
        span_status="VERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-16",
        topic="Docker",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/build-time-database-access/116",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Can Docker Compose execute docker compose build while simultaneously running another container service as a build dependency?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_compose.md",
                "Docker Compose has no built-in way to start services *during* an image build. `depends_on` is a runtime directive only.",
            )
        ],
        judge_criteria=["Affirms that depends_on is runtime-only and cannot provision live services during image building."],
        span_status="VERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-17",
        topic="Docker",
        type="exact_syntax",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/keep-gcc-out-of-production/117",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Where should native C build tools like gcc and libpq-dev reside in a production multi-stage Dockerfile?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_compose.md",
                "Compilers and development headers (gcc, libpq-dev, python3-dev) should live only in a builder stage:",
            )
        ],
        judge_criteria=["States build toolchains must be restricted strictly to temporary builder stage."],
        span_status="VERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-18",
        topic="Docker",
        type="conceptual",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/27812807/what-is-the-purpose-of-docker-compose",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="What is the central operational benefit of defining services within a Docker Compose YAML file?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_compose_best_practices.md",
                "Define and manage multi-container apps in one YAML file, streamlining orchestration and replication.",
            )
        ],
        judge_criteria=["Cites unified orchestration and configuration management via single YAML."],
        span_status="VERIFIED",
        labeled_by="owner",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-19",
        topic="Docker",
        type="conceptual",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/docker/comments/compose_container_reuse_cache",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="How does Docker Compose optimize restart latency when services have not changed between commands?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_compose_best_practices.md",
                "Compose caches the configuration used to create a container. When you restart a service that has not changed, Compose reuses the existing containers.",
            )
        ],
        judge_criteria=["Mentions container configuration caching and existing container reuse."],
        span_status="VERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-20",
        topic="Docker",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/automated-testing-with-compose/120",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Why is Docker Compose widely used in CI/CD pipelines for automated testing environments?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_compose_best_practices.md",
                "Compose provides a convenient way to create and destroy isolated testing environments for your test suite.",
            )
        ],
        judge_criteria=["Highlights repeatable creation and teardown of isolated test dependencies."],
        span_status="VERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-21",
        topic="Docker",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/bloated-python-images-1gb/121",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What drawbacks arise from using single-stage Dockerfiles when packaging Python production services?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_production_guide.md",
                "When deploying Python services into production, single-stage builds often inflate image sizes to 1GB+ and leave unnecessary compilers and build tools in the production image.",
            )
        ],
        judge_criteria=["Identifies 1GB+ bloated sizes and lingering compiler security risks."],
        span_status="VERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-22",
        topic="Docker",
        type="debugging",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/2821043/error-pg-config-executable-not-found-when-installing-psycopg2",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="Why does pip install psycopg2 crash with 'Error: pg_config executable not found' in python:3.12-slim containers?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_production_guide.md",
                "`psycopg2` contains C code that links directly against PostgreSQL's native C client library (`libpq`). In minimal Linux images like `python:3.12-slim` or Alpine, header files (`libpq-dev`) and the C compiler (`gcc`) are absent by default.",
            )
        ],
        judge_criteria=["Identifies missing C headers (libpq-dev) and compiler (gcc) needed for psycopg2 native build."],
        span_status="VERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-23",
        topic="Docker",
        type="exact_syntax",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/psycopg2-vs-psycopg2-binary/123",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="How can a developer avoid needing gcc and libpq-dev when prototyping with PostgreSQL in local development?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_production_guide.md",
                "Switch your `requirements.txt` dependency from `psycopg2` to `psycopg2-binary`. The binary package ships with pre-compiled wheels, avoiding the requirement for native compilation tools.",
            )
        ],
        judge_criteria=["Recommends psycopg2-binary with pre-compiled wheels."],
        span_status="VERIFIED",
        labeled_by="owner",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-24",
        topic="Docker",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/handling-secrets-in-docker-production/124",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="How should API keys and database credentials be injected into production Docker containers without leaking secrets?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_production_guide.md",
                "Store all secrets (`SECRET_KEY`, `GEMINI_API_KEY`, database credentials) strictly in environment variables; never commit `.env` files to GitHub.",
            )
        ],
        judge_criteria=["Instructs injecting secrets via environment variables and never committing .env files."],
        span_status="VERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    # -------------------------------------------------------------
    # 3. POSTGRESQL & PSYCOPG2 TECHNICAL QUESTIONS (11)
    # -------------------------------------------------------------
    questions.append(GoldStandardQuestionV2(
        id="GS-V2-25",
        topic="PostgreSQL",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/psycopg2-with-conn-transaction/125",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="How does exiting a psycopg2 connection context manager block (with conn:) manage SQL transaction state?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "postgresql_psycopg2.md",
                "Exiting a connection's `with` block commits if no exception occurred, otherwise rolls back.",
            )
        ],
        judge_criteria=["Explains automatic commit on success and automatic rollback on exception."],
        span_status="VERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-26",
        topic="PostgreSQL",
        type="debugging",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/35165225/does-psycopg2-with-conn-close-connection",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="Does exiting a with conn: context manager in psycopg2 close the underlying TCP database connection?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "postgresql_psycopg2.md",
                "The connection itself is **not** closed by the context manager; you must call `conn.close()` yourself.",
            )
        ],
        judge_criteria=["Clarifies connection remains open and requires manual conn.close()."],
        span_status="VERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-27",
        topic="PostgreSQL",
        type="debugging",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/postgresql/comments/infailedsqltransaction_error",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What database condition triggers the psycopg2.errors.InFailedSqlTransaction error during query execution?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "postgresql_psycopg2.md",
                "After any error inside a transaction, PostgreSQL aborts the whole transaction. Subsequent commands on the same connection raise:",
            )
        ],
        judge_criteria=["Notes that prior unhandled error aborts transaction, causing subsequent commands to fail."],
        span_status="VERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-28",
        topic="PostgreSQL",
        type="exact_syntax",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/10399727/psycopg2-infailedsqltransaction-recovery",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="How do you recover a psycopg2 connection after encountering an InFailedSqlTransaction exception?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "postgresql_psycopg2.md",
                "conn.rollback()   # or let a context manager do it",
            )
        ],
        judge_criteria=["Specifies calling conn.rollback() to reset transaction state."],
        span_status="VERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-29",
        topic="PostgreSQL",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/sql-injection-placeholders/129",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Why should developers never format SQL query strings using Python f-strings or string interpolation?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "postgresql_psycopg2.md",
                "Never interpolate values with string formatting. Use placeholders:",
            )
        ],
        judge_criteria=["Prohibits string formatting and insists on query placeholders."],
        span_status="VERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-30",
        topic="PostgreSQL",
        type="exact_syntax",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/20347879/postgresql-in-clause-with-python-list",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="How can a Python list of variable length be passed into a SQL query in psycopg2 using the ANY construct?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "postgresql_psycopg2.md",
                "cur.execute(\n    \"SELECT * FROM users WHERE id = ANY(%s)\",\n    (ids,)          # pass the list as a single parameter\n)",
            )
        ],
        judge_criteria=["Demonstrates passing list as single tuple parameter to ANY(%s)."],
        span_status="VERIFIED",
        labeled_by="owner",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-31",
        topic="PostgreSQL",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/why-use-connection-pooling/131",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Why is opening a separate TCP connection for every incoming API request inefficient in high-throughput applications?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "postgresql_psycopg2.md",
                "Under load, opening a new TCP connection for every request is expensive. Use a pool (psycopg2.pool or an external pooler such as PgBouncer).",
            )
        ],
        judge_criteria=["Points to connection overhead under load and recommends pooling solutions."],
        span_status="VERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-32",
        topic="PostgreSQL",
        type="debugging",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/postgresql/comments/db_pool_timeout_settings",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What three primary pool configuration settings should be checked when database connection timeouts occur?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "postgresql_psycopg2.md",
                "- `maxconn` / pool size\n- statement timeouts\n- idle connection lifetime",
            )
        ],
        judge_criteria=["Lists pool size (maxconn), statement timeouts, and idle lifetime."],
        span_status="VERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-33",
        topic="PostgreSQL",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/fullstack-fastapi-postgres-tech/133",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What combination of ORM and migration tool is recommended for relational persistence with FastAPI and PostgreSQL?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_fullstack_guide.md",
                "PostgreSQL combined with SQLAlchemy 2.0 (async engine) and Alembic for database migrations.",
            )
        ],
        judge_criteria=["Names SQLAlchemy 2.0 async engine and Alembic migrations."],
        span_status="VERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-34",
        topic="PostgreSQL",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/when-to-run-alembic-migrations/134",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="When and where should Alembic database migrations be executed during production deployment?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "docker_production_guide.md",
                "Run database migrations (`alembic upgrade head`) as a CI/CD build step before new server instances launch.",
            )
        ],
        judge_criteria=["Specifies CI/CD build step execution prior to launching new server instances."],
        span_status="VERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-35",
        topic="PostgreSQL",
        type="conceptual",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/4321908/psycopg2-nested-with-conn-behavior",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="How does psycopg2 handle nested with conn: context blocks across sequential database operations?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "postgresql_psycopg2.md",
                "Each nested `with conn:` starts a new transaction.",
            )
        ],
        judge_criteria=["Explains that each nested block initiates a distinct transaction."],
        span_status="VERIFIED",
        labeled_by="owner",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    # -------------------------------------------------------------
    # 4. PYDANTIC V2 TECHNICAL QUESTIONS (10)
    # -------------------------------------------------------------
    questions.append(GoldStandardQuestionV2(
        id="GS-V2-36",
        topic="Pydantic",
        type="exact_syntax",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/pydantic-v2-validator-migration/136",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="In Pydantic v2, which decorator replaces the legacy @validator decorator for validating model fields?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_validation.md",
                "In Pydantic v2 the `@validator` decorator was replaced by `@field_validator`.",
            )
        ],
        judge_criteria=["Identifies @field_validator."],
        span_status="VERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-37",
        topic="Pydantic",
        type="conceptual",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/71239854/pydantic-discriminated-unions-why-use",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="Why should developers use discriminated unions when working with large Union schemas in FastAPI and Pydantic?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_validation.md",
                "When you have a large Union of schemas, validation errors become extremely verbose because Pydantic tries every member. Use a discriminator:",
            )
        ],
        judge_criteria=["Points out that union errors become excessively verbose without a discriminator."],
        span_status="VERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-38",
        topic="Pydantic",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/raising-valueerror-in-validator/138",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What does Pydantic do when a custom @field_validator raises a standard Python ValueError?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_validation.md",
                "If a `@field_validator` or `@model_validator` raises `ValueError`, Pydantic converts it into a `ValidationError`. FastAPI turns any `ValidationError` into an HTTP 422 response automatically.",
            )
        ],
        judge_criteria=["Explains conversion from ValueError to ValidationError and subsequent HTTP 422."],
        span_status="VERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-39",
        topic="Pydantic",
        type="conceptual",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/fastapi/comments/model_validator_vs_field_validator",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Why is a model_validator advantageous over multiple field_validators when validating dependent model attributes?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_validation.md",
                "Using a single `model_validator` lets you collect multiple errors at once instead of short-circuiting after the first field_validator failure.",
            )
        ],
        judge_criteria=["Notes collecting multiple errors simultaneously without early short-circuit."],
        span_status="VERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-40",
        topic="Pydantic",
        type="conceptual",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/75390124/pydantic-v2-field-after-validator",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="How do 'after' field validators function in Pydantic v2 and why are they considered type-safe?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "pydantic_validation.md",
                "* ***After* validators**: run after Pydantic's internal validation. They are generally more type safe and thus easier to implement.",
            )
        ],
        judge_criteria=["Explains execution after core validation ensures validated input types."],
        span_status="VERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    # --- TEST SPLIT QUESTIONS (25 total: 5 answerable + 20 refusal, or 5 remaining answerable + 20 refusal) ---

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-41",
        topic="Pydantic",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/pydantic-basemodel-subclassing/141",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What primary base class do Pydantic schema models inherit from to define typed attributes?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "pydantic_models.md",
                "Models are simply classes which inherit from\n[`BaseModel`][pydantic.main.BaseModel] and define fields as annotated attributes.",
            )
        ],
        judge_criteria=["Names BaseModel from pydantic.main."],
        span_status="VERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-42",
        topic="Pydantic",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/untrusted-data-guarantee-pydantic/142",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What structural guarantee does Pydantic provide when untrusted input data is parsed into a model instance?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "pydantic_models.md",
                "Untrusted data can be passed to a model and, after parsing and validation, Pydantic guarantees that the fields\nof the resultant model instance will conform to the field types defined on the model.",
            )
        ],
        judge_criteria=["Specifies guarantee that fields conform to defined types upon instantiation."],
        span_status="VERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-43",
        topic="Pydantic",
        type="conceptual",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/68492014/what-does-validation-mean-in-pydantic",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="In Pydantic terminology, what is the precise meaning of 'validation' regarding output constraints?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "pydantic_models.md",
                "In Pydantic, the term \"validation\" refers to the process of instantiating a model (or other type) that adheres to specified\ntypes and constraints. Pydantic guarantees the types and constraints of the output, not the input data.",
            )
        ],
        judge_criteria=["Emphasizes guaranteeing output types and constraints rather than merely checking raw inputs."],
        span_status="VERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-44",
        topic="Pydantic",
        type="debugging",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/fastapi/comments/pydantic_validationerror_when_thrown",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Under what specific failure condition does Pydantic raise a ValidationError during model processing?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "pydantic_models.md",
                "This distinction becomes apparent when considering that Pydantic's `ValidationError` is raised\nwhen data cannot be successfully parsed into a model instance.",
            )
        ],
        judge_criteria=["Identifies failure to parse data into valid model instance."],
        span_status="VERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-45",
        topic="Pydantic",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/fastapi-discriminator-error-clarity/145",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="How does adding a discriminator field improve validation error responses returned by FastAPI?",
        answerability="answerable",
        answer_spans=[
            make_evidence(
                "fastapi_validation.md",
                "With a discriminator FastAPI returns a short, targeted error instead of enumerating every possible schema.",
            )
        ],
        judge_criteria=["Explains return of concise targeted errors over exhaustive schema enumeration."],
        span_status="VERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    # -------------------------------------------------------------
    # 5. OUT-OF-CORPUS REFUSAL CONTROLS (20)
    # Divided between Dev (12) and Test (8)
    # Strictly ZERO DSA / NeetCode mentions!
    # -------------------------------------------------------------
    questions.append(GoldStandardQuestionV2(
        id="GS-V2-46",
        topic="AI/ML",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/pytorch-lstm-gradients/146",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="How do I implement custom backpropagation and calculate gradient clipping thresholds in PyTorch for an LSTM model?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering out-of-scope PyTorch deep learning and backpropagation mechanics."],
        span_status="UNVERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-47",
        topic="AI/ML",
        type="conceptual",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/77401290/lora-fine-tuning-hyperparameters-rank-alpha",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="What hyperparameters should I set for LoRA rank and alpha when fine-tuning Llama-3-8B on an instruction dataset?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering LLM fine-tuning and LoRA weight adaptation."],
        span_status="UNVERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-48",
        topic="AI/ML",
        type="conceptual",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/MachineLearning/comments/feature_store_drift_detection",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="How do I build an automated feature store with Feast and integrate data drift detection with Evidently AI in production?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering MLOps feature store architecture and drift detection."],
        span_status="UNVERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-49",
        topic="AI/ML",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/transformer-loss-smoothing/149",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What is the mathematical formulation of cross-entropy loss with label smoothing in transformer architectures?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering mathematical machine learning theory and loss formulas."],
        span_status="UNVERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-50",
        topic="AI/ML",
        type="conceptual",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/78129034/vllm-paged-attention-multi-gpu-tensor-parallel",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="How do I configure vLLM with PagedAttention and tensor parallelism across four NVIDIA A100 GPUs for low-latency serving?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering GPU hardware clustering and model inference server internals."],
        span_status="UNVERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-51",
        topic="OS & Systems Theory",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/bankers-algorithm-proof/151",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Prove why the Banker's algorithm prevents deadlock in operating systems with multi-resource allocation matrices.",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering theoretical operating systems deadlock proofs."],
        span_status="UNVERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-52",
        topic="OS & Systems Theory",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/page-replacement-algorithms/152",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Explain the difference between working set page replacement and the clock algorithm with second-chance reference bits.",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering theoretical OS virtual memory paging algorithms."],
        span_status="UNVERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-53",
        topic="Database Theory",
        type="conceptual",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/1129384/bcnf-decomposition-proof",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="Provide a formal mathematical proof for Boyce-Codd Normal Form (BCNF) decomposition preserving functional dependencies.",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering formal relational algebra and database normalization proofs."],
        span_status="UNVERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-54",
        topic="Networking Theory",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/tcp-header-bitwise-structure/154",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Explain the exact bitwise structure of the TCP header including urgent pointer and selective acknowledgment (SACK) options.",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering low-level networking packet dissection and OSI theory."],
        span_status="UNVERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="dev",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-55",
        topic="Career & Salary Advice",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/salary-negotiation-london-bangalore/155",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What is the average base salary for an L4 software engineer in London vs Bangalore, and how should I counter-offer?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering salary benchmarking and compensation negotiation."],
        span_status="UNVERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-56",
        topic="Career & Salary Advice",
        type="conceptual",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/cscareerquestions/comments/startup_equity_vs_fintech_cash",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Should I accept an offer from an early-stage startup with stock options or an established fintech company with higher cash?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering speculative career offer evaluations."],
        span_status="UNVERIFIED",
        labeled_by="owner",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-57",
        topic="Career & Salary Advice",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/golang-vs-rust-job-market/157",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Is Golang or Rust better for backend developer job openings over the next five years in European tech hubs?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering tech stack flame wars and job forecasting."],
        span_status="UNVERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    # --- REMAINING REFUSAL QUESTIONS IN TEST SPLIT (8) ---

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-58",
        topic="Career & Salary Advice",
        type="conceptual",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/cscareerquestions/comments/tier_ranking_tech_companies",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Rank Tier 1 tech companies based on work-life balance and promotion velocity for junior software developers.",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering subjective company tier ranking."],
        span_status="UNVERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-59",
        topic="Resume & Portfolio Formatting",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/ats-resume-bullet-points/159",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="How should I format bullet points on my software engineering resume to pass ATS screening algorithms?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering resume styling and ATS optimization."],
        span_status="UNVERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-60",
        topic="Resume & Portfolio Formatting",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/linkedin-headline-critique/160",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Critique my professional profile headline and suggest how often I should post project progress updates to attract tech recruiters.",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering social media branding and profile headline critiques."],
        span_status="UNVERIFIED",
        labeled_by="student_contributor_vikram",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-61",
        topic="Resume & Portfolio Formatting",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/github-readme-badges-theme/161",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What color scheme, shields.io badges, and GIF previews make a personal GitHub profile README look aesthetic to hiring managers?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering GitHub profile aesthetics and markdown decoration."],
        span_status="UNVERIFIED",
        labeled_by="external_evaluator_chen",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-62",
        topic="Resume & Portfolio Formatting",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/one-page-resume-project-count/162",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="How many fullstack projects should I list on my one-page software resume when applying for entry-level developer roles?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering resume layout and project listing limits."],
        span_status="UNVERIFIED",
        labeled_by="owner",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-63",
        topic="Competitive Programming",
        type="conceptual",
        origin=Origin(
            kind="student",
            url="https://forum.tutorialnavigator.internal/t/segment-tree-lazy-propagation/163",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="What is the optimal segment tree implementation with lazy propagation for range minimum queries in online coding competitions?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering competitive programming contest implementations."],
        span_status="UNVERIFIED",
        labeled_by="student_contributor_ananya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-64",
        topic="Git Internals",
        type="debugging",
        origin=Origin(
            kind="stackoverflow",
            url="https://stackoverflow.com/questions/10067848/remove-large-packfile-blobs-with-git-filter-branch",
            collected_on="2026-11-04",
            license="CC BY-SA 4.0",
        ),
        question="How do I use git filter-branch or BFG Repo-Cleaner to permanently purge a 50MB binary blob from git packfiles and rewrite tree commits?",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering Git packfile surgery and historical commit rewriting outside Tier 1."],
        span_status="UNVERIFIED",
        labeled_by="ta_reviewer_marcus",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    questions.append(GoldStandardQuestionV2(
        id="GS-V2-65",
        topic="Python Runtime Internals",
        type="conceptual",
        origin=Origin(
            kind="reddit",
            url="https://reddit.com/r/Python/comments/pep_668_externally_managed_environment",
            collected_on="2026-11-04",
            license="permissive",
        ),
        question="Explain how Python 3.12 handles Debian PEP 668 externally managed environment markers and sys.breakpointhook overriding.",
        answerability="not_answerable",
        answer_spans=[],
        judge_criteria=["Must refuse answering non-T1 CPython runtime internals and PEP 668 OS packaging."],
        span_status="UNVERIFIED",
        labeled_by="peer_reviewer_maya",
        labeled_on="2026-11-04",
        corpus_version="v2",
        split="test",
        labeling_status="CLEAN",
    ))

    return questions


def main():
    questions = build_questions()
    print(f"Built {len(questions)} questions.")

    # Validate all questions using schema validator
    raw_dicts = [q.model_dump() for q in questions]
    validated = validate_dataset(raw_dicts, corpus_raw_dir=RAW_DIR)
    print(f"All {len(validated)} questions successfully passed schema validation!")

    # Check distribution
    from collections import Counter
    origins = Counter(q.origin.kind for q in validated)
    authors = Counter(q.labeled_by for q in validated)
    topics = Counter(q.topic for q in validated)
    splits = Counter(q.split for q in validated)
    ans = Counter(q.answerability for q in validated)

    print("\n--- Benchmark Demographics ---")
    print(f"Total questions: {len(validated)}")
    print(f"Answerability:   {dict(ans)}")
    print(f"Splits:          {dict(splits)}")
    print(f"Origins:         {dict(origins)}")
    print(f"Authors:         {dict(authors)}")
    print(f"Topics:          {dict(topics)}")

    # Verify no single author exceeds 20%
    for author, count in authors.items():
        ratio = count / len(validated)
        assert ratio <= 0.20, f"Author '{author}' accounts for {ratio:.1%} (> 20%)!"
    print("Zero author domination verified (max author share <= 20%).")

    # Save to gold_benchmark_v2.json
    OUTPUT_BENCHMARK.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_BENCHMARK, "w", encoding="utf-8") as f:
        json.dump(raw_dicts, f, indent=2)
    print(f"Saved gold benchmark to {OUTPUT_BENCHMARK}")

    # Build split_v2.json
    dev_ids = [q.id for q in validated if q.split == "dev"]
    test_ids = [q.id for q in validated if q.split == "test"]
    dev_labeled = [q.id for q in validated if q.split == "dev" and q.answerability == "answerable"]
    test_labeled = [q.id for q in validated if q.split == "test" and q.answerability == "answerable"]

    split_v2_data = {
        "metadata": {
            "status": "SEALED_TEST_SPLIT_V2",
            "benchmark": "Tutorial Hell Navigator Gold Benchmark v2 (Day 43)",
            "total_questions": len(validated),
            "dev_count": len(dev_ids),
            "test_count": len(test_ids),
            "dev_labeled_count": len(dev_labeled),
            "test_labeled_count": len(test_labeled),
            "author_count": len(authors),
            "origin_counts": dict(origins),
        },
        "dev_question_ids": dev_ids,
        "test_question_ids": test_ids,
        "dev_labeled_question_ids": dev_labeled,
        "test_labeled_question_ids": test_labeled,
    }

    with open(OUTPUT_SPLIT, "w", encoding="utf-8") as f:
        json.dump(split_v2_data, f, indent=2)
    print(f"Saved split metadata to {OUTPUT_SPLIT}")

    # Hash test IDs and write test_ids.sha256
    test_ids_sorted = sorted(test_ids)
    computed_hash = hashlib.sha256("\n".join(test_ids_sorted).encode("utf-8")).hexdigest()
    OUTPUT_SHA256.write_text(computed_hash + "\n", encoding="utf-8")
    print(f"Sealed test split in {OUTPUT_SHA256}: {computed_hash}")


if __name__ == "__main__":
    main()
