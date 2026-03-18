#!/usr/bin/env python3
"""
compute_stats.py — compute project metrics and update README.md.

Metrics
-------
- Total git additions / deletions (all commits reachable from HEAD)
- Monthly commit activity for the last 12 months  →  docs/stats/activity.svg
- Lines of code by language                        →  Mermaid pie in README
- Commits per author (sorted descending)
- Backend source LOC  (backend/app/**/*.py)
- Frontend source LOC (frontend/src/**/*.{ts,vue}, excl. test files)
- Backend test-case count  (def test_ / async def test_)
- Frontend test-case count (it( / test( calls in test files)
- Backend test LOC  / frontend test LOC  → test-to-source ratio
- REST API endpoint count  (@router.get/post/put/delete/patch)
- Alembic migration count
- Longest commit streak (consecutive calendar days with ≥1 commit)
- Top 5 largest source files by line count

Usage
-----
    python scripts/compute_stats.py
"""

import re
import subprocess
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATS_START = "<!-- STATS:START -->"
STATS_END = "<!-- STATS:END -->"

_TEST_NAME_RE = re.compile(r"\.(test|spec)\.(ts|js|tsx|jsx)$")
_TEST_DIR_RE = re.compile(r"[/\\]__tests__[/\\]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, text=True, cwd=ROOT).strip()


def _count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
    except OSError:
        return 0


def _is_test_file(path: Path) -> bool:
    s = str(path)
    return bool(_TEST_NAME_RE.search(path.name) or _TEST_DIR_RE.search(s))


def _fmt(n: int) -> str:
    return f"{n:,}"


# ---------------------------------------------------------------------------
# 1. Git additions / deletions
# ---------------------------------------------------------------------------

def git_additions_deletions() -> tuple[int, int]:
    output = _run("git log --numstat --pretty=format:")
    plus = minus = 0
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            plus += int(parts[0])
            minus += int(parts[1])
    return plus, minus


# ---------------------------------------------------------------------------
# 2. Per-author commit counts
# ---------------------------------------------------------------------------

# Aliases: map alternate names → canonical display name.
# Add entries here whenever the same person commits under different identities.
_AUTHOR_ALIASES: dict[str, str] = {
    "Leo": "Isaries",
}


def git_author_stats() -> list[tuple[int, str, int, int]]:
    """Returns list of (commits, name, additions, deletions) sorted by commits desc."""
    output = _run("git log --numstat --pretty=format:COMMIT:%an HEAD")
    commit_counts: defaultdict[str, int] = defaultdict(int)
    adds: defaultdict[str, int] = defaultdict(int)
    dels: defaultdict[str, int] = defaultdict(int)
    current: str | None = None
    for line in output.splitlines():
        if line.startswith("COMMIT:"):
            raw = line[7:].strip()
            current = _AUTHOR_ALIASES.get(raw, raw)
            commit_counts[current] += 1
        elif current and "\t" in line:
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                adds[current] += int(parts[0])
                dels[current] += int(parts[1])
    result = [
        (commit_counts[n], n, adds[n], dels[n])
        for n in commit_counts
    ]
    return sorted(result, reverse=True)


# ---------------------------------------------------------------------------
# 3. Monthly commits for the last 12 months
# ---------------------------------------------------------------------------

def monthly_commits(months: int = 12) -> list[tuple[str, int]]:
    output = _run("git log --format=%as HEAD")
    counts: defaultdict[str, int] = defaultdict(int)
    for line in output.splitlines():
        line = line.strip()
        if len(line) >= 7:
            counts[line[:7]] += 1  # "YYYY-MM"

    today = date.today()
    result: list[tuple[str, int]] = []
    for i in range(months - 1, -1, -1):
        total_m = today.year * 12 + (today.month - 1) - i
        y, m = total_m // 12, (total_m % 12) + 1
        ym = f"{y}-{m:02d}"
        label = date(y, m, 1).strftime("%b")
        if m == 1:
            label = f"Jan'{str(y)[2:]}"
        result.append((label, counts.get(ym, 0)))
    return result


# ---------------------------------------------------------------------------
# 4. Longest commit streak (consecutive days)
# ---------------------------------------------------------------------------

def longest_commit_streak() -> int:
    output = _run("git log --format=%as HEAD")
    unique: set[date] = set()
    for line in output.splitlines():
        line = line.strip()
        if line:
            try:
                unique.add(date.fromisoformat(line))
            except ValueError:
                pass
    if not unique:
        return 0
    sorted_days = sorted(unique)
    max_streak = cur = 1
    for i in range(1, len(sorted_days)):
        if (sorted_days[i] - sorted_days[i - 1]).days == 1:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 1
    return max_streak


# ---------------------------------------------------------------------------
# 5. Backend source LOC  (backend/app/**/*.py)
# ---------------------------------------------------------------------------

def backend_loc() -> int:
    return sum(
        _count_lines(p)
        for p in (ROOT / "backend" / "app").rglob("*.py")
    )


# ---------------------------------------------------------------------------
# 6. Frontend source LOC  (frontend/src/**/*.{ts,vue}, excl. test files)
# ---------------------------------------------------------------------------

def frontend_loc() -> int:
    total = 0
    src = ROOT / "frontend" / "src"
    for ext in ("*.ts", "*.vue"):
        for path in src.rglob(ext):
            if not _is_test_file(path):
                total += _count_lines(path)
    return total


# ---------------------------------------------------------------------------
# 7. Language breakdown (all source, incl. tests, for a full picture)
# ---------------------------------------------------------------------------

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}
_EXT_TO_LANG = {".py": "Python", ".ts": "TypeScript", ".vue": "Vue", ".css": "CSS"}


def language_breakdown() -> dict[str, int]:
    counts: defaultdict[str, int] = defaultdict(int)
    for base in (ROOT / "backend", ROOT / "frontend" / "src"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            lang = _EXT_TO_LANG.get(path.suffix.lower())
            if lang:
                counts[lang] += _count_lines(path)
    return dict(counts)


# ---------------------------------------------------------------------------
# 8. Backend test count  (def test_ / async def test_)
# ---------------------------------------------------------------------------

def backend_test_count() -> int:
    count = 0
    for path in (ROOT / "backend" / "tests").rglob("test_*.py"):
        try:
            for line in path.open("r", encoding="utf-8", errors="ignore"):
                s = line.lstrip()
                if s.startswith("def test_") or s.startswith("async def test_"):
                    count += 1
        except OSError:
            pass
    return count


# ---------------------------------------------------------------------------
# 9. Frontend test count  (it( / test( calls in test files)
# ---------------------------------------------------------------------------

_IT_TEST_RE = re.compile(r"^\s*(it|test)\s*\(")


def frontend_test_count() -> int:
    count = 0
    for ext in ("*.test.ts", "*.spec.ts", "*.test.js", "*.spec.js"):
        for path in (ROOT / "frontend" / "src").rglob(ext):
            try:
                for line in path.open("r", encoding="utf-8", errors="ignore"):
                    if line.lstrip().startswith("//"):
                        continue
                    if _IT_TEST_RE.match(line):
                        count += 1
            except OSError:
                pass
    return count


# ---------------------------------------------------------------------------
# 10. Test LOC (backend + frontend)
# ---------------------------------------------------------------------------

def backend_test_loc() -> int:
    return sum(
        _count_lines(p)
        for p in (ROOT / "backend" / "tests").rglob("*.py")
    )


def frontend_test_loc() -> int:
    total = 0
    for ext in ("*.test.ts", "*.spec.ts", "*.test.js", "*.spec.js"):
        for path in (ROOT / "frontend" / "src").rglob(ext):
            total += _count_lines(path)
    return total


# ---------------------------------------------------------------------------
# 11. REST API endpoint count
# ---------------------------------------------------------------------------

_ROUTE_RE = re.compile(r"@router\.(get|post|put|delete|patch|head|options)\s*\(")


def api_endpoint_count() -> int:
    count = 0
    for path in (ROOT / "backend" / "app").rglob("*.py"):
        try:
            for line in path.open("r", encoding="utf-8", errors="ignore"):
                if _ROUTE_RE.search(line):
                    count += 1
        except OSError:
            pass
    return count


# ---------------------------------------------------------------------------
# 12. Alembic migration count
# ---------------------------------------------------------------------------

def migration_count() -> int:
    versions = ROOT / "backend" / "alembic" / "versions"
    if not versions.exists():
        return 0
    return sum(
        1 for p in versions.glob("*.py")
        if p.name != "__init__.py" and not p.name.startswith("__")
    )


# ---------------------------------------------------------------------------
# 13. Top N largest source files by LOC
# ---------------------------------------------------------------------------

_TOP_SKIP_RE = re.compile(r"(test_|\.test\.|\.spec\.|__tests__|[/\\]locales[/\\])")


def top_files_by_loc(n: int = 5) -> list[tuple[str, int]]:
    files: list[tuple[int, str]] = []
    for base in (ROOT / "backend" / "app", ROOT / "frontend" / "src"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".ts", ".vue"}:
                continue
            if _TOP_SKIP_RE.search(str(path)):
                continue
            loc = _count_lines(path)
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            files.append((loc, rel))
    files.sort(reverse=True)
    return [(rel, loc) for loc, rel in files[:n]]


# ---------------------------------------------------------------------------
# SVG: monthly commit activity bar chart
# ---------------------------------------------------------------------------

def generate_activity_svg(monthly: list[tuple[str, int]]) -> Path:
    W, H = 640, 160
    PAD_L, PAD_R = 12, 12
    TITLE_H, LABEL_H = 25, 28
    BOT = H - LABEL_H          # 132 — baseline y
    TOP = TITLE_H              # 25  — chart top y
    CHART_H = BOT - TOP        # 107
    CHART_W = W - PAD_L - PAD_R  # 616

    n = len(monthly)
    slot_w = CHART_W / n
    bar_w = slot_w * 0.65
    bar_off = (slot_w - bar_w) / 2
    max_count = max(c for _, c in monthly) or 1

    p: list[str] = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    p.append("""<style>
  .t{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
  @media(prefers-color-scheme:dark){
    .bg{fill:#161b22}.bar{fill:#388bfd}.axis{stroke:#30363d}
    .lbl{fill:#8b949e}.cnt{fill:#c9d1d9}.ttl{fill:#e6edf3}
  }
  @media(prefers-color-scheme:light),(prefers-color-scheme:no-preference){
    .bg{fill:#f6f8fa}.bar{fill:#0969da}.axis{stroke:#d0d7de}
    .lbl{fill:#57606a}.cnt{fill:#24292f}.ttl{fill:#24292f}
  }
</style>""")
    p.append(f'<rect width="{W}" height="{H}" class="bg" rx="8"/>')
    p.append(
        f'<text x="{W//2}" y="17" text-anchor="middle" '
        f'font-size="12" font-weight="600" class="t ttl">'
        f'Commit Activity \u2014 Last 12 Months</text>'
    )
    p.append(
        f'<line x1="{PAD_L}" y1="{BOT}" x2="{W-PAD_R}" y2="{BOT}" '
        f'class="axis" stroke-width="1"/>'
    )

    for i, (label, count) in enumerate(monthly):
        bh = (count / max_count) * CHART_H
        bx = PAD_L + i * slot_w + bar_off
        by = BOT - bh
        cx = PAD_L + i * slot_w + slot_w / 2  # horizontal center of slot

        if bh >= 2:
            rx = min(3.0, bh / 2)
            p.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                f'height="{bh:.1f}" class="bar" rx="{rx:.1f}"/>'
            )
        if count > 0 and bh >= 18:
            # Place label above bar; if it would overlap the title area,
            # fall back to inside the bar top.
            label_y = by - 4
            if label_y < TOP + 6:
                label_y = by + 12
            p.append(
                f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" '
                f'font-size="9" class="t cnt">{count}</text>'
            )
        p.append(
            f'<text x="{cx:.1f}" y="{BOT + 16:.0f}" text-anchor="middle" '
            f'font-size="10" class="t lbl">{label}</text>'
        )

    p.append("</svg>")

    out = ROOT / "docs" / "stats" / "activity.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(p), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Build the README stats block
# ---------------------------------------------------------------------------

def build_stats_block(
    plus: int,
    minus: int,
    authors: list[tuple[int, str, int, int]],
    be_loc: int,
    fe_loc: int,
    be_tests: int,
    fe_tests: int,
    be_test_loc: int,
    fe_test_loc: int,
    lang: dict[str, int],
    endpoints: int,
    migrations: int,
    streak: int,
    top_files: list[tuple[str, int]],
) -> str:
    today = date.today().isoformat()
    total_source = be_loc + fe_loc
    total_test_loc = be_test_loc + fe_test_loc
    ratio = total_test_loc / total_source if total_source else 0

    rows: list[str] = [
        STATS_START,
        f"_Last updated: {today} \u2014 auto-generated on every push to `main`_",
        "",
        "### Code Volume",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Total lines added (all commits) | +{_fmt(plus)} |",
        f"| Total lines removed (all commits) | -{_fmt(minus)} |",
        f"| Backend source lines (excl. tests) | {_fmt(be_loc)} |",
        f"| Frontend source lines (excl. tests) | {_fmt(fe_loc)} |",
        "",
        "### Language Breakdown",
        "",
    ]

    # Mermaid pie — only languages with meaningful LOC
    rows.append("```mermaid")
    rows.append("pie title Lines of Code by Language")
    for lang_name, loc in sorted(lang.items(), key=lambda x: -x[1]):
        if loc > 50:
            rows.append(f'    "{lang_name}" : {loc}')
    rows.append("```")

    rows += [
        "",
        "### Commit Activity",
        "",
        "![Commit activity over the last 12 months](docs/stats/activity.svg)",
        "",
        "### Test Coverage",
        "",
        "| Suite | Test cases | Source lines | Test lines |",
        "| --- | ---: | ---: | ---: |",
        f"| Backend (pytest) | {_fmt(be_tests)} | {_fmt(be_loc)} | {_fmt(be_test_loc)} |",
        f"| Frontend (Vitest) | {_fmt(fe_tests)} | {_fmt(fe_loc)} | {_fmt(fe_test_loc)} |",
        f"| **Total** | **{_fmt(be_tests + fe_tests)}** | **{_fmt(total_source)}** | **{_fmt(total_test_loc)}** |",
        "",
        f"Test-to-source ratio: **{ratio:.2f}** "
        f"({_fmt(total_test_loc)} lines of tests for every {_fmt(total_source)} lines of source)",
        "",
        "### Additional Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| REST API endpoints | {_fmt(endpoints)} |",
        f"| Database migrations | {_fmt(migrations)} |",
        f"| Longest commit streak | {streak} days |",
        "",
        "### Top 5 Largest Source Files",
        "",
        "| File | Lines |",
        "| --- | ---: |",
    ]
    for rel, loc in top_files:
        rows.append(f"| `{rel}` | {_fmt(loc)} |")

    rows += [
        "",
        "### Contributions by Author",
        "",
        "| Author | Commits | Lines added | Lines removed |",
        "| --- | ---: | ---: | ---: |",
    ]
    for commits, author, a, d in authors:
        rows.append(f"| {author} | {_fmt(commits)} | +{_fmt(a)} | -{_fmt(d)} |")

    rows.append("")
    rows.append(STATS_END)
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Update README.md
# ---------------------------------------------------------------------------

def update_readme(block: str) -> bool:
    readme = ROOT / "README.md"
    original = readme.read_text(encoding="utf-8")

    if STATS_START in original and STATS_END in original:
        pattern = re.compile(
            re.escape(STATS_START) + r".*?" + re.escape(STATS_END),
            re.DOTALL,
        )
        updated = pattern.sub(lambda _: block, original)
    else:
        insert_before = "## Documentation"
        if insert_before in original:
            updated = original.replace(
                insert_before,
                f"## Project Stats\n\n{block}\n\n---\n\n{insert_before}",
                1,
            )
        else:
            updated = original.rstrip() + f"\n\n## Project Stats\n\n{block}\n"

    if updated == original:
        return False
    readme.write_text(updated, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Computing git additions/deletions…")
    plus, minus = git_additions_deletions()
    print(f"  +{_fmt(plus)} / -{_fmt(minus)}")

    print("Computing author commit counts…")
    authors = git_author_stats()
    for commits, author, a, d in authors:
        print(f"  {commits:>6,}  {author}  +{_fmt(a)} / -{_fmt(d)}")

    print("Computing monthly commit activity…")
    monthly = monthly_commits()
    for label, count in monthly:
        print(f"  {label:>8}  {count}")

    print("Computing longest commit streak…")
    streak = longest_commit_streak()
    print(f"  {streak} days")

    print("Counting backend source LOC…")
    be_loc = backend_loc()
    print(f"  {_fmt(be_loc)} lines")

    print("Counting frontend source LOC…")
    fe_loc = frontend_loc()
    print(f"  {_fmt(fe_loc)} lines")

    print("Computing language breakdown…")
    lang = language_breakdown()
    for name, loc in sorted(lang.items(), key=lambda x: -x[1]):
        print(f"  {name:>12}  {_fmt(loc)} lines")

    print("Counting backend test cases…")
    be_tests = backend_test_count()
    print(f"  {_fmt(be_tests)} test cases")

    print("Counting frontend test cases…")
    fe_tests = frontend_test_count()
    print(f"  {_fmt(fe_tests)} test cases")

    print("Counting backend test LOC…")
    be_tl = backend_test_loc()
    print(f"  {_fmt(be_tl)} lines")

    print("Counting frontend test LOC…")
    fe_tl = frontend_test_loc()
    print(f"  {_fmt(fe_tl)} lines")

    print("Counting API endpoints…")
    endpoints = api_endpoint_count()
    print(f"  {_fmt(endpoints)} endpoints")

    print("Counting migrations…")
    migrations = migration_count()
    print(f"  {_fmt(migrations)} migrations")

    print("Finding top 5 largest source files…")
    top_files = top_files_by_loc()
    for rel, loc in top_files:
        print(f"  {_fmt(loc):>6}  {rel}")

    print("Generating activity SVG…")
    svg_path = generate_activity_svg(monthly)
    print(f"  Written to {svg_path.relative_to(ROOT)}")

    block = build_stats_block(
        plus, minus, authors,
        be_loc, fe_loc,
        be_tests, fe_tests,
        be_tl, fe_tl,
        lang, endpoints, migrations, streak, top_files,
    )
    changed = update_readme(block)
    if changed:
        print("README.md updated.")
    else:
        print("README.md already up to date — no changes written.")


if __name__ == "__main__":
    main()
