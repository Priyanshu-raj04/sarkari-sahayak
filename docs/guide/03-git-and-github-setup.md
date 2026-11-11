# 03 — Git & GitHub Setup (both repos)

Goal: two public repos that look and behave like a real team's repos from the very first commit — signed commits, protected `main`, PR-only workflow, labels, milestones, issue/PR templates, a Projects board, Dependabot, security scanning and Pages.

## 1. Names, descriptions and topics

| | Sahayak | Gatekeeper |
|---|---|---|
| Repo slug | `sarkari-sahayak` | `mcp-gatekeeper` |
| Display name (README H1) | **Sarkari Sahayak — सरकारी सहायक** | **MCP Gatekeeper** |
| GitHub "About" (≤ 350 chars) | `Bilingual (Hindi/English) agentic-RAG MCP server over RBI regulations. Cites every answer or refuses. Benchmarked on MIRACL-hi / NoMIRACL / IndicQA, traced with Phoenix, regression-tested with DeepEval in CI.` | `A firewall for MCP tools: tool-hash pinning, argument validation and Indian-PII redaction proxy, a benchmarked poisoned-tool detector (incl. Hindi/Hinglish attacks), red-teaming, and a GitHub Action that fails PRs adding poisoned tools.` |
| Topics | `mcp, model-context-protocol, rag, agentic-rag, langgraph, hindi, indic-nlp, multilingual, rbi, llm-evaluation, deepeval, arize-phoenix, fastmcp, pgvector, bm25` | `mcp, model-context-protocol, ai-security, llm-security, prompt-injection, tool-poisoning, guardrails, red-teaming, promptfoo, sarif, github-actions, pii-redaction, fastmcp, hindi` |
| Website field | Render URL (after S6) | PyPI page `pypi.org/project/mcp-tool-gatekeeper` (after G4) |

## 2. Git identity, SSH auth and signed commits (once per machine)

```bash
git config --global user.name  "Priyanshu Raj"
# Use your GitHub no-reply address (Settings → Emails → "Keep my email private") so your email isn't in public history:
git config --global user.email "<id>+Priyanshu-raj04@users.noreply.github.com"
git config --global init.defaultBranch main
git config --global pull.rebase true
git config --global fetch.prune true
git config --global rerere.enabled true

# One SSH key for both auth and signing
ssh-keygen -t ed25519 -C "Priyanshu-raj04@github" -f ~/.ssh/id_ed25519
eval "$(ssh-agent -s)" && ssh-add --apple-use-keychain ~/.ssh/id_ed25519

git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
git config --global tag.gpgsign true
```

Log in with the GitHub CLI and upload the key twice (once as an **authentication** key, once as a **signing** key):

```bash
gh auth login --hostname github.com --git-protocol ssh --web
gh auth refresh -s project,admin:public_key,admin:ssh_signing_key
gh ssh-key add ~/.ssh/id_ed25519.pub --title "M1 auth"    --type authentication
gh ssh-key add ~/.ssh/id_ed25519.pub --title "M1 signing" --type signing
ssh -T git@github.com     # "Hi Priyanshu-raj04! ..."
```

Verify signing: after your first commit, `git log --show-signature -1` and the "Verified" badge on GitHub.

## 3. Create the repos

Run once per repo (shown for Sahayak; repeat with the Gatekeeper values):

```bash
mkdir -p ~/code && cd ~/code
gh repo create Priyanshu-raj04/sarkari-sahayak \
  --public --license mit --gitignore Python --add-readme \
  --description "Bilingual (Hindi/English) agentic-RAG MCP server over RBI regulations. Cites every answer or refuses." \
  --clone
cd sarkari-sahayak
gh repo edit --add-topic mcp,model-context-protocol,rag,agentic-rag,langgraph,hindi,indic-nlp,multilingual,rbi,llm-evaluation,deepeval,arize-phoenix,fastmcp,pgvector,bm25
```

### Merge settings (squash-only, linear history, auto-delete branches)

```bash
gh repo edit \
  --enable-squash-merge --enable-merge-commit=false --enable-rebase-merge=false \
  --delete-branch-on-merge --enable-auto-merge \
  --enable-issues --enable-projects --enable-wiki=false --enable-discussions=false
```

In **Settings → General → Pull Requests**: "Default commit message for squash merging" → **Pull request title and description**. That makes your PR title (a conventional commit) the commit on `main`.

## 4. Protect `main` with a ruleset

Rulesets are the modern replacement for branch protection and are free on public repos. Create it **after** the Phase-0 skeleton is on `main` and CI has run once (so the `check` status exists).

Save as `ruleset-main.json` (do not commit it):

```json
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" },
    { "type": "required_signatures" },
    { "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true
      } },
    { "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [ { "context": "check" } ]
      } }
  ]
}
```

```bash
gh api -X POST repos/Priyanshu-raj04/sarkari-sahayak/rulesets --input ruleset-main.json
```

⚠️ If the API rejects a field (the REST schema evolves), create the same ruleset in **Settings → Rules → Rulesets → New branch ruleset** with: target default branch; block deletions and force pushes; require linear history; require signed commits; require a PR (0 approvals, since you're solo; resolve conversations); require status check **`check`** (must match the CI job name in `.github/workflows/ci.yml`), "require branches to be up to date".

> Solo-developer note: 0 required approvals is normal for a solo repo; the PR still forces CI + a self-review of the diff.

## 5. Security features (Settings → Code security)

Turn on, all free for public repos:

* **Dependabot alerts** and **Dependabot security updates**.
* **Secret scanning** and **Push protection** (blocks pushes that contain API keys).
* **Code scanning → CodeQL "Default setup"** for Python and Actions.
* **Private vulnerability reporting** (pairs with `SECURITY.md`).

## 6. Labels

```bash
# Remove GitHub defaults you won't use, then create a small, meaningful set.
for l in "good first issue" "help wanted" "invalid" "question" "wontfix" "duplicate"; do gh label delete "$l" --yes 2>/dev/null; done

gh label create "type:feat"     -c 1D76DB -d "New capability"
gh label create "type:fix"      -c D73A4A -d "Bug fix"
gh label create "type:test"     -c 0E8A16 -d "Tests only"
gh label create "type:docs"     -c 0075CA -d "Docs / ADR"
gh label create "type:chore"    -c BFD4F2 -d "Tooling, deps, CI"
gh label create "type:spike"    -c FBCA04 -d "Time-boxed investigation; outcome = ADR or notes"
gh label create "area:ingest"   -c C5DEF5
gh label create "area:retrieval" -c C5DEF5
gh label create "area:agent"    -c C5DEF5
gh label create "area:mcp"      -c C5DEF5
gh label create "area:evals"    -c C5DEF5
gh label create "area:ui"       -c C5DEF5
gh label create "area:infra"    -c C5DEF5
gh label create "run-evals"     -c 5319E7 -d "Run the live LLM eval gate on this PR"
gh label create "blocked"       -c 000000
```

Gatekeeper uses `area:corpus`, `area:detectors`, `area:proxy`, `area:cli`, `area:action`, `area:redteam` instead of the Sahayak areas.

## 7. Milestones

```bash
R=Priyanshu-raj04/sarkari-sahayak
for m in "S0 Bootstrap" "S1 Ingestion" "S2 Retrieval + Benchmarks" "S3 Agent" "S4 MCP Server" "S5 UI + Flight Recorder" "S6 Ship v1.0" "S7 v1.1 Supersession + Marathi"; do
  gh api -X POST repos/$R/milestones -f title="$m"
done
R=Priyanshu-raj04/mcp-gatekeeper
for m in "G0 Bootstrap" "G1 Corpus + Scanner Benchmark" "G2 LLM Judge" "G3 Firewall Proxy" "G4 Red Team + CI + PyPI" "G5 Dogfood + Ship v1.0"; do
  gh api -X POST repos/$R/milestones -f title="$m"
done
```

## 8. Projects board (one board for both repos)

```bash
gh project create --owner Priyanshu-raj04 --title "Measured, Secure, Hindi-capable Agents"
# Note the project number it prints, e.g. 1
gh project link 1 --owner Priyanshu-raj04 --repo Priyanshu-raj04/sarkari-sahayak
gh project link 1 --owner Priyanshu-raj04 --repo Priyanshu-raj04/mcp-gatekeeper
```

In the web UI: switch to **Board** layout with columns `Backlog → Ready → In progress → In review → Done`; add a **Milestone** field grouping; enable the built-in workflow "Item closed → Done" and "PR merged → Done".

## 9. Templates (commit these in the Phase-0 skeleton PR)

### `.github/ISSUE_TEMPLATE/milestone-task.yml`

```yaml
name: Task
description: A unit of work inside a milestone (one PR)
labels: []
body:
  - type: textarea
    id: goal
    attributes: { label: Goal, description: "What and why, in 2–3 sentences." }
    validations: { required: true }
  - type: textarea
    id: acceptance
    attributes:
      label: Acceptance criteria
      description: Testable statements. Each becomes at least one test.
      value: |
        - [ ]
        - [ ]
    validations: { required: true }
  - type: textarea
    id: tests
    attributes: { label: Test plan, description: "Unit / integration / e2e tests to write first." }
  - type: textarea
    id: notes
    attributes: { label: Notes / links }
```

### `.github/ISSUE_TEMPLATE/bug.yml`

```yaml
name: Bug
description: Something is broken
labels: ["type:fix"]
body:
  - type: textarea
    id: what
    attributes: { label: What happened, description: "Include the trace id / request id if you have one." }
    validations: { required: true }
  - type: textarea
    id: repro
    attributes: { label: Steps to reproduce }
    validations: { required: true }
  - type: textarea
    id: expected
    attributes: { label: Expected behaviour }
```

### `.github/pull_request_template.md`

```markdown
## What & why
<!-- 1–3 sentences. Link the issue: Closes #NN -->

## How it was tested
- [ ] New/updated unit tests (written first — TDD)
- [ ] Integration / e2e tests where relevant
- [ ] `make check` passes locally
- [ ] Eval impact: <none | retrieval metrics changed (paste table) | needs `run-evals` label>

## Risk & rollback
<!-- What could break? How do we roll back? -->

## Checklist
- [ ] PR title is a conventional commit (`feat(retrieval): add RRF fusion`)
- [ ] No secrets, no raw PDFs, no personal data
- [ ] Docs/ADR/CHANGELOG updated if behaviour or design changed
```

## 10. Conventions

| Thing | Convention | Example |
|---|---|---|
| Branch | `<type>/<milestone>-<slug>` | `feat/s2-rrf-fusion` |
| Commit / PR title | Conventional Commits | `feat(retrieval): add reciprocal rank fusion` |
| Scopes (Sahayak) | `ingest, retrieval, agent, llm, mcp, api, ui, evals, infra, docs` | |
| Scopes (Gatekeeper) | `corpus, detectors, bench, proxy, pii, cli, action, redteam, infra, docs` | |
| Versioning | SemVer tags `v0.1.0` … `v1.0.0` | `git tag -s v1.0.0 -m "v1.0.0"` |
| Releases | `gh release create v1.0.0 --generate-notes` | |
| PR size | ≤ ~400 changed lines (excluding lockfile/fixtures) | split otherwise |

## 11. Secrets (add when the milestone needs them)

```bash
gh secret set GROQ_API_KEY     --repo Priyanshu-raj04/sarkari-sahayak      # S3
gh secret set GEMINI_API_KEY   --repo Priyanshu-raj04/sarkari-sahayak      # S5 weekly judge job
gh secret set HF_TOKEN         --repo Priyanshu-raj04/sarkari-sahayak      # S2 nightly benchmark (read-only token)
# Render deploy hook (S6) — store as a secret, never in code:
gh secret set RENDER_DEPLOY_HOOK_URL --repo Priyanshu-raj04/sarkari-sahayak
```

Rules: no secret is ever available to workflows triggered by PRs from forks (GitHub's default), so PR CI must work **without** secrets — that's why the PR eval gate uses a local Ollama judge.

## 12. GitHub Pages

Settings → Pages → **Source: GitHub Actions**. Workflows in S5/G4 publish reports with `actions/upload-pages-artifact` + `actions/deploy-pages`.

## Done when

- [ ] Both repos exist, public, MIT, About + topics set
- [ ] First commit on `main` shows **Verified**
- [ ] Squash-only merge, auto-delete branches
- [ ] Ruleset active (after Phase-0 CI ran once) — try `git push origin main` directly: it must be rejected
- [ ] Labels, milestones, Projects board linked
- [ ] Security features on
