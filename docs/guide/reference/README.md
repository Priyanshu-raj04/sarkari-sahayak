# Reference repos

These are the two repos whose test suites were run while writing the guide. Every code block marked ✅
in the guide was copied from here automatically.

Use them to **compare after** you have written your own version test-first. Don't copy them wholesale:
you must be able to explain every line in an interview, and your git history should show the work.

They are snapshots, not finished projects: they contain the verified core (text, retrieval, agent, gateway,
service, MCP, rate limiting, UI, Flight Recorder store, ONNX embedder; PII, detectors, proxy, SARIF, CLI,
action, workflows). Milestone glue described in the guide (benchmark runners, deployment files, etc.) is yours to write.
`uv.lock` is deliberately not included; run `uv lock` to create your own.
