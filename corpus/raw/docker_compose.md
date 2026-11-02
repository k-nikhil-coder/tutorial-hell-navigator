# Docker and Docker Compose

## Volumes vs COPY in Multi-stage Builds

Files copied into an image during `docker build` (via `COPY` or `ADD`) are present in the image layers. When a container is started with a volume mount that targets the same path, the volume content **replaces** the image content at that path.

Example:

```dockerfile
# Dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app /app
```

```yaml
# docker-compose.yml
services:
  app:
    build: .
    volumes:
      - ./:/app          # this overwrites everything that was COPYed
```

The `vendor/` or `node_modules/` directory that existed after the build is hidden by the bind mount. Solutions:

1. Do not mount over the path that contains build artifacts in production.
2. Use a named volume only for data that must persist (database, uploads).
3. Mount a sub-directory instead of the whole application root.

## depends_on and Service Readiness

`depends_on` only guarantees that the dependent container has *started*. It does **not** wait for the application inside the container to be ready to accept connections.

```yaml
services:
  db:
    image: postgres:16
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build: .
    depends_on:
      db:
        condition: service_healthy
```

Without a healthcheck the app often receives "connection refused" because Postgres is still initializing.

## Build-time Dependencies

Docker Compose has no built-in way to start services *during* an image build. `depends_on` is a runtime directive only.

Common work-arounds:

- Split the workflow into a Makefile or shell script that starts the required services first, then runs `docker compose build`.
- Use a multi-stage build that does not need a live service (copy static data into the image).
- Generate API clients or static sites at container *start* time rather than build time.

## Multi-stage Builds for Smaller Images

Compilers and development headers (gcc, libpq-dev, python3-dev) should live only in a builder stage:

```dockerfile
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
```

The final image contains only the runtime shared library `libpq5`, not the compiler toolchain.
