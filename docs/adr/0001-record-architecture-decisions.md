# 1. Record architecture decisions
Date: 2026-11-10 · Status: Accepted

## Context
We need a lightweight, reviewable record of why the system looks the way it does.

## Decision
We use Architecture Decision Records (Michael Nygard format): Context → Decision → Consequences.
One file per decision in docs/adr/, numbered, never edited after Accepted (supersede instead).

## Consequences
Every non-obvious choice (DB, model, hosting, protocol) gets an ADR in the PR that introduces it.
