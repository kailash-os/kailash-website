# Contributing

Contributions are welcome. This document is the working agreement. It states
how changes move: proposal, review, merge. It also states what the
continuous-integration gates enforce. This repo is the docs-only Quarto site.
It carries no nix code and no manifest. The distribution working agreements
live in
[kailash-os](https://github.com/kailash-os/kailash-os/blob/master/CONTRIBUTING.md)
and
[kailash-packages](https://github.com/kailash-os/kailash-packages/blob/main/CONTRIBUTING.md).

## Ground rules

1. **Never commit to `main`.** All work happens on a branch. One branch
   carries one change. A pull request merges the branch. Branch names follow
   `<type>/<short-description>` with kebab-case — e.g. `site/tools-page`,
   `docs/paper-render`, `agents/page-refresh`.
2. **Conventional Commits.** Every commit subject follows
   the [specification](https://www.conventionalcommits.org/en/v1.0.0). The
   form: `type: subject` (scope optional on a docs-only site).
   - Standard types: `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`,
     `chore`, `perf`, `revert`.
   - Site-surface types (this repo's extension, carried by its history):
     `site` (rendered-page content/layout) and `agents` (the coding-agents
     guide page).
   - Subject: imperative, no trailing period. The body (optional) records
     the change and the reason. Wrap the body at 72 columns.
   - PR titles follow the same form. Site-track items carry their roadmap id
     in the subject — `site: KA-WS-x — …`. Squash merges use the PR title as
     the commit subject (`squash_merge_commit_title: COMMIT_OR_PR_TITLE`).
     The PR title is then the commit record. A CI gate checks the form on
     every PR. Bot and dependency PRs keep their canonical titles: renovate,
     pre-commit.ci autoupdate.
3. **Sign everything.** Commits must be GPG- or SSH-signed. The
   `protect-default` ruleset requires signatures (`required_signatures`). An
   unsigned commit blocks the PR. Check signatures with
   `git log --show-signature`.
4. **One logical change per PR.** Small, reviewable diffs merge faster.
5. **Pre-commit runs locally.** Install the hooks once per clone:
   `pre-commit install && pre-commit install --hook-type pre-push`. Every
   `git commit` and `git push` then runs the hook set that CI runs.
   pre-commit.ci still gates every PR.

## CI gates

Every pull request runs:

| Check | What it does |
|---|---|
| `site-check` (required) | `quarto render` fails on broken refs; the built HTML must exist |
| `PR title — Conventional Commits` | PR title checked against the Conventional Commits form |
| `scorecard` | OpenSSF Scorecard |
| `pre-commit.ci` | the [.pre-commit-config.yaml](.pre-commit-config.yaml) hook set |

The branch ruleset `protect-default` (active) enforces the rules. The rules:
no deletions, no non-fast-forward pushes, required signatures, and the PR
rule. The PR needs code-owner review. Unattributed changes need extra
approval. Merges to `main` deploy the site. The deploy rides the Pages
workflow (`pages.yml`). The live page is [kailash.site](https://kailash.site).

## Commits and pull requests

- Cut the branch from current `origin/main`. Push it. Open the PR against
  `main`. The PR description states the change, the reason (the issue), and
  the render check.
- Check rendered output, not configuration. Run `quarto render`. Then parse
  the built `_site/*.html` for nav order, labels, and TOC anchors. Do this
  check before pushing.
- A merge happens on review. The maintainer merges.

## Reporting bugs

Open a [GitHub issue](https://github.com/kailash-os/kailash-website/issues/new).
The issue names the page, the observed render, and the expected render. It
also cites the commit where the behaviour appeared. Security issues never go
here. Use [SECURITY.md](SECURITY.md) instead.

## Writing standard

Every written text in this repo follows ASD-STE100 Simplified Technical
English. The rules: one thought per sentence, 20 words per sentence or
fewer, active voice, present tense. The canonical decision record lives in
the kailash-os repo:
[`docs/adr/0004-asd-ste100-standard.md`](https://github.com/kailash-os/kailash-os/blob/master/docs/adr/0004-asd-ste100-standard.md)
([kailash-os#217](https://github.com/kailash-os/kailash-os/pull/217) carries
it). The conversion lane:
[kailash-website#46](https://github.com/kailash-os/kailash-website/issues/46).
