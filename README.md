# Kestrel MCP Gateway

Enterprise MCP Tool Gateway for Kestrel Logistics. Exposes warehouse management,
transport, ticketing, and contracts operations as MCP tools behind a single
gateway with team-scoped authorization, rate limiting, audit logging, and a
kill switch for emergency tool disablement.

## Quick Start

1. **Copy the environment file**
   ```bash
   cp .env.example .env
   ```
2. **Build and start all services**
   ```bash
   docker compose up --build
   ```
3. **Connect** -- the gateway is available at `http://localhost:8080`.
4. **Caller identity** -- every request must include headers:
   - `X-Team` -- team identifier (e.g. `warehouse-ops`)
   - `X-User-Id` -- individual user id
   - `X-Scope` -- permission scope (e.g. `read`, `write`)
5. **Kill switch** -- edit `kill_switch.json` at the project root to disable
   individual tools at runtime without restarting the gateway.

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
src/
  kestrel_gateway/
    auth/          # Context extraction, policy enforcement, approval gates
    clients/       # HTTP clients for downstream systems (WMS, TMS, etc.)
    config/        # Settings, team definitions, kill switch loader
    middleware/     # Rate limiter, audit logger, sanitizer, kill switch check
    models/        # Pydantic request / response / error models
    server.py      # MCP server assembly and tool registration
    __main__.py    # Entrypoint
  stubs/           # Lightweight FastAPI stub servers for local development
tests/             # Pytest suite
```
