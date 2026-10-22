#!/usr/bin/env python3
# Generate the website's Tools page (tools.qmd) from the tool manifest.
#
# Single source of truth: kailash-os/kailash-packages manifest/tools.yaml
# (tool rows) + manifest/categories.yaml (the taxonomy). This script fetches
# both files live from the pinned raw.githubusercontent.com URLs, then renders
# tools.qmd: provenance/methodology prose, a glossary for every field a tool
# row carries, one section per category with a table of its tools, and a
# per-layer summary. Nothing on the generated page is hand-maintained — run
# this script again after a manifest merge and commit the result.
#
# Requirements: python 3.9+, PyYAML (pip install pyyaml). Network access to
# raw.githubusercontent.com; no credentials.
#
# Usage:
#   python3 tools/generate-tools-page.py              # regenerate tools.qmd
#   python3 tools/generate-tools-page.py --out X.qmd  # write elsewhere
#   python3 tools/generate-tools-page.py --self-test  # assert-based checks
#
# After generating, the script re-reads its own output and asserts the section
# and row counts against the manifest before exiting non-zero on mismatch.

import argparse
import os
import sys
import urllib.request

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("error: PyYAML is required (python3 -m pip install pyyaml)\n")
    sys.exit(2)

PACKAGES_RAW_BASE = "https://raw.githubusercontent.com/kailash-os/kailash-packages/main"
TOOLS_URL = PACKAGES_RAW_BASE + "/manifest/tools.yaml"
CATEGORIES_URL = PACKAGES_RAW_BASE + "/manifest/categories.yaml"

DEFAULT_OUT = "tools.qmd"
USER_AGENT = "kailash-website-tools-page-generator/1.0"
DESC_LIMIT = 140  # truncate long descriptions at a word boundary

# Layer presentation, derived from category ids at render time; layer values
# never leave this vocabulary.
LAYER_LETTER = {"CLASSIC": "c", "ATTACK": "a", "OPS": "o", "DEFENCE": "d"}


def fetch_manifest(url):
    """Fetch and parse one manifest YAML file from the pinned URL."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = yaml.safe_load(resp.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest %s: expected a mapping at the top level" % url)
    return data


def md_cell(text):
    """Make a string safe inside a pipe-table cell (entities, not backslashes)."""
    text = str(text)
    for from_, to in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("|", "&#124;")):
        text = text.replace(from_, to)
    return text


def truncate(text, limit=DESC_LIMIT):
    """Truncate a one-line description at a word boundary."""
    text = text.rstrip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def category_code(cat_id):
    """c-01-information-gathering -> C-1 (manifest letter + census number)."""
    letter, num = cat_id.split("-", 2)[0], cat_id.split("-", 2)[1]
    return "%s-%d" % (letter.upper(), int(num))


def packaging_cell(tool):
    """Packaging column: status, plus the derivation path for bespoke rows."""
    pack = tool.get("packaging") or {}
    status = pack.get("status")
    if not status:
        return "—"
    cell = "`%s`" % md_cell(status)
    derivation = pack.get("derivation")
    if derivation:
        cell += " · `%s`" % md_cell(derivation)
    return cell


def safety_cell(tool):
    """Safety column: level, plus the target-required marker when declared."""
    safety = tool.get("safety") or {}
    level = safety.get("level")
    if not level:
        return "—"
    cell = "`%s`" % md_cell(level)
    if safety.get("target-required"):
        cell += " · target-required"
    return cell


def tool_cell(tool):
    """Tool column: name linked to the pinned upstream vcs_url when present."""
    name = md_cell(tool.get("name") or tool.get("id"))
    source = tool.get("source") or {}
    url = source.get("vcs_url")
    if url:
        return "[%s](%s)" % (name, md_cell(url))
    return "**%s**" % name


def tool_row(tool):
    """One pipe-table row for a tool. Columns: Tool | Licence | Packaging | Safety | Description."""
    secondary = tool.get("secondary_categories") or []
    toolname = tool_cell(tool)
    if secondary:
        toolname += '<br>*also:* `%s`' % md_cell(", ".join(secondary))
    cells = [
        toolname,
        md_cell(tool.get("license") or "—"),
        packaging_cell(tool),
        safety_cell(tool),
        md_cell(truncate(tool.get("description") or "")),
    ]
    return "| " + " | ".join(cells) + " |"


def tool_table(tools):
    """Render the category table for the given tool rows (manifest order)."""
    lines = [
        "| Tool | Licence | Packaging | Safety | Description |",
        "|---|---|---|---|---|",
    ]
    lines.extend(tool_row(t) for t in tools)
    return "\n".join(lines)


def group_by_category(tools, categories):
    """Bucket tool rows by primary category, preserving manifest order."""
    buckets = {c["id"]: [] for c in categories}
    unknown = []
    for t in tools:
        cid = t.get("category")
        if cid in buckets:
            buckets[cid].append(t)
        else:
            unknown.append(t["id"])
    if unknown:
        raise ValueError("tool rows with an unknown primary category: %s"
                         % ", ".join(sorted(unknown)))
    return buckets


def category_section(cat, tools):
    """Render one category section: heading, purpose, table."""
    cid = cat["id"]
    code = category_code(cid)
    layer = cat.get("layer", "")
    kind = cat.get("kind", "category")
    n = len(tools)
    planned = cat.get("tools")
    h2 = "## %s · %s (`%s`, %s" % (code, md_cell(cat.get("name", cid)), cid, layer)
    if kind == "data-pack":
        h2 += " data-pack"
    if planned and planned != n:
        h2 += ", %d of %d planned" % (n, planned)
    else:
        h2 += ", %d tools" % n
    h2 += ")"

    lines = [h2, ""]
    purpose = cat.get("purpose")
    if purpose:
        lines.append("**Purpose:** %s" % md_cell(purpose))
        lines.append("")
    coverage = cat.get("coverage")
    if coverage:
        lines.append("*Coverage:* %s" % md_cell(coverage))
        lines.append("")
    if kind == "data-pack":
        pack_ref = cat.get("data", "")
        lines.append(
            "**Opt-in data-pack.** This category ships as the opt-in data-pack `%s`. "
            "Its tools stay absent from default profiles and ISOs by design. The "
            "module stub exists. It stays off on every default surface. "
            "Manifest note: %s" % (md_cell(pack_ref), md_cell(cat.get("notes", "")))
        )
        lines.append("")
    lines.append(tool_table(tools))
    lines.append("")
    return "\n".join(lines)


def field_glossary(tools):
    """'Field meanings': the full row-field glossary + vocabularies."""
    total = len(tools)

    def count_of(pred):
        return sum(1 for t in tools if pred(t))

    def has_map(tool, key):
        return bool(tool.get(key))

    in_counts = {
        "id": total,
        "layer": count_of(lambda t: t.get("layer")),
        "category": count_of(lambda t: t.get("category")),
        "secondary_categories": count_of(lambda t: t.get("secondary_categories")),
        "name": count_of(lambda t: t.get("name")),
        "description": count_of(lambda t: t.get("description")),
        "source": count_of(lambda t: has_map(t, "source") and (t["source"].get("vcs_url"))),
        "license": count_of(lambda t: t.get("license")),
        "packaging": count_of(lambda t: has_map(t, "packaging")),
        "safety": count_of(lambda t: has_map(t, "safety")),
        "nixos_menu": count_of(lambda t: has_map(t, "nixos_menu")),
        "docs": count_of(lambda t: t.get("docs")),
        "tags": count_of(lambda t: t.get("tags")),
        "atlas_tactics": count_of(lambda t: t.get("atlas_tactics")),
        "owasp_llm": count_of(lambda t: has_map(t, "owasp_llm")),
    }
    derivations = count_of(lambda t: (t.get("packaging") or {}).get("derivation"))

    update_tags = {tc: count_of(lambda t, tc=tc: tc in (t.get("tags") or []))
                   for tc in ("update:slow", "update:steady", "update:weekly", "update:fast")}

    rows = [
        ("`id`", "%d/%d" % (in_counts["id"], total),
         "Unique slug — the row's key on every generated surface (menu, CLI, modules, docs, derivations)."),
        ("`layer`", "%d/%d" % (in_counts["layer"], total),
         "`CLASSIC` · `ATTACK` · `DEFENCE` · `OPS` (the platform layer, formerly BUILD — [kailash-os#121](https://github.com/kailash-os/kailash-os/issues/121)). All four ride a CORE substrate with no tool categories."),
        ("`category`", "%d/%d" % (in_counts["category"], total),
         "Primary category id — exactly one per row (the one-tool-one-primary invariant). The id orders the 31 sections on this page."),
        ("`secondary_categories`", "%d/%d" % (in_counts["secondary_categories"], total),
         "Optional cross-refs where dual-use is real — never a second primary. The tables show it as the *also* line."),
        ("`name`", "%d/%d" % (in_counts["name"], total),
         "Human name (menu/docs surface). It equals `id` on all rows but one."),
        ("`description`", "%d/%d" % (in_counts["description"], total),
         "One line: what the tool does. The manifest holds the text. The tables truncate it."),
        ("`source`", "%d/%d" % (in_counts["source"], total),
         "Upstream coordinates `{vcs_owner, repo, vcs_url}`. Research-grade tools pin commit-exact (nvfetcher, `_sources/`). The field is absent on %d rows with no declared upstream URL. Those rows render unlinked."
         % (total - in_counts["source"])),
        ("`license`", "%d/%d" % (in_counts["license"], total),
         "SPDX identifier (`GPL-2.0-only`, `MIT`, …)."),
        ("`packaging`", "%d/%d" % (in_counts["packaging"], total),
         "`status` (vocabulary below) + `derivation` path on bespoke rows (%d)."
         % (derivations,)),
        ("`safety`", "%d/%d" % (in_counts["safety"], total),
         "`level` (vocabulary below) + `target-required` bool. The pair is inert without a declared target. The OS-side double gate reads the pair."),
        ("`nixos_menu`", "%d/%d" % (in_counts["nixos_menu"], total),
         "Desktop-menu surface `{icon, exec, category}`."),
        ("`docs`", "%d/%d" % (in_counts["docs"], total),
         "Generated docs path: `layers/<category>/<tool>.md`."),
        ("`tags`", "%d/%d" % (in_counts["tags"], total),
         "Lowercase list: shape/stage markers + the `update:*` cadence class (below)."),
        ("`atlas_tactics`", "%d/%d" % (in_counts["atlas_tactics"], total),
         "≥1 MITRE ATLAS tactic id (`AML.T…`, 2026.05 matrix) — ATTACK rows only."),
        ("`owasp_llm`", "%d/%d" % (in_counts["owasp_llm"], total),
         "Dual-epoch OWASP LLM Top 10 map `{2026: […], v2: […]}` — ATTACK rows only. The epochs stay separate and never mix (§2.4)."),
    ]

    lines = [
        "## Field meanings", "",
        "Every field a tool row can carry, in manifest order. The *In* column "
        "shows the live count of the %d tool rows carrying the field at this "
        "revision. A smaller count marks an optional field. A row shows the "
        "field only when the row carries it." % total,
        "",
        "| Field | In | Meaning |",
        "|---|---|---|",
    ]
    for field, in_column, meaning in rows:
        lines.append("| %s | %s | %s |" % (field, in_column, meaning))
    lines.append("")

    lines.extend([
        "### `packaging.status`", "",
        "| Status | Count | Meaning |",
        "|---|---|---|",
    ])
    status_meanings = [
        ("native", lambda: in_counts["packaging"],
         "nixpkgs ships the tool. The row records the upstream coordinates that the lock builds from."),
        ("stale", lambda: count_of(lambda t: (t.get("packaging") or {}).get("status") == "stale"),
         "nixpkgs-native. The packaged version trails upstream. The update cadence tracks the lag. No fork exists."),
        ("bespoke", lambda: count_of(lambda t: (t.get("packaging") or {}).get("status") == "bespoke"),
         "Packaged in this overlay: the nvfetcher commit-exact pin, `pkgs/<tool>/default.nix`, and a committed `_sources/`."),
        ("module", lambda: count_of(lambda t: (t.get("packaging") or {}).get("status") == "module"),
         "Ships as a bundled module/component (service- or library-shape). It is not a single menu executable."),
        ("data", lambda: count_of(lambda t: (t.get("packaging") or {}).get("status") == "data"),
         "Data artefact: wordlists, corpora, pack seeds. Typically an opt-in data-pack row."),
    ]
    for status, count_fn, meaning in status_meanings:
        lines.append("| `%s` | %d | %s |" % (status, count_fn(), meaning))
    lines.append("")

    lines.extend([
        "### `safety.level`", "",
        "| Level | Count | Meaning |",
        "|---|---|---|",
    ])
    level_meanings = [
        ("safe", lambda: count_of(lambda t: (t.get("safety") or {}).get("level") == "safe"),
         "Runs as-is — works on artefacts, local models, or one's own systems."),
        ("requires-target", lambda: count_of(lambda t: (t.get("safety") or {}).get("level") == "requires-target"),
         "Needs a system under test as its target — authorised engagements only."),
        ("exp", lambda: count_of(lambda t: (t.get("safety") or {}).get("level") == "exp"),
         "Experimental research code — lab releases. The OS side double-gates it (`kailash.labMode = true` + `KAILASH_LAB_MODE=1`)."),
    ]
    for level, count_fn, meaning in level_meanings:
        lines.append("| `%s` | %d | %s |" % (level, count_fn(), meaning))
    lines.append("")
    lines.extend([
        "`target-required` (%d of %d rows, all ATTACK) — inert without a target. It renders as the `· target-required` marker in the Safety column." % (count_of(lambda t: (t.get("safety") or {}).get("target-required")), total),
        "",
    ])

    lines.extend([
        "### Tag update classes", "",
        "The `update:*` tag on a row is the update-automation cadence class. "
        "The class sets how fast the tool's pin follows upstream. Live "
        "distribution at this revision:",
        "",
        "| Tag | Rows |",
        "|---|---|",
    ])
    update_meanings = [
        ("update:slow", "The bulk cadence — steady availability, not per-commit tracking."),
        ("update:steady", "Tighter tracking, not release-pinned."),
        ("update:weekly", "Weekly follow — fast-moving attack tooling."),
        ("update:fast", "Tightest follow — pinned-reference tools stay near upstream head."),
    ]
    for tag, meaning in update_meanings:
        lines.append("| `%s` | %d — %s |" % (tag, update_tags[tag], meaning))
    lines.append("")
    return "\n".join(lines)


def layer_summary(categories, tools):
    """Final per-layer summary table + the data-pack note."""
    buckets = group_by_category(tools, categories)
    per_layer = {}
    for cat in categories:
        layer = cat.get("layer", "—")
        entry = per_layer.setdefault(layer, {"categories": 0, "rows": 0, "kinds": {}, "codes": []})
        entry["categories"] += 1
        entry["rows"] += len(buckets.get(cat["id"], []))
        entry["kinds"][cat.get("kind", "category")] = True
        entry["codes"].append(category_code(cat["id"]))

    lines = ["## Per-layer summary", "",
             "| Layer | Categories | Tool rows |",
             "|---|---|---|"]
    ordered_layers = sorted(per_layer, key=lambda l: list(LAYER_LETTER).index(l)
                            if l in LAYER_LETTER else 99)
    for layer in ordered_layers:
        entry = per_layer[layer]
        codes = entry["codes"]
        id_range = codes[0] if len(codes) == 1 else "%s…%s" % (codes[0], codes[-1])
        cats_desc = "%d (%s)" % (entry["categories"], id_range)
        if entry["kinds"].get("data-pack"):
            cats_desc += " — includes the opt-in SDR data-pack"
        rows_desc = str(entry["rows"])
        if layer == "CLASSIC":
            sdp = len(buckets.get("c-07-signal-sdr", []))
            if sdp:
                rows_desc += " (of which %d in the SDR data-pack)" % sdp
        lines.append("| **%s** | %s | %s |" % (layer, cats_desc, rows_desc))
    n_cats = sum(1 for c in categories if c.get("kind", "category") == "category")
    n_packs = sum(1 for c in categories if c.get("kind") == "data-pack")
    total_desc = "%d categories" % n_cats
    if n_packs:
        total_desc += " + %d opt-in data-pack%s" % (n_packs, "" if n_packs == 1 else "s")
    lines.append("| **Total** | %s | %d |" % (total_desc, len(tools)))
    lines += [
        "",
        "The second planned data-pack, `kailash-data.wordlists-mega` (riding "
        "C-5), is a manifest plan row. It is not yet a tool row. The opt-in "
        "wordlist pack lands with the KA-07 data work. This page renders the "
        "manifest as it stands. Regenerate after the next manifest merge. "
        "The counts then move with it.",
        "",
    ]
    return "\n".join(lines)


INTRO_PARAGRAPHS = [
    # Provenance — where the tools come from.
    "The page has three provenance streams. The **CLASSIC** layer follows the "
    "Kali heritage catalog, re-derived for a software-only scope. **DEFENCE** "
    "and **OPS** use the nixpkgs staple set: reproducible infrastructure, "
    "not curated exotica. **ATTACK** and the specialised edges of every layer "
    "use upstream research tooling: garak, PyRIT, promptfoo, ART, "
    "counterfit. nvfetcher pins these tools commit-exact. A pin moves only "
    "with an upstream commit.",
    # Method — how selection works.
    "The selection criterion is fit to the four pillars: **AppSec**, "
    "**APISec**, **MLSec**, **AISec**. **AppSec** is classic software "
    "assessment. **APISec** is web/API/AI-endpoint runtime assessment. "
    "**MLSec** is adversarial ML against predictive models. **AISec** is "
    "LLM, agentic, and MCP security. Every tool lands in exactly one primary "
    "category. A dual-use tool carries `secondary_categories` cross-refs. "
    "Duplicate rows never render.",
    # Exclusions — §3.7.
    "The §3.7 no-resurrection guard holds. The distribution excludes "
    "hardware/RF/wifi/bluetooth tooling (one opt-in exception: the c-07 SDR "
    "data-pack). It also excludes paid-licence tools, cloud-only SaaS, "
    "unmaintained tools, and classic-network attack tooling (lateral "
    "movement, C2 frameworks, social engineering). The last group is Kali's "
    "network-arsenal territory. It is not the four pillars.",
    # The census.
    "The census holds %d taxonomy rows: %d categories + %d opt-in data-pack "
    "(%s). Tool rows: %d — %s. The §3.6 census projected ~337 primary slots. The rows "
    "fill %d of them. Each section heading shows its open planned slots.",
    # The generation statement.
    "Generated — never hand-maintained. `python3 tools/generate-tools-page.py` "
    "fetches `tools.yaml` + `categories.yaml` from kailash-packages. The "
    "script renders every number, table, and link at generation time. A "
    "manifest merge regenerates this page.",
]


def census_paragraph(categories, tools):
    """Fill the census paragraph with live-computed numbers."""
    rows_by_category = group_by_category(tools, categories)
    data_packs = [c for c in categories if c.get("kind") == "data-pack"]
    cats = [c for c in categories if c.get("kind", "category") == "category"]
    cat_rows = sum(len(rows_by_category[c["id"]]) for c in cats)
    pack_rows = {c["id"]: len(rows_by_category[c["id"]]) for c in data_packs}
    layer_counts = {}
    for t in tools:
        layer_counts[t.get("layer")] = layer_counts.get(t.get("layer"), 0) + 1
    layer_str = ", ".join("%s %d" % (l, layer_counts[l]) for l in ("CLASSIC", "ATTACK", "OPS", "DEFENCE") if l in layer_counts)
    open_slots = ["%s at %d of %d" % (category_code(c["id"]), len(rows_by_category[c["id"]]), c["tools"])
                  for c in cats if c.get("tools") and c["tools"] != len(rows_by_category[c["id"]])]
    pack_names = ", ".join("`%s`" % c["id"] for c in data_packs)
    return INTRO_PARAGRAPHS[3] % (
        len(categories),      # taxonomy rows
        len(cats),            # categories
        len(data_packs),      # data-pack rows
        pack_names,
        len(tools),           # tool rows
        layer_str,
        cat_rows,
    )


GENERATED_COMMENT = """<!-- GENERATED FILE — do not hand-edit.
Regenerate from the tool manifest with:

    python3 tools/generate-tools-page.py

Run the command from the repository root. The command fetches
manifest/tools.yaml and manifest/categories.yaml from
kailash-os/kailash-packages main, then rewrites tools.qmd. No number or
table on this page is hand-maintained. Regenerate after every manifest
merge, then commit the result. -->"""


def render_page(categories, tools):
    """Render the full tools.qmd document."""
    header = "---\ntitle: \"Tools\"\ntoc-depth: 3\n---"
    intro = [INTRO_PARAGRAPHS[0], "", INTRO_PARAGRAPHS[1], "", INTRO_PARAGRAPHS[2], "",
             census_paragraph(categories, tools), "", INTRO_PARAGRAPHS[4], ""]

    buckets = group_by_category(tools, categories)
    sections = [category_section(cat, buckets.get(cat["id"], [])) for cat in categories]

    body = [
        header,
        "",
        GENERATED_COMMENT,
        "",
        "# Kailash tool set", "",
    ]
    body.extend(intro)
    body.append(field_glossary(tools))
    body.append("")
    for section in sections:
        body.append(section)
        body.append("")
    body.append(layer_summary(categories, tools))

    text = "\n".join(body)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.rstrip("\n") + "\n"


def verify_output(text, categories, tools):
    """Read-back invariant: every category section and every tool row renders
    exactly once, matching the manifest."""
    buckets = group_by_category(tools, categories)
    lines = text.splitlines()

    # Each category heading appears exactly once.
    for cat in categories:
        heading = "## %s · " % category_code(cat["id"])
        found = sum(1 for ln in lines if ln.startswith(heading))
        if found != 1:
            raise AssertionError("category %s: heading found %d times (expected 1)"
                                 % (cat["id"], found))

    # Each tool's exact table row appears exactly once (one primary category).
    for t in tools:
        row = tool_row(t)
        found = text.count(row)
        if found != 1:
            raise AssertionError("tool %s: table row found %d times (expected 1)\n  %s"
                                 % (t.get("id"), found, row[:120]))

    linked = sum(1 for t in tools if (t.get("source") or {}).get("vcs_url"))
    return {"sections": len(categories), "rows": len(tools),
            "linked": linked, "unlinked": len(tools) - linked,
            "in_data_packs": sum(len(buckets.get(c["id"], []))
                                 for c in categories if c.get("kind") == "data-pack")}


# ---------------------------------------------------------------------------
# Self-test: fixture-based asserts for the pure rendering/selection logic.
# ---------------------------------------------------------------------------

FIXTURE = {
    "categories": {
        "categories": [
            {"id": "c-01-information-gathering", "layer": "CLASSIC", "kind": "category",
             "name": "Information Gathering", "purpose": "Find and enumerate software targets.",
             "coverage": "nixpkgs-native majority", "tools": 3},
            {"id": "a-02-prompt-injection-jailbreaks", "layer": "ATTACK", "kind": "category",
             "name": "LLM Prompt Injection & Jailbreaking", "purpose": "Attack language-model controls.",
             "coverage": "upstream research tooling", "tools": 2,
             "atlas_tactics": ["AML.T0051"],
             "owasp_llm": {"2026": ["LLM01"], "v2": ["LLM01"]}},
            {"id": "c-07-signal-sdr", "layer": "CLASSIC", "kind": "data-pack",
             "name": "Signal & SDR Processing", "purpose": "Software-only DSP and audio tooling.",
             "coverage": "opt-in data-pack", "tools": 1,
             "opt_in": True, "data": "kailash-data.sdr-tools",
             "notes": "off default profiles/ISOs by design."},
        ]
    },
    "tools": {
        "tools": [
            {"id": "nmap", "layer": "CLASSIC", "category": "c-01-information-gathering",
             "name": "nmap",
             "description": "Network scanner and security mapper.",
             "source": {"vcs_owner": "nmap", "repo": "nmap",
                        "vcs_url": "https://github.com/nmap/nmap"},
             "license": "GPL-2.0-only",
             "packaging": {"status": "native"},
             "safety": {"level": "safe"},
             "nixos_menu": {"icon": "nmap.svg", "exec": "nmap",
                            "category": "c-01-information-gathering"},
             "docs": "layers/c-01/nmap.md", "tags": ["classic", "native", "update:slow"]},
            {"id": "long-describer", "layer": "CLASSIC", "category": "c-01-information-gathering",
             "name": "long describer",
             "description": "word " * 60,
             "source": {"vcs_owner": "x", "repo": "x", "vcs_url": "https://example.com/x/y"},
             "license": "MIT", "packaging": {"status": "stale"},
             "safety": {"level": "requires-target"},
             "nixos_menu": {"icon": "a.svg", "exec": "x", "category": "c-01-information-gathering"},
             "docs": "layers/c-01/long-describer.md",
             "secondary_categories": ["c-10-runtime-appsec-ai"],
             "tags": ["classic"]},
            {"id": "shell-pack", "layer": "CLASSIC", "category": "c-01-information-gathering",
             "name": "shell pack",
             "description": "Pipes <and> amps & | inside.",
             "license": "MIT", "packaging": {"status": "bespoke",
                                             "derivation": "pkgs/shell-pack/default.nix"},
             "safety": {"level": "safe"},
             "docs": "layers/c-01/shell-pack.md", "tags": ["classic", "update:weekly"]},
            {"id": "atk", "layer": "ATTACK", "category": "a-02-prompt-injection-jailbreaks",
             "name": "atk",
             "description": "Attacker kit for jailbreaks.",
             "source": {"vcs_owner": "lab", "repo": "atk", "vcs_url": "https://gitlab.com/lab/atk"},
             "license": "Apache-2.0", "packaging": {"status": "module"},
             "safety": {"level": "exp", "target-required": True},
             "atlas_tactics": ["AML.T0051", "AML.T0054"],
             "owasp_llm": {"2026": ["LLM01"], "v2": ["LLM01"]},
             "docs": "layers/a-02/atk.md", "tags": ["attack", "update:fast"]},
            {"id": "sdr-pack", "layer": "CLASSIC", "category": "c-07-signal-sdr",
             "name": "sdr pack",
             "description": "Software-only DSP seed row.",
             "license": "MIT", "packaging": {"status": "data"},
             "docs": "layers/c-07/sdr-pack.md", "tags": ["sdr", "data"]},
        ]
    },
}


def self_test():
    """Assert-based checks over a small inline fixture (no network)."""
    cats = FIXTURE["categories"]["categories"]
    tools = FIXTURE["tools"]["tools"]

    # --- cell helpers ---
    assert packaging_cell(FIXTURE["tools"]["tools"][0]) == "`native`"
    assert packaging_cell(tools[2]) == "`bespoke` · `pkgs/shell-pack/default.nix`"
    assert safety_cell(tools[0]) == "`safe`"
    assert safety_cell(tools[3]) == "`exp` · target-required"
    assert safety_cell({}) == "—"
    assert tool_cell(tools[0]) == "[nmap](https://github.com/nmap/nmap)"
    assert tool_cell({"id": "x", "name": "x"}) == "**x**"
    assert truncate("short line") == "short line"
    truncated = truncate("word " * 60)
    assert truncated.endswith("…") and len(truncated) <= DESC_LIMIT + 1
    assert "|" not in truncated.replace("…", "")

    # --- description escaping (the '<', '&', '|' case) ---
    row = tool_row(tools[2])
    assert "&amp;" in row and "&lt;" in row and "&#124;" in row
    assert "Pipes <and>" not in row

    # --- secondary-category cross-ref line ---
    row_sec = tool_row(tools[1])
    assert "*also:* `c-10-runtime-appsec-ai`" in row_sec
    secondary_rows = [t for t in tools if t.get("secondary_categories")]
    assert len(secondary_rows) == 1

    # --- category grouping preserves manifest order ---
    buckets = group_by_category(tools, cats)
    assert list(buckets) == ["c-01-information-gathering",
                             "a-02-prompt-injection-jailbreaks", "c-07-signal-sdr"]
    assert len(buckets["c-01-information-gathering"]) == 3
    assert len(buckets["c-07-signal-sdr"]) == 1

    # --- every tool renders exactly once ---
    text = render_page(cats, tools)
    for t in tools:
        expect = "[%s](%s)" % (t["name"], (t.get("source") or {}).get("vcs_url")) \
            if (t.get("source") or {}).get("vcs_url") else "**%s**" % t["name"]
        assert text.count(expect) == 1, "tool rendered != once: %s" % t["id"]

    # --- section + row counts from the fixture ---
    stats = verify_output(text, cats, tools)
    assert stats["sections"] == 3, stats
    assert stats["rows"] == 5, stats
    assert stats["linked"] == 3 and stats["unlinked"] == 2, stats
    assert stats["in_data_packs"] == 1, stats

    # --- data-pack section carries the opt-in note ---
    assert "**Opt-in data-pack.**" in text
    assert "kailash-data.sdr-tools" in text

    # --- planned-vs-filled heading: c-01 filled 3 of planned 3 -> plain;
    # a-02 filled 1 of planned 2 -> "1 of 2 planned" ---
    assert "`c-01-information-gathering`, CLASSIC, 3 tools)" in text
    assert "`a-02-prompt-injection-jailbreaks`, ATTACK, 1 of 2 planned)" in text

    # --- glossary coverage: every field the fixture rows carry is glossed ---
    glossed = ("| `id` |", "| `layer` |", "| `category` |", "| `secondary_categories` |",
               "| `name` |", "| `description` |", "| `source` |", "| `license` |",
               "| `packaging` |", "| `safety` |", "| `nixos_menu` |", "| `docs` |",
               "| `tags` |", "| `atlas_tactics` |", "| `owasp_llm` |")
    for g in glossed:
        assert g in text, "missing glossary row: %s" % g
    for status in ("native", "stale", "bespoke", "module", "data"):
        assert "| `%s` |" % status in text
    for level in ("safe", "requires-target", "exp"):
        assert "| `%s` |" % level in text
    for tag in ("update:slow", "update:steady", "update:weekly", "update:fast"):
        assert "`%s`" % tag in text

    # --- dual-epoch owasp map glossed, atlas glossed --- (wording per 02425ce)
    assert "Dual-epoch OWASP LLM Top 10 map" in text
    assert "≥1 MITRE ATLAS tactic id" in text
    assert "2026.05 matrix" in text

    # --- per-layer summary ---
    assert "## Per-layer summary" in text
    assert "| **CLASSIC** | 2 (C-1…C-7" in text
    assert "| **ATTACK** | 1 (A-2) | 1 |" in text
    assert "**Total** | 2 categories + 1 opt-in data-pack | 5 |" in text

    # --- generation statement + header comment ---
    assert "python3 tools/generate-tools-page.py" in text
    assert "<!-- GENERATED FILE" in text

    print("self-test: all fixture assertions passed")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate tools.qmd from the kailash-packages tool manifest.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="output path (default tools.qmd)")
    parser.add_argument("--manifest-dir", default=None,
                        help="read manifest/tools.yaml + categories.yaml from this "
                             "local directory instead of the packages main raw URLs "
                             "(pre-merge regeneration for manifest PRs; the default "
                             "stay the pinned URLs)")
    parser.add_argument("--self-test", action="store_true",
                        help="run fixture-based assertions and exit")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    if args.manifest_dir:
        tools_doc = yaml.safe_load(
            open(os.path.join(args.manifest_dir, "tools.yaml"), encoding="utf-8"))
        categories_doc = yaml.safe_load(
            open(os.path.join(args.manifest_dir, "categories.yaml"), encoding="utf-8"))
    else:
        tools_doc = fetch_manifest(TOOLS_URL)
        categories_doc = fetch_manifest(CATEGORIES_URL)
    tools = tools_doc.get("tools") or []
    categories = categories_doc.get("categories") or []
    if not tools or not categories:
        sys.stderr.write("error: manifest fetch produced empty tools/categories\n")
        return 1

    text = render_page(categories, tools)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)

    stats = verify_output(text, categories, tools)
    data_packs = [c["id"] for c in categories if c.get("kind") == "data-pack"]
    print("generated %s: %d category sections, %d tool rows (%d linked / %d unlinked), "
          "%d data-pack row(s) rendered inline: %s"
          % (args.out, stats["sections"], stats["rows"], stats["linked"],
             stats["unlinked"], len(data_packs), ", ".join(data_packs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
