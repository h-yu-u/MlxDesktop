# ADR-002: Python Supervisor and one active Worker

Status: Accepted

FastAPI Supervisor owns HTTP, persistence, jobs and event delivery. One subprocess Worker owns the active model. Supervisor and Worker communicate with versioned NDJSON. A Worker is terminated when deterministic memory release is required.
