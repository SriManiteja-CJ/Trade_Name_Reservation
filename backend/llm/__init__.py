"""
llm/__init__.py
LLM gateway and client package for the Trade Name Intelligence Service.

Contains:
  - schemas.py   — Pydantic v2 LLM output schema (spec §4.2)
  - prompts.py   — Prompt loading, versioning, caching
  - gateway.py   — Timeout, retry, circuit breaker, cache, audit write
  - client.py    — Async LlmClient protocol
"""
