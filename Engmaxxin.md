1. Containerized local stack with Docker Compose: Makes backend, frontend, proxy, DB, cache, broker, and LLM reproducible across machines.
2. Nginx as single ingress: One public entrypoint (localhost) that routes UI and API cleanly, simplifies browser CORS/cookie behavior, and mirrors production ingress patterns.
3. Loopback-only published ports (127.0.0.1): Reduces accidental LAN exposure during local development.
4. Service decomposition (web/api/llm/data infra): Separates concerns so each service can scale, fail, and evolve independently.
5. LLM sidecar via llama.cpp + GGUF: Enables free/self-hosted inference without paid dependency.
6. Provider failover (local LLM -> OpenAI if key exists): Keeps advisory available when local model fails.
7. Strict LLM output validation: Prevents malformed advice by requiring mandatory sections and CAD down-payment formatting.
8. Deterministic fallback advisor: Avoids hard failures and always returns a usable recommendation under outages/timeouts/invalid generations.
9. Advisory orchestrator pattern: Centralizes prompting, validation, fallback, market context, caching, and trace/event emission in one flow.
10. Market data abstraction + cached snapshot + stale flag: Uses free public indicators while degrading gracefully when data refresh fails.
11. Monte Carlo simulation backbone: Quantifies uncertainty instead of giving single-point deterministic outputs.
12. Deterministic seeding for simulation: Makes runs reproducible for testing/debugging/audit.
13. Config-driven policy thresholds (env-based): Lets you tune risk posture (buy/wait gates, emergency months, down payment %) without code changes.
14. Machine-readable diagnostics for verdict gates: Explains exactly why verdict is “wait” (which gate failed), improving trust and debuggability.
15. Idempotency keys on execute: Prevents duplicate executions from retries/network glitches.
16. Execution preview TTL: Limits stale execution intents and reduces accidental outdated actions.
17. Contract-first typed API models (Pydantic): Enforces schema validation and safer evolution of endpoints.
18. Auth and ownership boundaries: Bearer token + scenario ownership check prevent cross-user scenario access.
19. Decision trace persistence model: Captures model/policy context and inputs for explainability/audit.
20. Event emission for lifecycle milestones: Supports observability, analytics, and future async workflows.
Frontend default action = advisor brief, graph secondary: Optimizes for user intent (clear decision first, quant detail second).
21. Production-parity placeholders (Postgres/Redis/Redpanda in compose): Lets you prototype now while keeping migration path to persistent, scalable infra clear.