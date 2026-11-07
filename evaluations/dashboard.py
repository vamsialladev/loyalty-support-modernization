"""The evaluation-only comparison page (UI-02; spec B.13). A static file, never served by the app.

It holds labels-based results, so operational users never see it: the app's routes don't reach it. It shows the
generated reports in full, in a fixed order, so nothing can be picked out.

    uv run python -m evaluations.dashboard
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from evaluations.final_report import OUT

ORDER = (
    "hypotheses.md",
    "comparison.md",
    "a-or-b-beats-c.md",
    "a-as-is.md",
    "after-stop-sensitivity.md",
    "fairness.md",
    "stress.md",
    "variability.md",
    "predicted-vs-actual.md",
    "business-value.md",
)
STYLE = """
:root { color-scheme: light dark; --bg: #f7f4ee; --ink: #1c1f1d; --line: #e3ddd2; --muted: #5b625e; }
@media (prefers-color-scheme: dark) { :root { --bg: #111613; --ink: #ece8e0; --line: #26302b; --muted: #a3aba6; } }
body { background: var(--bg); color: var(--ink); font: 16px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 75rem;
  padding: 1rem; }
table { border-collapse: collapse; display: block; overflow-x: auto; margin: 1rem 0; }
th, td { border: 1px solid var(--line); padding: .35rem .6rem; text-align: left; vertical-align: top; }
blockquote { border-left: 3px solid var(--line); color: var(--muted); margin: 1rem 0; padding-left: 1rem; }
nav a { margin-right: 1rem; }
"""


def inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)


def render(markdown: str) -> str:
    """The small part of Markdown these reports use. Everything is escaped first."""
    out: list[str] = []
    in_table = in_list = False
    for line in markdown.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")] if line.startswith("|") else None
        if in_table and cells is None:
            out.append("</table>")
            in_table = False
        if in_list and not line.startswith("- "):
            out.append("</ul>")
            in_list = False
        if cells is not None:
            if set(line) <= set("|- "):
                continue
            tag = "th" if not in_table else "td"
            if not in_table:
                out.append("<table>")
                in_table = True
            out.append("<tr>" + "".join(f"<{tag}>{inline(cell)}</{tag}>" for cell in cells) + "</tr>")
        elif line.startswith("# "):
            out.append(f"<h2>{inline(line[2:])}</h2>")
        elif line.startswith("## "):
            out.append(f"<h3>{inline(line[3:])}</h3>")
        elif line.startswith("> "):
            out.append(f"<blockquote>{inline(line[2:])}</blockquote>")
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(line[2:])}</li>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    if in_table:
        out.append("</table>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def build(folder: Path = OUT) -> str:
    sections = []
    links = []
    for name in ORDER:
        path = folder / name
        if not path.exists():
            continue
        anchor = name.removesuffix(".md")
        links.append(f'<a href="#{anchor}">{anchor}</a>')
        sections.append(f'<section id="{anchor}">{render(path.read_text(encoding="utf-8"))}</section>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Benchmark Results</title><style>{STYLE}</style></head><body>"
        "<h1>Benchmark results: arms A, B and C</h1>"
        "<p><strong>Independent portfolio simulation. Synthetic data, fictional hotel group.</strong> "
        "Evaluation only: not part of the console.</p>"
        f"<nav>{''.join(links)}</nav>{''.join(sections)}</body></html>\n"
    )


def main() -> int:
    target = OUT / "dashboard.html"
    target.write_text(build(), encoding="utf-8", newline="\n")
    print(f"wrote {target.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
