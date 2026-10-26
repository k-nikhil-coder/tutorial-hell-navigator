# Production Containerization & Deployment Manual: Docker, PostgreSQL & FastAPI

## 1. Multi-Stage Dockerfile for Python Applications
When deploying Python services into production, single-stage builds often inflate image sizes to 1GB+ and leave unnecessary compilers and build tools in the production image. Multi-stage builds solve this.

### Standard Production Dockerfile
```dockerfile
# Stage 1: Build & wheels generation
FROM python:3.12-slim AS builder

WORKDIR /app

# Install native compilation dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Final minimal runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

# Only install runtime libraries without compilers
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy user wheels from builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 2. Resolving the `psycopg2` Docker Build Crash
A frequent roadblock encountered by computer science students is the following terminal error:
```text
Error: pg_config executable not found.
      Failed to build psycopg2
      error: command 'gcc' failed: No such file or directory
```

### Root Cause Analysis
`psycopg2` contains C code that links directly against PostgreSQL's native C client library (`libpq`). In minimal Linux images like `python:3.12-slim` or Alpine, header files (`libpq-dev`) and the C compiler (`gcc`) are absent by default.

### Remediation Strategies
1. **Production Recommended:** Install `libpq-dev` and `gcc` in the builder stage of your Dockerfile:
   ```dockerfile
   RUN apt-get update && apt-get install -y libpq-dev gcc
   ```
2. **Local Prototyping:** Switch your `requirements.txt` dependency from `psycopg2` to `psycopg2-binary`. The binary package ships with pre-compiled wheels, avoiding the requirement for native compilation tools.

---

## 3. Docker Compose Orchestration: Frontend, Backend & Database
To run a complete full-stack system locally with one command:

```yaml
version: '3.8'

services:
  database:
    image: postgres:16-alpine
    container_name: navigator-db
    environment:
      POSTGRES_USER: navigator_user
      POSTGRES_PASSWORD: navigator_password
      POSTGRES_DB: navigator_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U navigator_user -d navigator_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: .
    container_name: navigator-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://navigator_user:navigator_password@database:5432/navigator_db
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    depends_on:
      database:
        condition: service_healthy

volumes:
  pgdata:
```

---

## 4. Beginner-Friendly Production Deployment Checklist
When your app works locally and you are preparing to deploy frontend, backend, and database to production:

### 1. Database Tier
- Deploy a managed database instance (e.g., Supabase, Neon, AWS RDS, or Render PostgreSQL) rather than running a raw container on an unbacked VPS.
- Set up automated daily database backups.
- Run database migrations (`alembic upgrade head`) as a CI/CD build step before new server instances launch.

### 2. Backend Tier
- Store all secrets (`SECRET_KEY`, `GEMINI_API_KEY`, database credentials) strictly in environment variables; never commit `.env` files to GitHub.
- Expose a deterministic `/health` endpoint for load balancers.
- Configure a reverse proxy (e.g. Nginx, Caddy, or Cloudflare) to terminate SSL/TLS certificates (HTTPS).

### 3. Frontend Tier
- Build production assets using `npm run build` or `vite build`.
- Deploy static HTML/CSS/JS bundles to a Content Delivery Network (CDN) such as Vercel, Netlify, or Cloudflare Pages.
- Ensure the production API URL is injected via environment variables (`VITE_API_URL=https://api.yourdomain.com`).
