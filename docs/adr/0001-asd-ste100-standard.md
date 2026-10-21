# 0001 — ASD-STE100: the site's writing standard

Status: accepted

## Context

The site renders reader-facing prose: the home page, the roadmap, the build
page, and the agent-page set. The register differs between the pages:
sentence length, tense, and person drift. Two record classes share the tree
with that prose: delivered-work log entries in `roadmap.qmd`, and accepted
records. The reader gets no promise of one word list or one register.

## Decision

The operator's directive (2026-10-20) sets the standard. The org record is
[`kailash-os` ADR 0004](https://github.com/kailash-os/kailash-os/blob/master/docs/adr/0004-asd-ste100-standard.md);
this record adopts the same rule set for this repo's written output.

Every written text on the site follows ASD-STE100 Simplified Technical English:

1. One thought per sentence. A sentence carries one fact or one instruction.
2. A sentence stays at or under 20 words.
3. The voice is active. The tense is present. Instructions sit in the imperative.
4. A non-approved verb takes one fixed approved substitution.
5. One word carries one meaning, on every page.
6. Fixed technical names stay exact: tool ids, flag names, layer names, gate names.
7. Numbers use digits, with units adjacent.
8. Rendered text carries no idioms, no slang, and no first or second person.
9. No invented facts. A claim states its basis. A measured number cites the record that measured it.
10. Historical records keep their filed tense and wording.

The scope, and the boundary:

- The rendered pages in the project render list, plus the repo README, follow
  the rule set.
- The delivered-work timeline in `roadmap.qmd` is a historical record. It
  keeps its filed tense and wording; the standard governs that page's
  forward-written sections only.
- `CONTRIBUTING.md` and `SECURITY.md` are include-copies of repo-side
  sources. Both sides convert in one PR.
- `tools.qmd` is generator output. Its words convert in
  `tools/generate-tools-page.py`; the generator then re-renders the page.
- `includes/README.md` mirrors `AGENTS.md` in the `kailash-os` repo and never
  converts alone.

Enforcement:

- The conversion lane is [kailash-website#46](https://github.com/kailash-os/kailash-website/issues/46).
- Every change rides a leaf branch, a signed Conventional Commit, and a PR.
- Every PR keeps the site gates green: the `site-check` render,
  `dependency-review`, `pr-title-gate`, and `pre-commit.ci`.
- The render list, the page set, and the anchor set never move in a conversion.

## Consequences

- Forward-written page prose follows the rule set from the merge day on.
- The standing page prose converts through the conversion lane, page by page.
- The `site-check` render stays the mechanical check for every conversion PR.
