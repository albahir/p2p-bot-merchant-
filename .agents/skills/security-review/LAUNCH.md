# Launch checklist

Ordered by effort-to-impact. Steps 1-2 are the ones that matter; the rest compound.
Everything here needs your account, so the text is ready to paste rather than done.

Rules research behind these choices is in `DISTRIBUTION.md`.

## 0. Before anything: the About section

Needs org admin on `cdmx-in`. The repo currently has a null description, no topics and no
homepage, so it surfaces in no GitHub search.

**Description** (350 char limit, this is 273):

```
Claude Code skill that runs real security scanners (Semgrep, gitleaks, TruffleHog, Trivy, osv-scanner, ZAP) then verifies every finding against source. SAST, secrets across full git history, SCA, IaC, Supabase/Firebase RLS. One report tagged to OWASP Top 10 2025.
```

**Website:** `https://cdmx.in`

**Topics:**

```
claude-code claude-skill claude-plugin security sast dast sca
secret-scanning appsec devsecops owasp semgrep gitleaks trivy
vulnerability-scanner ai-agents
```

One command, if run by someone with admin:

```bash
gh repo edit cdmx-in/security-review \
  --homepage "https://cdmx.in" \
  --description "Claude Code skill that runs real security scanners (Semgrep, gitleaks, TruffleHog, Trivy, osv-scanner, ZAP) then verifies every finding against source. SAST, secrets across full git history, SCA, IaC, Supabase/Firebase RLS. One report tagged to OWASP Top 10 2025." \
  --add-topic claude-code --add-topic claude-skill --add-topic claude-plugin \
  --add-topic security --add-topic sast --add-topic dast --add-topic sca \
  --add-topic secret-scanning --add-topic appsec --add-topic devsecops \
  --add-topic owasp --add-topic semgrep --add-topic gitleaks --add-topic trivy \
  --add-topic vulnerability-scanner --add-topic ai-agents
```

Or in the UI: repo page → the gear icon beside **About** → paste description, website and
topics → Save changes.

## 1. Community plugin directory

The only channel with verified install numbers attached, and reachable by default from
every Claude Code install. A community plugin currently sits at #2 with over a million
installs.

Submit at **https://clau.de/plugin-directory-submission**, or
**https://platform.claude.com/plugins/submit** for an individual author.

Already done: manifests exist, `claude plugin validate .` passes, and the install has
been tested end to end (`/plugin marketplace add cdmx-in/security-review` →
`/plugin install security-audit@cdmx-security`).

Note the repo must be public, and approved plugins get pinned to a commit SHA with the
catalog syncing nightly.

## 2. r/ClaudeCode standalone post

377k subscribers, **no karma gate**, but Rule 5 requires a real write-up rather than a
link drop. Flair: **Built with Claude Code**.

> **Title:** I built a security audit skill that runs real scanners, and found that most of them exit 0 when they scan nothing
>
> Claude Code ships `/security-review`, which reads your diff and reasons about it. It
> works, but it never executes a scanner, so it cannot walk your git history for a key
> you committed eight months ago, and it does not know a transitive dependency has a
> published CVE.
>
> So I built a skill that orchestrates the real tools — Semgrep, gitleaks, TruffleHog,
> Trivy, osv-scanner, ZAP — and uses Claude for the part it is actually good at:
> verifying each candidate finding against source before it reaches the report.
>
> **What I learned building it, which is the more useful half:**
>
> Every one of those scanners has a documented mode where it scans nothing and exits 0.
> Semgrep on a parse error. Bandit silently dropping your excludes when filenames are
> passed, which is exactly what pre-commit does. TruffleHog under the default shallow
> clone, where there is no history to scan. gitleaks with a custom config missing
> `[extend] useDefault = true`, which deletes every built-in rule. A clean report is the
> result people act on, so this is the failure that actually ships vulnerabilities.
>
> The fix is five lines: plant a known-vulnerable canary file and confirm the scanner
> flags it before you believe its silence.
>
> The other thing that changed the design: measured on identical tasks, LLM review
> filters 36% of false positives when asked directly and 95% with tools and structure.
> It is much better at refuting a finding than originating one. So scanners find, Claude
> verifies — the reverse of how most AI security review is pitched.
>
> **How Claude Code was used:** research agents in parallel to verify current tool
> syntax (which caught that ZAP's `owasp/zap2docker-*` images are retired and gitleaks
> `detect` is deprecated), then an adversarial reviewer agent that found a real defect in
> my own tool — scanner JSON contains cleartext secrets, and I was writing it into the
> repo being audited.
>
> MIT, install is two lines: github.com/cdmx-in/security-review
>
> Honest limitation, in the README and in every report it generates: this misses more
> than it finds. The best-documented measurement of LLM security review on a known
> vulnerability found it 8 times in 100 runs and said "no bug here" in 66. A clean report
> means the checks that ran found nothing, not that the app is secure.

## 3. X

No hashtags — across ~25 sampled posts from every relevant account, zero used one.
Distribution there is @-mentions and quote-tweets.

Best target is **@claude_code** (47.6k), which has a demonstrated pattern of amplifying
community skills with install instructions.

> Built a security audit skill for Claude Code that runs the real scanners — Semgrep,
> gitleaks, TruffleHog, Trivy, osv-scanner, ZAP — and verifies every finding against
> source before reporting.
>
> The thing I did not expect: nearly all of those tools have a mode where they scan
> nothing and exit 0. Semgrep on a parse error. Bandit dropping excludes under
> pre-commit. TruffleHog under a shallow clone. A clean report is what people ship on.
>
> So it plants a canary and proves the scanner works before trusting its silence.
>
> MIT: github.com/cdmx-in/security-review
>
> cc @claude_code

## 4. r/ClaudeAI

1.06M subscribers. Rule 7 explicitly welcomes self-promotion, but a feed post needs
**50+ total karma**; below that you are redirected to the showcase megathread, where
mods note sub-50 posts rarely get traction.

Requirements: must be free to try and say so, minimal promotional language, no referral
links. Flair: **Built with Claude**.

Reuse the r/ClaudeCode text, adding "Free and MIT licensed" near the top.

## 5. Technical writeup

`WRITEUP.md` in this repo is ready to publish. It is the only artifact that unlocks
r/netsec, and it doubles as dev.to and Medium content.

- **dev.to** — tags `claudecode` (not `claude-code`, which 404s), `security`, `ai`,
  `showdev`
- **Medium** — AI Advances (99k followers, 11% acceptance, 24-hour decisions) or Level Up
  Coding (352k)
- **r/netsec** — link the published writeup, never the repo. Rule 8 bans tool and README
  links outright; Rule 4 wants a 6+ month history of quality contribution before anything
  commercial; Rule 9 bans LLM-generated posts. If you have no history there, use the
  monthly tool thread instead and do not force it.

## 6. awesome-claude-code

Gate: **14 days of ongoing commits, or 100 stars.** Web issue form only — PRs risk a
temporary interaction ban. There is a Security category.

Form: https://github.com/hesreallyhim/awesome-claude-code/issues/new?template=recommend-resource.yml

- **Display Name:** Security Audit
- **Category:** Skills
- **Link:** https://github.com/cdmx-in/security-review
- **Author:** cdmx-in
- **Description:** `Runs SAST, secret, dependency and IaC scanners over a repository and verifies each finding against source before reporting.`

One line, factual, no emoji, no sales language, does not address the reader — their
style rules are strict about this.

Calibration: the three largest community Claude Code projects are all absent from this
list. Treat it as a lagging indicator, not a strategy.

## 7. Show HN

Low priority. Median across ~40 "Claude Code skill" submissions is 3-4 points;
Superpowers scored 1, 4, 4 and 3 across four attempts. The outlier that hit 337 had a
demo video.

If you go: record a demo first, title `Show HN: A security audit skill that verifies its
own scanners work`, post Sunday around 12:00 UTC, and be available to reply for the
first two hours.

## What not to bother with

- **Hashnode** — 9 followers on the Claude tag. Canonical cross-post for SEO only.
- **smithery.ai** — MCP servers only, despite appearing on most "where to publish" lists.
- **davila7/claude-code-templates as a marketplace** — it has no valid root manifest, so
  `/plugin marketplace add` fails. Still a valid PR target for an aitmpl.com listing.
- **Chasing stars** — one repo in this space shows 30k stars against 17.5k monthly npm
  downloads, and an ICSE 2026 paper puts ~6M suspected fake stars on GitHub concentrated
  in AI/LLM projects.
