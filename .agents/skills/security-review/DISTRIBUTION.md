# Distribution checklist

Ordered by effort-to-impact. Cheapest and highest impact first.

Verification status is marked inline. `VERIFIED` means I read it on the source page or
parsed the actual file. `UNVERIFIED` means I did not confirm it and it must be checked
before acting on it.

---

## Current repo state (VERIFIED via `gh api repos/cdmx-in/security-review`)

```json
{"description": null, "topics": [], "homepage": null,
 "stars": 0, "created": "2026-08-05T18:29:07Z", "license": "MIT"}
```

The repo has no description, no topics, and no homepage. It does not appear in GitHub
search results for any relevant query (VERIFIED: searched `claude code security audit`,
`topic:claude-code security`, and `cdmx-in`, it ranks nowhere in the top results).

Two other facts that shape everything below:

1. The repo is named `security-review`. Claude Code ships a built-in `/security-review`
   command (VERIFIED, the README acknowledges this). Every search for "claude code
   security review" resolves to Anthropic's own docs and the built-in feature, not to
   this repo. The skill inside is named `security-audit`, so repo name and product name
   already disagree.
2. `oa.yaml` (2.8 MB) sits untracked in the working tree and is not in `.gitignore`.
   If a plugin `source` points at the repo root it gets copied into every user's plugin
   cache. Delete it or ignore it before publishing.

---

## Tier 0: minutes, largest single gain

### 0.1 Set the GitHub description and topics

Topic sizes measured with the GitHub search API (VERIFIED, `total_count` per topic):

```
claude-code           56255
agent-skills          13733
claude-skills          6502
devsecops              5529
claude-code-plugin     4887
claude-skill           4225
owasp                  2828
security-audit         2351
claude-code-skill      2118
claude-plugin          1643
appsec                 1605
claude-code-skills     1383
sast                   1203
```

GitHub allows 20 topics. Set these:

```bash
gh repo edit cdmx-in/security-review \
  --description "Claude Code skill that runs a real security audit: Semgrep, gitleaks, TruffleHog, Trivy, osv-scanner, Checkov, ZAP. Verified findings, one OWASP-tagged report." \
  --add-topic claude-code \
  --add-topic claude-skills \
  --add-topic claude-code-skill \
  --add-topic claude-skill \
  --add-topic agent-skills \
  --add-topic claude-code-plugin \
  --add-topic security-audit \
  --add-topic sast \
  --add-topic sca \
  --add-topic appsec \
  --add-topic devsecops \
  --add-topic owasp \
  --add-topic semgrep \
  --add-topic gitleaks \
  --add-topic secret-scanning \
  --add-topic vulnerability-scanner
```

A null description means GitHub search has almost no text to match on beyond the README.
This is the single cheapest fix in this document.

### 0.2 Decide the name collision

`security-review` competes directly with a built-in Claude Code command name. Options,
in order of preference:

1. Rename the repo to `security-audit` or `claude-security-audit`. GitHub issues a
   permanent redirect from the old path, so existing clone URLs keep working
   (UNVERIFIED for this specific repo, but this is standard GitHub rename behaviour).
   This aligns repo name, skill name, and invocation.
2. Keep the repo name and rely on topics plus description. Weaker.

Competitors already occupy the obvious names (VERIFIED via GitHub search):

```
6464 stars  trailofbits/skills            Trail of Bits Claude Code skills for security research
2083 stars  0xSteph/pentest-ai-agents     offensive security research assistant
 405 stars  aiskillstore/marketplace      Security-audited skills for Claude, Codex & Claude Code
 293 stars  HarmonicSecurity/claudit-sec  Security audit tool for Claude Desktop and Claude Code
 275 stars  PlamenTSV/plamen              Autonomous Web3 security audit agent
   0 stars  velimattiv/claude-security-audit  polyglot multi-phase security audit skill
```

`velimattiv/claude-security-audit` is the closest positional competitor: same scanner
bundle, same OWASP tagging, 0 stars, 12 topics set, no marketplace file, no demo media
(VERIFIED by fetching the repo). It is not winning yet. The category is open.

---

## Tier 1: one hour, unlocks every distribution channel below

Nothing else in this document works until the repo is installable as a plugin. The
marketplace submission forms, the community catalog, and every aggregator site key off
`.claude-plugin/marketplace.json`.

### 1.1 The marketplace.json schema

Required fields, from the official docs at
`https://code.claude.com/docs/en/plugin-marketplaces` (VERIFIED):

| Field     | Type   | Notes |
|-----------|--------|-------|
| `name`    | string | Marketplace identifier, kebab-case, no spaces. Public facing. One marketplace per name per user. |
| `owner`   | object | `name` required. `email` and `url` optional. |
| `plugins` | array  | Each entry requires `name` and `source`. |

Optional marketplace fields (VERIFIED from the same page): `$schema`, `description`,
`version`, `metadata.pluginRoot`, `allowCrossMarketplaceDependenciesOn`, `renames`.

Required per plugin entry: `name`, `source`. Optional per entry: `displayName`,
`description`, `version`, `author`, `homepage`, `repository`, `license`, `keywords`,
`metadata`, `category`, `tags`, `strict`, `relevance`, `defaultEnabled`, plus the
component path fields `skills`, `commands`, `agents`, `hooks`, `mcpServers`, `lspServers`.

Source types (VERIFIED): relative path string starting with `./`, or an object with
`source` set to `github` (`repo`, `ref?`, `sha?`), `url` (`url`, `ref?`, `sha?`),
`git-subdir` (`url`, `path`, `ref?`, `sha?`), or `npm` (`package`, `version?`, `registry?`).

Reserved marketplace names that will be rejected (VERIFIED, quoted from the docs):
`claude-code-marketplace`, `claude-code-plugins`, `claude-plugins-official`,
`claude-plugins-community`, `claude-community`, `anthropic-marketplace`,
`anthropic-plugins`, `agent-skills`, `anthropic-agent-skills`, `knowledge-work-plugins`,
`life-sciences`, `claude-for-legal`, `claude-for-financial-services`,
`financial-services-plugins`, `first-party-plugins`, `healthcare`. Names that impersonate
official marketplaces are also blocked.

### 1.2 Real working example, quoted verbatim

Fetched from `https://raw.githubusercontent.com/anthropics/skills/main/.claude-plugin/marketplace.json`
(VERIFIED, this is the live file, truncated after the first plugin entry):

```json
{
  "name": "anthropic-agent-skills",
  "owner": {
    "name": "Keith Lazuka",
    "email": "klazuka@anthropic.com"
  },
  "metadata": {
    "description": "Anthropic example skills",
    "version": "1.0.0"
  },
  "plugins": [
    {
      "name": "document-skills",
      "description": "Collection of document processing suite including Excel, Word, PowerPoint, and PDF capabilities",
      "source": "./",
      "strict": false,
      "skills": [
        "./skills/xlsx",
        "./skills/docx",
        "./skills/pptx",
        "./skills/pdf"
      ]
    }
  ]
}
```

Second real example, from `https://raw.githubusercontent.com/anthropics/claude-code/main/.claude-plugin/marketplace.json`
(VERIFIED, truncated):

```json
{
  "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
  "name": "claude-code-plugins",
  "version": "1.0.0",
  "description": "Bundled plugins for Claude Code including Agent SDK development tools, PR review toolkit, and commit workflows",
  "owner": {
    "name": "Anthropic",
    "email": "support@anthropic.com"
  },
  "plugins": [
    {
      "name": "agent-sdk-dev",
      "description": "Development kit for working with the Claude Agent SDK",
      "source": "./plugins/agent-sdk-dev",
      "category": "development"
    }
  ]
}
```

Note the two differ: the first puts `description` and `version` under `metadata`, the
second puts them at top level. The docs state both are accepted, with `metadata` kept
for backward compatibility (VERIFIED).

### 1.3 Concrete file for this repo

Current layout is `security-review/security-audit/SKILL.md` plus
`security-audit/references/*.md`. `SKILL.md` already sits at the root of the
`security-audit/` directory, so that directory can serve as the plugin root with zero
file moves.

Create `.claude-plugin/marketplace.json` at the repo root:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
  "name": "cdmx-security",
  "description": "Security tooling for Claude Code from cdmx.in",
  "owner": {
    "name": "cdmx-in",
    "url": "https://github.com/cdmx-in"
  },
  "plugins": [
    {
      "name": "security-audit",
      "source": "./security-audit",
      "description": "Runs a full security audit using real scanners (Semgrep, gitleaks, TruffleHog, Trivy, osv-scanner, Checkov, ZAP, nuclei), verifies each finding against source, and produces one severity-ranked report tagged to OWASP Top 10 2025.",
      "version": "1.0.0",
      "author": { "name": "cdmx-in" },
      "homepage": "https://github.com/cdmx-in/security-review",
      "repository": "https://github.com/cdmx-in/security-review",
      "license": "MIT",
      "category": "security",
      "keywords": ["security", "sast", "sca", "secrets", "owasp", "dast", "compliance"]
    }
  ]
}
```

Do not use `"source": "./"` here. That would copy the entire repo, including `oa.yaml`,
into every user's plugin cache.

Also create `security-audit/.claude-plugin/plugin.json`. The docs say the manifest is
optional when components use default locations, but the community marketplace review
pipeline runs `claude plugin validate`, so ship it:

```json
{
  "name": "security-audit",
  "description": "Runs a full security audit using real scanners, verifies findings against source, and produces one severity-ranked OWASP-tagged report.",
  "version": "1.0.0",
  "author": { "name": "cdmx-in" },
  "homepage": "https://github.com/cdmx-in/security-review",
  "license": "MIT"
}
```

Warning about `.claude-plugin/` contents (VERIFIED, quoted from the docs): "Don't put
`commands/`, `agents/`, `skills/`, or `hooks/` inside the `.claude-plugin/` directory.
Only `plugin.json` goes inside `.claude-plugin/`."

### 1.4 Invocation name caveat

Plugin skills are namespaced as `/plugin-name:skill-name` (VERIFIED). With a plugin named
`security-audit` containing a skill named `security-audit`, the invocation is most likely
`/security-audit:security-audit`, which is redundant. The docs also state that a plugin
shipping exactly one skill can place `SKILL.md` at the plugin root and that Claude Code
"uses the frontmatter `name` field for the invocation name", which may or may not skip the
namespace prefix. `UNVERIFIED`: I did not run this. Test locally before publishing:

```bash
claude --plugin-dir ./security-audit
# then in session, check /help > Custom commands for the actual name
```

If it resolves to `/security-audit:security-audit`, rename the marketplace plugin entry
to something like `cdmx-security` so the invocation reads `/cdmx-security:security-audit`.

### 1.5 Validate

```bash
claude plugin validate ./security-audit
```

VERIFIED from the docs: passing prints `✔ Validation passed`, or
`✔ Validation passed with warnings`. Warnings do not fail validation. Add `--strict` to
treat warnings as errors. The community marketplace review pipeline runs this same check.

### 1.6 Result

Once merged, this works for anyone:

```
/plugin marketplace add cdmx-in/security-review
/plugin install security-audit@cdmx-security
```

VERIFIED: `owner/repo` shorthand is the documented GitHub form for
`/plugin marketplace add`, and it requires `.claude-plugin/marketplace.json` at the
repository root.

Add both lines to the README install section. Keep the existing `install.sh` and
`install.ps1` for users who want the plain skill without the plugin wrapper.

---

## Tier 2: official Anthropic channels

### 2.1 Community marketplace, `claude-community`

This is the highest-value listing available, and individual developers can submit.

VERIFIED, quoted from `https://code.claude.com/docs/en/plugins`:

> To submit your plugin for community-marketplace review, use one of the in-app forms:
> claude.ai: claude.ai/admin-settings/directory/submissions/plugins/new
> Console: platform.claude.com/plugins/submit
> The claude.ai form requires a Team or Enterprise organization and directory management
> access; organization Owners have this access by default. Individual authors who aren't
> part of a Team or Enterprise organization can use the Console form instead.

So the path for an individual is:

```
https://platform.claude.com/plugins/submit
```

Requires a Developer, Admin, or Owner role on a Console organization. Sign up free at
`https://platform.claude.com` (VERIFIED from `https://claude.com/docs/plugins/submit`).

Requirements (VERIFIED): the repo must be public, closed-source plugins are not accepted,
and `claude plugin validate` must pass. After approval the plugin is pinned to a commit
SHA in the catalog and CI bumps the pin automatically as you push. You do not resubmit
for updates. The public catalog syncs nightly, so expect a delay between approval and
appearance.

Users then install with:

```
/plugin marketplace add anthropics/claude-plugins-community
/plugin install security-audit@claude-community
```

Do not open a PR against `anthropics/claude-plugins-community`. VERIFIED from the repo
README: it is a read-only mirror and "Pull requests opened directly against this
repository are closed automatically".

Competition in that catalog, measured by parsing the live
`.claude-plugin/marketplace.json` (VERIFIED, 1.58 MB file):

```
total plugins in claude-community: 2298
entries mentioning "security":      203
```

Crowded but the bar is automated validation plus safety screening, not curation.

### 2.2 Official marketplace, `claude-plugins-official`

There is no application process. VERIFIED, quoted from
`https://code.claude.com/docs/en/plugins`:

> The official marketplace, `claude-plugins-official`, is curated separately. Anthropic
> decides which plugins to include at its discretion. There is no application process,
> and the submission form does not add plugins to the official marketplace.

The docs also note that Anthropic already ships a `security-guidance` plugin in the
official marketplace covering automatic per-change security review (VERIFIED). That is
adjacent to this skill but not the same job, since it does not execute scanners.

Do not spend effort here. Getting into `claude-community` and accumulating install counts
is the only visible input to official curation.

### 2.3 claude.com/plugins directory

VERIFIED by fetching the page: a browsable, searchable directory that displays install
counts per plugin and an "Anthropic verified" badge where applicable. It shows a "Submit
your plugin" section reading "Share your plugin with the Claude community. We'll review
it for the directory". Pagination indicated 4 pages.

```
https://claude.com/plugins
```

This is the web surface of the same directory reached by the Console form in 2.1. One
submission covers both. Install counts are public, which makes this the best available
adoption metric.

### 2.4 anthropics/skills

`https://github.com/anthropics/skills`, 166.6k stars (VERIFIED). It has no
`CONTRIBUTING.md`; the raw URL returns HTTP 404 (VERIFIED). The README carries a
disclaimer that the skills are "provided for demonstration and educational purposes only".

There is no external contribution path. Skip it.

---

## Tier 3: third-party directories and marketplaces

### 3.1 Skill Store

VERIFIED by fetching `https://github.com/aiskillstore/marketplace` (405 stars, 41 forks).
Submission is by web form, not PR. Quoted mechanics from the README:

```
1. Visit https://skillstore.io/submit
2. Enter your GitHub repository URL containing SKILL.md
3. Automated security analysis runs
4. Maintainer review and approval
5. Publication to the marketplace
```

PRs adding skills are closed. Requirements: `SKILL.md` per the Agent Skills spec,
supporting files, LICENSE recommended. This repo already satisfies all three.

Install path once listed:

```bash
npx skillstore add cdmx-in/security-audit
```

Positioning note: Skill Store brands itself as "security-audited skills". A security
audit skill listed there is on-theme.

### 3.2 claudemarketplaces.com

VERIFIED by fetching the site: claims 23,600+ skills, 2,600+ marketplaces, 12,700+ MCP
servers, and 380,000+ monthly visitors. Self-describes as independent and not affiliated
with Anthropic. Last updated 2026-08-06.

```
https://claudemarketplaces.com
```

`UNVERIFIED`: whether listing is automatic scraping of GitHub or requires submission. No
submit form was visible on the landing page. The scale of the index (23,600 skills)
strongly suggests automated crawling, in which case setting the topics in Tier 0.1 and
adding `marketplace.json` in Tier 1 is what gets you indexed. The site does sell paid
promotional slots.

### 3.3 Aggregators observed but not verified for submission mechanics

All of these surfaced in search results with Claude Code skill and plugin listings.
`UNVERIFIED` for every one of them: submission process, acceptance criteria, and traffic.

```
https://www.claudepluginhub.com
https://www.claudedirectory.org
https://awesomeskill.ai
https://mcpmarket.com/tools/skills
https://skills.rest
https://lobehub.com/skills
https://www.aitmpl.com          (davila7/claude-code-templates)
```

Most appear to be auto-generated indexes over public GitHub repos and marketplace files,
which again means Tier 0 and Tier 1 are the actual levers. Check each for a submit form
before spending time on manual outreach.

### 3.4 Community marketplaces worth adding to

`UNVERIFIED` across the board: I did not read the contribution files for any of these,
so treat the names as leads, not instructions.

- `davila7/claude-code-templates`, the repo behind aitmpl.com. Widely referenced.
  `UNVERIFIED`: directory layout for a new skill and whether a PR template exists.
- `wshobson/agents` and `wshobson/commands`. `UNVERIFIED`: whether external
  contributions are accepted at all.
- `hesreallyhim/awesome-claude-code`. `UNVERIFIED`: current submission mechanics. It
  historically used a structured data file plus a helper command rather than free-form
  README edits, so read `CONTRIBUTING.md` before opening a PR.
- `travisvn/awesome-claude-skills` and `ComposioHQ/awesome-claude-skills`. Both have
  active PR queues (VERIFIED only in the sense that PR pages exist). `UNVERIFIED`:
  acceptance criteria.

For each, the correct first step is the same: read `CONTRIBUTING.md`, follow the exact
format used by existing entries, one PR per list, and do not batch-spam them on the same
day.

---

## Tier 4: community channels

### 4.1 Hacker News, Show HN

VERIFIED by fetching `https://news.ycombinator.com/showhn.html`. Quoted:

> Show HN is for something you've made that other people can play with.

> Off topic: blog posts, sign-up pages, newsletters, lists, and other reading material.

> Please don't ask friends to upvote or comment. That's not ok on HN.

The work must be non-trivial, something you worked on personally, and easy to try
"without barriers such as signups or emails". This skill qualifies: it is MIT, installs
in one command, and needs no account.

`UNVERIFIED`: optimal posting time. The commonly repeated advice is weekday mornings US
Eastern, but I did not verify this against 2026 data. Do not treat it as fact.

Preconditions before posting: Tier 0 and Tier 1 complete, README shows a real report
excerpt, and the one-line install works on a clean machine. A Show HN that lands on a
repo with a null description converts nothing.

### 4.2 Reddit

`UNVERIFIED`. I could not retrieve the rules. `old.reddit.com/r/ClaudeAI/about/rules`
returned "You've been blocked by network security" through the browser tool, and I will
not paraphrase subreddit rules from memory.

Read these manually before posting:

```
https://www.reddit.com/r/ClaudeAI/about/rules/
https://www.reddit.com/r/ClaudeCode/about/rules/
https://www.reddit.com/r/netsec/about/rules/
```

r/netsec in particular is known for strict submission filtering; check its rules
carefully, since a tool launch may not qualify there at all. Several Claude subreddits
run scheduled showcase threads rather than allowing standalone promo posts. Confirm
whether one exists before posting a top-level thread.

### 4.3 Discord

`UNVERIFIED`. I did not confirm an official Anthropic or Claude Developers Discord invite
URL. Do not post an invite link you have not opened yourself. If one exists, find it
linked from `https://claude.com` or the Claude Code docs footer rather than from a
third-party blog.

### 4.4 X/Twitter, dev.to

`UNVERIFIED` for all of it: which accounts amplify Claude Code tooling in 2026, which
hashtags carry traffic, and whether dev.to has an active Claude Code tag or publication.
I did not verify any of this. Treat as unresearched.

---

## What actually drives adoption

Honest scope note: `UNVERIFIED` for the general claim. I found no retrospective or
dataset analysing why specific Claude Code skills became popular. What follows is
inference from the comparative repo data I did collect, not evidence.

What the data does show:

1. Discovery is mechanical before it is social. This repo currently has a null
   description and zero topics and does not appear in any relevant GitHub search.
   `velimattiv/claude-security-audit` set 12 topics and still has 0 stars, so topics are
   necessary and not sufficient.
2. Neither this repo nor its closest competitor has a demo GIF or screenshot (VERIFIED
   for both). A security tool's output is a report, which is inherently screenshot-able.
   An embedded excerpt of a real `SECURITY-AUDIT-*.md` showing severity ranking and an
   OWASP tag is the cheapest credibility signal available and no competitor has it.
3. Install friction is a real filter. The current path is clone, cd, run a script,
   restart. The plugin path in Tier 1 reduces that to two lines typed inside Claude Code.
   Show HN guidelines explicitly reward removing barriers.
4. Install counts are public on `claude.com/plugins` (VERIFIED). That makes the community
   marketplace both a distribution channel and the only public scoreboard, which likely
   feeds the curation decision for the official marketplace.
5. Context cost is now shown in the `/plugin` UI (VERIFIED from the docs, v2.1.143+).
   Measured sizes for this skill: `SKILL.md` is 18,552 bytes, roughly 4.6k tokens, and
   the ten reference files total 121 KB but load lazily. The frontmatter description is
   793 characters, roughly 198 tokens, and is always resident. The progressive disclosure
   structure here is already correct; do not inline the references.

---

## Ordered action list

```
1.  gh repo edit: set description + 16 topics                    5 min
2.  Delete or gitignore oa.yaml (2.8 MB)                         2 min
3.  Decide repo rename to security-audit                        15 min
4.  Add .claude-plugin/marketplace.json                          20 min
5.  Add security-audit/.claude-plugin/plugin.json                10 min
6.  claude --plugin-dir ./security-audit, confirm invocation     15 min
7.  claude plugin validate ./security-audit                       5 min
8.  README: add the two-line /plugin install path                10 min
9.  README: embed a real report excerpt, add a demo GIF          60 min
10. Submit at platform.claude.com/plugins/submit                 20 min
11. Submit at skillstore.io/submit                               10 min
12. Read CONTRIBUTING.md for each awesome list, one PR each    varies
13. Read subreddit rules, then post where permitted            varies
14. Show HN, only after 1 through 9 are done                     30 min
```

Steps 1 through 8 are prerequisites for everything else and total under two hours.
Steps 12 through 14 are unverified in their mechanics and must be researched before
execution.

---

# Appendix: verified directory targets

Star counts pulled from the GitHub API on 2026-08-06. Everything below was read from
the repo's own CONTRIBUTING or README unless marked UNVERIFIED.

## Ranked for a single open-source skill

1. **platform.claude.com/plugins/submit** — distribution inside the product itself.
2. **aitmpl.com** (davila7/claude-code-templates) — PR, skills are first-class.
3. **awesomeskill.ai** — zero effort, auto-indexes public SKILL.md files.
4. **BehiSecc/awesome-claude-skills** — lowest friction of the awesome lists.
5. **ComposioHQ** and **VoltAgent** — straightforward PRs.
6. **hesreallyhim/awesome-claude-code** — hardest gate, only 4 skills listed.
7. **travisvn/awesome-claude-skills** — needs 10 stars first, and is stale.

## Anthropic's community marketplace — highest value

Catalog is `anthropics/claude-plugins-community`, 2,298 plugins, installed by users via
`/plugin marketplace add anthropics/claude-plugins-community`.

Submit at `https://platform.claude.com/plugins/submit` (Console; works for individual
authors). The older `clau.de/plugin-directory-submission` link redirects here.

Process: run `claude plugin validate ./your-plugin` locally — the review pipeline runs
the same check plus automated safety screening. Approved plugins get pinned to a commit
SHA, CI bumps the pin on new pushes, and the catalog syncs nightly.

**A skill-only repo qualifies.** Per the docs, a plugin shipping exactly one skill can
place `SKILL.md` at the plugin root instead of creating a `skills/` directory.

`claude-plugins-official` is curated at Anthropic's sole discretion with no application
process, and the submission form explicitly does not add plugins to it.

## Awesome lists

| Repo | Stars | Mechanism | Gate |
|---|---|---|---|
| ComposioHQ/awesome-claude-skills | 71,942 | PR, hosts the skill itself in a root folder. Default branch is `master` | Real use case, documented, tested |
| hesreallyhim/awesome-claude-code | 51,776 | **Web issue form only** | 14 days of commits **or** 100 stars |
| sickn33/agentic-awesome-skills | 44,553 | PR, hosts skills; `npm run validate` | Source-only PR, auto review workflow |
| VoltAgent/awesome-agent-skills | 29,703 | PR, link only | Description ≤10 words; no brand-new skills |
| travisvn/awesome-claude-skills | 14,536 | PR | **≥10 stars**, no AI-generated PRs |
| BehiSecc/awesome-claude-skills | 9,905 | PR or issue | No stated criteria |
| heilcheng/awesome-agent-skills | 6,063 | PR | SKILL.md under 500 lines |

**hesreallyhim is emphatic about the form:** "Do not open a PR. Just fill out the form",
and submitting any other way risks a temporary interaction restriction. It is not
possible to submit via the `gh` CLI. Form:
`https://github.com/hesreallyhim/awesome-claude-code/issues/new?template=recommend-resource.yml`

**travisvn requires acknowledging the PR was not AI-generated**, and closes PRs without
comment where the submitter has not. Worth respecting rather than working around.

## Web directories

**aitmpl.com / claudecodetemplates.com** — repo `davila7/claude-code-templates`,
30,131 stars, 871 entries typed `skill`. Submit by PR touching
`cli-tool/components/skills/<category>/<name>/`. A workflow auto-labels it, security
scans run, and a nightly job regenerates the JSON the site renders — so merge, then live
next day. Note CONTRIBUTING documents agents and commands but never mentions skills;
mirror the agent pattern.

**awesomeskill.ai** — harvests SKILL.md files from public GitHub repos automatically.
Verified through its own API, which returns `sourceUrl`, `githubRepo` and `githubStars`.
No submission needed; a public SKILL.md should get picked up.

**smithery.ai is MCP servers only** and is not a skill target, despite appearing on most
"where to publish" lists.

**claudepluginhub.com** — UNVERIFIED, blocked by Cloudflare Turnstile. It reportedly
auto-discovers via GitHub code search and accepts a repo URL at `/tools/submit-plugin`.

**mcpmarket.com** — has skills at `/tools/skills` (the nav's `/skills` is a 404). Submit
link exists at `/submit` but whether skills are submittable there is UNVERIFIED.

---

# Appendix 2: installable marketplaces, and one correction

## Correction to Appendix 1

**`davila7/claude-code-templates` is not a `/plugin marketplace add` target.** The repo
has no root `.claude-plugin/marketplace.json`; the only such file lives at
`cli-tool/components/.claude-plugin/marketplace.json` and is malformed as a marketplace
manifest — its top-level key is `agents`, with no `name` and no `plugins` array.
`/plugin marketplace add davila7/claude-code-templates` fails. It is a CLI
(`npx claude-code-templates@latest`) plus a website.

It remains a valid **PR target** for a listing, as described in Appendix 1. Just do not
expect users to install from it directly. Note also that its "Promote your component"
link is a paid-ads Google Form, not a listing path.

## Marketplaces users can actually install from

| Marketplace | `/plugin marketplace add <arg>` | Size | Stars | Open? |
|---|---|---|---|---|
| anthropics/claude-plugins-community | `anthropics/claude-plugins-community` | 2,298 plugins | official | Yes, via form |
| wshobson/agents | `wshobson/agents` | 95 plugins, 180 skills | 38,535 | **Yes** |
| alirezarezvani/claude-skills | `alirezarezvani/claude-skills` | 88 plugins | 23,905 | **Yes** |
| ananddtyagi/cc-marketplace | `ananddtyagi/cc-marketplace` | 119 plugins | 687 | Off-GitHub form |
| obra/superpowers-marketplace | `obra/superpowers-marketplace` | 10 plugins | 1,202 | No, personal curation |
| trailofbits/skills-curated | `trailofbits/skills-curated` | 29 plugins | 478 | No, staff-reviewed only |

**anthropics/claude-plugins-community** takes no PRs — "pull requests opened directly
against this repo are closed automatically." The repo must be public (closed-source is
rejected), validated locally with `claude plugin validate ./your-plugin`, then submitted
through the form. Approved plugins are pinned to a commit SHA and the catalog syncs
nightly. `claude-plugins-official` has no application process at all.

**wshobson/agents** is the largest open one. Process: open an issue first using a
template, create `plugins/<name>/.claude-plugin/plugin.json` with skills in `skills/`,
**add your entry to `.claude-plugin/marketplace.json`**, then run `make generate-all`,
`make validate`, `make garden`, `make test` and `make smoke-test` before opening a PR
that references the issue. No `__` in names, no promotional content, and disclose it if
you maintain a service the plugin wraps. Worth knowing: it ships to six harnesses and
Codex truncates SKILL.md at 8 KB, which is an argument for keeping the body lean.

**alirezarezvani/claude-skills** requires PRs against `dev` — PRs to `main` are
auto-closed — and compliance with its `CONVENTIONS.md` and `SKILL-AUTHORING-STANDARD.md`.

Skip **obra/superpowers-marketplace** and **trailofbits/skills-curated**. Both are
closed by design; Trail of Bits states plainly that the point is not installing plugins
from repos they have not reviewed.

## Aggregators: nothing to do

These auto-index public GitHub repos, so a public repo gets picked up without any
submission: claudepluginhub.com (largest, self-described auto-indexed — but its
`starCount` is a derived popularity metric, not GitHub stars, so ignore its rankings),
claudemarketplaces.com (auto-crawl, no submit form), skills.sh (resolves `owner/repo`
on demand, no submission at all), claudeskills.info (daily crawl, optional submit).

skillsdirectory.com is the exception with a real manual submission behind GitHub sign-in.

`claudecodemarketplace.com` is dead (HTTP 404, `DEPLOYMENT_NOT_FOUND`). smithery.ai and
glama.ai remain MCP-only and have not expanded into skills.

## Revised order

1. `clau.de/plugin-directory-submission` (or `platform.claude.com/plugins/submit` for
   individual authors) — official, reaches every Claude Code user.
2. PR to `wshobson/agents`.
3. PR to `alirezarezvani/claude-skills`, targeting `dev`.
4. PR to `davila7/claude-code-templates` for the aitmpl.com listing.
5. Everything else auto-indexes.

All four active steps require the plugin packaging described in Tier 1.

---

# Appendix 3: channels, and a correction on awesome-lists

## Awesome-lists matter less than assumed

The three largest community Claude Code projects — SuperClaude (23.7k stars),
davila7/claude-code-templates (30.1k), and wshobson/agents (38.5k) — are **all absent**
from `awesome-claude-code`. They got large without being listed.

The maintainer says so directly in CONTRIBUTING:

> "Too many people think like this: (i) Build something awesome; (ii) Submit to Awesome
> Claude Code; (iii) Get accepted, because of being awesome; (iv) Get users. However, a
> more likely chain of events is: (i) Build something awesome; (ii) Get users;
> (iii) Submit it."

Treat a listing as a lagging indicator, not a launch strategy. There is a Security
category, and the gate is 14 days of ongoing commits **or** 100 stars.

## The channel with actual numbers attached

`claude.com/plugins` is sorted by installs and publishes them. As of 2026-08-06:
Frontend Design 1,134,112 · **Superpowers 1,009,371 (community)** · Code Review 438,525 ·
Context7 417,801 (community) · Skill Creator 385,083.

A community plugin sitting at #2 with a million installs is the strongest evidence in
this whole document that the directory is the channel that matters. Note the official
catalog is auto-registered on first launch; the community catalog must be added manually,
and still produced those numbers.

## Reddit, precisely

**r/ClaudeCode** (377k) is the better first post despite being smaller. Rule 5 requires
standalone posts to be a real write-up — what you built, how Claude Code was used, what
you learned — but there is **no karma gate**. Simple drops go in the weekly showcase
thread. Flair: "Built with Claude Code".

**r/ClaudeAI** (1.06M) explicitly encourages self-promotion under Rule 7, but requires
**50+ total karma** for a feed post; below that you are redirected to the showcase
megathread, where mods note sub-50 posts "very rarely get any traction". Must be free to
try and say so. No referral links.

**r/netsec is effectively closed.** Rule 8 bans tool and README links outright, Rule 4
requires a 6+ month history of quality contribution before anything commercial, and
Rule 9 bans LLM-generated posts. The only viable path is a technical writeup explaining
what is genuinely novel about the analysis — not a repo link — or the monthly tool thread.

## X

No hashtags. Across ~25 sampled posts from every relevant account, zero used one;
distribution there is @-mentions and quote-tweets.

Best realistic target is **@claude_code** (47.6k), an independent community account with
a demonstrated pattern of amplifying third-party skills including install instructions.
Official accounts: @ClaudeDevs (634k) is the developer channel; @AnthropicAI is research
and policy, not tooling.

## Show HN: low priority for this category

Median score across ~40 "Claude Code skill" submissions is **3-4 points**. SuperClaude
got 6. Superpowers got 1, 4, 4 and 3 across four attempts. The two outliers were a skill
with a **demo video** and honest framing (337 points), and a third party reviewing
someone else's project (50).

Show HN rules explicitly exclude "blog posts, sign-up pages... and other reading
material" and warn against "quickly-generated one-offs". If you go, go with a demo video,
on a Sunday around 12:00 UTC. Expect little.

## Stars are not adoption

davila7/claude-code-templates has 30,131 stars and **17,540 npm downloads per month**.
SuperClaude's npm package sees **166 per month**. Superpowers is the only one where usage
exceeds stars.

An ICSE 2026 paper identified roughly six million suspected fake stars on GitHub and
names AI and LLM projects as the main remaining target category. Do not benchmark against
star counts in this space.

## The one documented adoption event

Jesse Vincent launched Superpowers on 2025-10-09. Simon Willison wrote it up the next
day, calling it "a really significant piece". That is the clearest causal catalyst
verifiable for any project in this category, and it was not a list, a marketplace, or
Show HN. Note the install was two commands, not one, so friction was not decisive.

## Ordered

1. Community plugin directory — `clau.de/plugin-directory-submission`. Only channel with
   verified install numbers, and default-reachable from every Claude Code install.
2. r/ClaudeCode standalone post with a real write-up. No karma gate.
3. X, @-mentioning @claude_code.
4. r/ClaudeAI feed post if you have 50+ karma, else the megathread.
5. A technical writeup on what is novel here. Unlocks r/netsec, doubles as dev.to
   (`claudecode`, not `claude-code`, which 404s) and Medium AI Advances (99k followers,
   11% acceptance, 24-hour decisions).
6. awesome-claude-code Security category, once past the gate. Lagging indicator.
7. Show HN, only with a demo video. Low priority.
