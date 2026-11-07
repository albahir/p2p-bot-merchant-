<div align="center">

# Security Audit

**A Claude Code skill that runs real security scanners — then verifies every finding against source.**

[![Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fcdmx-in%2Fsecurity-review%2Fmain%2F.claude-plugin%2Fplugin.json&query=%24.version&prefix=v&label=version&color=informational)](.claude-plugin/plugin.json)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-8A63D2)](https://code.claude.com/docs/en/plugins)
[![OWASP Top 10](https://img.shields.io/badge/OWASP-Top%2010%3A2025-000000)](https://owasp.org/Top10/2025/)
[![Always-on cost](https://img.shields.io/badge/context%20cost-~174%20tokens-brightgreen)](#cost)

<img src="assets/demo.svg" alt="security-audit terminal demo" width="680">

```
/plugin marketplace add cdmx-in/security-review
/plugin install security-audit@cdmx-security
```

<sub>Built and maintained by <a href="https://cdmx.in">Codemax IT Solutions Pvt. Ltd.</a></sub>

</div>

---

## Why this exists

Claude Code already ships `/security-review`, and it is good at what it does — an LLM
reads the diff on your branch and reasons about it. What it does not do is execute a
scanner. It cannot walk your git history for a key you committed eight months ago, it
does not know a transitive dependency has a published CVE, and it never touches a running
app.

The tools that *do* execute scanners are single-domain. The Semgrep plugin runs Semgrep.
A gitleaks skill runs gitleaks. Nobody orchestrates all of them, merges the output, kills
the false positives, and hands back one ranked report.

That gap is what this fills.

| | |
|---|---|
| **Scanners find** | Semgrep, gitleaks, TruffleHog, Trivy, osv-scanner, Checkov, ZAP, nuclei and the language-native tools produce candidates |
| **Claude verifies** | Each candidate is traced to real code before it reaches the report. Untraceable findings are discarded, and the report says how many |
| **You get one report** | Ranked by exploitability, tagged to OWASP Top 10 2025, with an optional evidence appendix for ISO 27001, ISO 42001, GDPR and DPDPA |

That division of labour is not stylistic. Measured on identical tasks, LLM review filters
**36%** of false positives when asked directly and **95%** when given tools and structure.
It is far better at refuting a finding than originating one — so the scanners originate.

## Coverage

| Domain | Tools |
|---|---|
| **SAST** | Semgrep, Bandit, gosec, Brakeman |
| **Secrets** | gitleaks, TruffleHog — full git history, not just the working tree |
| **Dependencies** | osv-scanner, Trivy, govulncheck, npm/pnpm audit, pip-audit, Grype, Syft, cargo/composer/bundler/dotnet |
| **IaC & containers** | Trivy, Checkov, Hadolint, zizmor for CI workflows |
| **BaaS config** | Supabase row-level security, Firebase rules |
| **Stack-specific** | Postgres, Redis, React, Next.js, Go, Node/Express |
| **LLM features** | OWASP LLM Top 10 2026, agentic tool-calling review |
| **DAST** | OWASP ZAP, nuclei — opt-in, behind an authorization gate |
| **Compliance** | OWASP 2025, ISO 27001:2022, ISO 42001:2023, GDPR, India DPDPA 2023 |

Every tool is free and open source. No account or licence is required for any of them.
Nothing is installed without asking, and each phase has a documented grep-based fallback
so a missing tool degrades the audit rather than stopping it.

## Built for how AI-generated code actually fails

The manual checklist is ranked by measured frequency from three independent 2025 audits,
not by intuition.

> In a 50-app audit, **88%** had row-level security missing or disabled and **78%** had
> secrets compiled into the client bundle. In a separate study of 434 findings, missing
> rate limiting was the largest single class and broken authorization the second.

These are configuration failures, not code-logic bugs — which is exactly why an AI
generator ships them (nothing about a missing ownership check stops the feature working)
and exactly why plain SAST does not catch them.

## It verifies the scanners before trusting them

Every scanner here has a documented mode where it **scans nothing and exits 0**: Semgrep
on a parse error, Bandit dropping its excludes when filenames are passed (which is what
pre-commit does), TruffleHog under a shallow clone, gitleaks with a custom config missing
`useDefault`.

A clean report is the result people act on, so before the tool inventory is even
reported, the skill plants a known-vulnerable canary set — fake credentials, a shell
injection, a pinned vulnerable dependency — and runs every present scanner against it.
The inventory records each tool as canary-verified, broken (with the actual error), or
missing, and a broken host install falls back to the tool's official Docker image
before anything degrades to grep.

## The repo under audit is treated as hostile input

A comment claiming `sanitize()` "cleans and validates input data", sitting above code that
does nothing of the sort, has been shown to make a reviewing model conclude no
vulnerability exists. Telling a model the code is clean is the most effective known way to
stop it finding bugs — and every comment, README and config file in the audited repo is
attacker-controllable.

So guards are verified by reading the guard's implementation, never by reading a claim
that one exists. Instructions embedded in repository content are reported as a finding
rather than followed.

## Install

**As a plugin** (recommended):

```
/plugin marketplace add cdmx-in/security-review
/plugin install security-audit@cdmx-security
```

**Or install the skill directly**, if you would rather not add a marketplace:

```powershell
git clone https://github.com/cdmx-in/security-review.git
cd security-review
./install.ps1          # macOS/Linux: ./install.sh
```

Either way, restart Claude Code after a first-time install.

## Use

| Command | Scope |
|---|---|
| `/security-audit` | Full static audit |
| `/security-audit --quick` | Secrets and SAST, working tree only |
| `/security-audit --secrets` | Full git history |
| `/security-audit --code` | SAST only |
| `/security-audit --deps` | Dependencies and supply chain |
| `/security-audit --config` | IaC, containers, BaaS, headers |
| `/security-audit --llm` | OWASP LLM Top 10 |
| `/security-audit --diff` | Only what changed against the base branch |
| `/security-audit --compliance` | Adds the framework evidence appendix |
| `/security-audit --dast <url>` | Dynamic scan, requires authorization |
| `/security-audit --fix` | Remediate, after a report exists |

Flags combine: `/security-audit --diff --compliance`. Output lands in
`SECURITY-AUDIT-<date>.md`.

## Cost

`~174 tokens` added to every session. The body (~8.3k) loads only when the skill fires,
and the reference files load only when their phase runs.

## Scanning things you do not own

Static analysis reads your code and is safe anywhere. Dynamic scanning sends real traffic,
and active scanning sends real attack payloads — legally indistinguishable from an attack.

The skill proceeds automatically only against `localhost`, `127.0.0.1` and
`host.docker.internal`. Any other host requires you to state that you own the target or
hold written authorization. It will not infer that from context. Even on loopback it asks
before an active scan, because a tunnel or port-forward can put production behind
`localhost`.

## Limits

Read this part. Security tools that overclaim are worse than none, because people stop
looking.

- **It misses more than it finds.** The best-documented measurement of LLM security review
  on a *known* vulnerability found it in **8 runs out of 100**, and reported "no bug here"
  in **66**. A clean report means the checks that ran found nothing — not that the
  application is secure.
- **Results are not reproducible.** Two runs can produce two different finding sets. That
  matters specifically for compliance evidence, and the report says so.
- **Findings skew low and medium.** AI-assisted review has not in practice been what
  catches critical flaws in hardened code.
- **Runtime behaviour is invisible.** A dependency that pulls its payload at install or
  execution time has nothing malicious in the repo to read.
- **Not a penetration test, not a certification.** Business-logic flaws, chained exploits
  and anything needing creative attacker reasoning need a human. The compliance appendix
  produces evidence supporting controls; certification additionally requires a management
  system, policies and risk assessments no scanner can produce.

Longer form, with citations: [WRITEUP.md](WRITEUP.md).

## Repository

| Path | What |
|---|---|
| [`security-audit/SKILL.md`](security-audit/SKILL.md) | The orchestrator |
| [`security-audit/references/`](security-audit/references/) | Eleven reference files, loaded on demand per phase |
| [`WRITEUP.md`](WRITEUP.md) | Why silence is the failure mode worth designing against |
| [`DISTRIBUTION.md`](DISTRIBUTION.md) | Verified publishing channels and their rules |
| [`LAUNCH.md`](LAUNCH.md) | Launch checklist |

## Contributing

Issues and pull requests welcome. Corrections to tool syntax are especially valuable —
scanner flags change often, and stale flags fail silently rather than erroring.

If you have counter-evidence to anything in the limits section, particularly measured
data, please open an issue. Being wrong about this in public is more useful than being
confidently wrong in private.

## Licence

MIT — see [LICENSE](LICENSE).

<div align="center">
<sub>

**[Codemax IT Solutions Pvt. Ltd.](https://cdmx.in)**

</sub>
</div>
