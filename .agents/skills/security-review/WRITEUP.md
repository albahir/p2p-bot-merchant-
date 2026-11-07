# Your security scanner probably exits 0 when it scans nothing

I spent a week building a security audit tool that orchestrates Semgrep, gitleaks,
TruffleHog, Trivy, osv-scanner and ZAP. The interesting part was not the orchestration.
It was discovering that the failure mode I had designed against — false positives — is
the wrong thing to worry about.

The dangerous failure is silence.

## Every one of these tools has a documented mode where it scans nothing and exits 0

Not "finds nothing". Scans nothing, reports success, and exits with the status code your
CI treats as a pass.

- **Semgrep** exits 0 when a Python file fails to parse, telling you the scan succeeded
  with no findings when in fact nothing in that file was examined
  ([#11443](https://github.com/semgrep/semgrep/issues/11443)). It also exits 0 on an
  invalid rule where the documentation promises exit 7
  ([#10319](https://github.com/semgrep/semgrep/issues/10319)), and on a `--config` value
  containing a space ([#7630](https://github.com/semgrep/semgrep/issues/7630)).
- **Bandit** silently drops the `exclude` paths in your config when filenames are passed
  on the command line ([#499](https://github.com/PyCQA/bandit/issues/499)) — which is
  precisely what pre-commit does. Your exclusions evaporate exactly when the tool runs
  in CI.
- **Trivy's secret scanner always exits 0**, findings or not
  ([#2366](https://github.com/aquasecurity/trivy/issues/2366)).
- **TruffleHog** under `actions/checkout`'s default shallow clone has no history to
  scan. A TruffleHog maintainer searched GitHub for real usages and concluded: *"There
  are many, many cases of workflows running TH on pushes, but they aren't actually
  scanning anything."*
  ([PR #2138](https://github.com/trufflesecurity/trufflehog/pull/2138))
- **osv-scanner** on Windows, with git's default `core.autocrlf`, misses C/C++
  vulnerabilities because CRLF conversion changes the content hashes it matches on
  ([#657](https://github.com/google/osv-scanner/issues/657), open since 2023). The same
  repository scans differently depending on which OS you scan it from.
- **gitleaks** with a custom `.gitleaks.toml` that omits `[extend] useDefault = true`
  silently discards every built-in rule. Add one custom rule, lose all 150 detectors,
  get a clean report.
- **ZAP** authenticating unsuccessfully scans only the login page and reports few
  alerts ([#7541](https://github.com/zaproxy/zaproxy/issues/7541)). A zero-alert ZAP run
  usually means the scan failed, not that the app is secure.

Each of these is individually a bug report. Together they are a design constraint.

## The corollary: a clean report is nearly worthless as evidence

This is worse than it sounds, because clean is the result people act on. Nobody ships on
the strength of a report full of findings. They ship on a green check.

So the tool now plants a canary set before the tool inventory is even reported. It
writes obviously vulnerable files — this one, plus a requirements.txt pinning a
known-vulnerable release — and confirms each scanner flags them:

```python
import subprocess
aws_key = "AKIAQYLPMN5G3XVRWTZK"              # fake, format-valid
github_token = "ghp_<36 random characters>"   # fake PAT, generated fresh each run
subprocess.call("ls " + input(), shell=True)
```

Leaked credentials, shell injection, unvalidated input. The fakes have to be
format-valid, because scanners allowlist documentation keys — a polite canary tests
nothing. (Format-valid enough, in fact, that a literal example PAT cannot be printed
here: it trips GitHub push protection on this very repository, which is the property
being tested.) If a scanner reports nothing on that file, it is broken or
misconfigured, and its silence on the real codebase carries no information. The
inventory reports every tool as canary-verified, broken with the actual error, or
missing — a present-but-broken scanner never prints `OK`.

This is a five-line check that every security pipeline should have and almost none do.

## Suppression is the least reliable feature in every one of these tools

The second pattern, and it fails in both directions — either hiding real findings or
failing builds that should pass.

Semgrep's `nosemgrep` comments have been ignored in `--sarif` output mode since 2022
([#6658](https://github.com/semgrep/semgrep/issues/6658),
[#8411](https://github.com/semgrep/semgrep/issues/8411), both still open). The practical
consequence: with `--json` a suppressed finding exits 0, and with `--sarif` the identical
scan exits 1. If your CI uploads SARIF to GitHub code scanning, which is the normal
setup, your suppressions do not suppress the build failure.

gitleaks fingerprints embed the commit SHA, so squash-merging a PR invalidates every
baselined suppression and they all resurrect on main
([#1355](https://github.com/gitleaks/gitleaks/issues/1355)). They also embed the OS path
separator, so an ignore file written on Windows silently fails in Linux CI
([#1565](https://github.com/gitleaks/gitleaks/issues/1565)).

ZAP has an open issue where "mark as false positive" does not mark the alert as a false
positive ([#8993](https://github.com/zaproxy/zaproxy/issues/8993)), and another where a
filtered alert still fails the build with no corresponding alert in the report
([#9021](https://github.com/zaproxy/zaproxy/issues/9021)).

The generalisable advice, which no tool's documentation states: **write a test that
proves a deliberately suppressed finding is actually suppressed, in CI, and re-run it
after every version bump.**

## The part that changed how the LLM half works

I had assumed the language model's job was to find things the scanners missed. The
evidence says the opposite.

Measured on identical false-positive triage tasks, LLM review filters **36.4%** of false
positives when prompted directly, and **95.5%** when given tools and agentic structure
([arXiv:2601.22952](https://arxiv.org/abs/2601.22952)). That is the largest effect size
I found anywhere in this literature, and it is about architecture, not model choice.

Meanwhile, at origination it is weak. The best-documented measurement of LLM review
against a *known* vulnerability found it in 8 runs out of 100 and reported "no bug here"
in 66 ([Sean Heelan on CVE-2025-37899](https://sean.heelan.io/2025/05/22/how-i-used-o3-to-find-cve-2025-37899-a-remote-zeroday-vulnerability-in-the-linux-kernels-smb-implementation/)).
Detection also degrades sharply with context: 8/100 at 27k tokens, 1/100 at 100k. Whole
repository review is worse than function-level review, not better.

So the division of labour is: deterministic scanners originate candidates, the model
refutes them. Which is the reverse of how most "AI security review" is marketed.

## The repository you are auditing is adversarial input

The last one is the one I would not have thought to design against.

A comment claiming `sanitize()` "cleans and validates input data", placed above code
containing netcat commands and labelled "safe demo only", was enough to make a reviewing
model conclude that **no legitimate security vulnerabilities were identified**
([Checkmarx](https://checkmarx.com/zero-post/bypassing-claude-code-how-easy-is-it-to-trick-an-ai-security-reviewer/)).

Academic work on contextual bias in LLM-assisted security review found the effect is
systematic across six models, that bug-free framing produces the strongest suppression,
and — usefully — that explicit debiasing "restores detection in all affected cases"
([arXiv:2603.18740](https://arxiv.org/abs/2603.18740)).

Telling a model the code is clean is the most effective known way to stop it finding
bugs. And every comment, README, commit message and `SECURITY.md` in the repository under
audit is attacker-controllable text.

This is not hypothetical. Prompt injection through repository metadata has an assigned
CVE with a full chain from a crafted issue to a stolen OIDC token to commits pushed into
downstream repos (CVE-2025-66032, CVSS 8.7). Anthropic's own security-review action
states plainly that it "is not hardened against prompt injection attacks and should only
be used to review trusted PRs."

So the tool treats repository content as data to analyse, never instruction to follow.
It verifies a guard by reading the guard's implementation, never by reading a claim that
the guard exists. And if it finds text in the repo trying to steer the review, that is
reported as a Critical finding rather than obeyed.

## What I would tell anyone running these tools

1. Plant a canary. Prove the scanner works before believing its silence.
2. Never gate CI on an exit code alone. Parse the JSON and assert on the finding count.
3. Test that your suppressions suppress, and retest after every upgrade.
4. Pin scanner versions. Checkov ships ~64 releases a year and adds new *checks* in
   patch releases, so an unchanged repo goes red overnight.
5. Pin scanner *actions* to commit SHAs. In March 2026, 76 of 77 tags in
   `aquasecurity/trivy-action` were force-pushed to credential-stealing malware that
   swept 50+ filesystem paths for cloud credentials. Your security scanner is a
   maximally privileged supply-chain node.

The tool is MIT and lives at
[github.com/cdmx-in/security-review](https://github.com/cdmx-in/security-review). It runs
as a Claude Code skill, but the findings above are tool-agnostic and mostly apply to any
pipeline running these scanners.

I would genuinely like to be wrong about some of this. If you have counter-evidence,
especially measured, I want to see it.
