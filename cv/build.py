#!/usr/bin/env python3
"""Generate LaTeX (-> PDF) and HTML from cv.md, the single source of truth.

Usage:
    python3 cv/build.py            # writes cv/out/cv.tex and updates the HTML page
    python3 cv/build.py --tex-only # skip the HTML page

Markdown contract (see cv.md):
    ---                       YAML frontmatter: name, title, contact fields
    ## Section               a CV section
    <!-- entry-layout: X --> optional section layout: stacked (default) | inline | list
    ### A | B | C            an entry: title | subtitle | meta
    ### Heading              a skill group (no pipes)
    - bullet                 list item, **bold**, `code` and [text](url) supported
    plain text               paragraph
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CV_MD = ROOT / "cv" / "cv.md"
OUT_DIR = ROOT / "cv" / "out"
HTML_PAGE = ROOT / "willian_cesar_cv_professional.html"
PDF_TARGET = ROOT / "assets" / "willian_cesar_cv_professional.pdf"

HTML_BEGIN = "<!-- CV:BEGIN generated from cv/cv.md - do not edit by hand -->"
HTML_END = "<!-- CV:END -->"


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
@dataclass
class Entry:
    title: str
    subtitle: str
    meta: str
    items: list[str] = field(default_factory=list)


@dataclass
class Group:
    heading: str
    items: list[str] = field(default_factory=list)


@dataclass
class Section:
    title: str
    layout: str = "stacked"
    paragraphs: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    blocks: list[Entry | Group] = field(default_factory=list)


@dataclass
class Document:
    meta: dict
    sections: list[Section]


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse(md_text: str) -> Document:
    if not md_text.startswith("---"):
        raise SystemExit("cv.md must start with YAML frontmatter")
    _, fm, body = md_text.split("---", 2)
    meta = yaml.safe_load(fm) or {}

    sections: list[Section] = []
    section: Section | None = None
    block: Entry | Group | None = None
    para: list[str] = []

    def flush_para() -> None:
        nonlocal para
        if para and section is not None:
            section.paragraphs.append(" ".join(para))
        para = []

    for raw in body.splitlines():
        line = raw.rstrip()

        layout = re.match(r"^<!--\s*entry-layout:\s*(\S+)\s*-->$", line.strip())
        if layout:
            if section is None:
                raise SystemExit("entry-layout comment outside a section")
            section.layout = layout.group(1)
            continue

        if line.startswith("## "):
            flush_para()
            section = Section(title=line[3:].strip())
            sections.append(section)
            block = None
            continue

        if line.startswith("### "):
            flush_para()
            if section is None:
                raise SystemExit(f"'### {line[4:]}' appears before any '## Section'")
            head = line[4:].strip()
            if "|" in head:
                parts = [p.strip() for p in head.split("|")]
                parts += [""] * (3 - len(parts))
                block = Entry(title=parts[0], subtitle=parts[1], meta=parts[2])
            else:
                block = Group(heading=head)
            section.blocks.append(block)
            continue

        if line.startswith("- "):
            flush_para()
            item = line[2:].strip()
            if block is not None:
                block.items.append(item)
            elif section is not None:
                section.items.append(item)
            continue

        if not line.strip():
            flush_para()
            continue

        if block is None:
            para.append(line.strip())
        else:
            # continuation of the previous bullet
            if block.items:
                block.items[-1] += " " + line.strip()

    flush_para()
    return Document(meta=meta, sections=sections)


# --------------------------------------------------------------------------- #
# Inline formatting
# --------------------------------------------------------------------------- #
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

TEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def tex_escape(text: str) -> str:
    return "".join(TEX_ESCAPES.get(ch, ch) for ch in text)


def to_tex(text: str) -> str:
    """Markdown inline -> LaTeX, escaping only the literal parts."""
    out: list[str] = []
    pos = 0
    pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)|\*\*(.+?)\*\*|`([^`]+)`")
    for m in pattern.finditer(text):
        out.append(tex_escape(text[pos : m.start()]))
        if m.group(3) is not None:
            out.append(r"\textbf{" + tex_escape(m.group(3)) + "}")
        elif m.group(4) is not None:
            out.append(r"\texttt{" + tex_escape(m.group(4)) + "}")
        else:
            label, url = m.group(1), m.group(2)
            out.append(r"\href{" + url.replace("%", r"\%") + "}{" + tex_escape(label) + "}")
        pos = m.end()
    out.append(tex_escape(text[pos:]))
    return "".join(out)


def to_html(text: str) -> str:
    """Markdown inline -> HTML, escaping only the literal parts."""
    out: list[str] = []
    pos = 0
    pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)|\*\*(.+?)\*\*|`([^`]+)`")
    for m in pattern.finditer(text):
        out.append(html.escape(text[pos : m.start()]))
        if m.group(3) is not None:
            out.append("<strong>" + html.escape(m.group(3)) + "</strong>")
        elif m.group(4) is not None:
            out.append("<code>" + html.escape(m.group(4)) + "</code>")
        else:
            label, url = m.group(1), m.group(2)
            out.append(
                f'<a href="{html.escape(url, quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{html.escape(label)}</a>'
            )
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# --------------------------------------------------------------------------- #
# LaTeX renderer
# --------------------------------------------------------------------------- #
PREAMBLE = r"""% !TeX program = pdflatex
% ---------------------------------------------------------------------------
% GENERATED FILE - do not edit.
% Source of truth: cv/cv.md   Regenerate with: python3 cv/build.py
% ---------------------------------------------------------------------------
\documentclass[11pt,a4paper]{article}

\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage[margin=1.9cm,top=1.6cm,bottom=1.8cm]{geometry}
\usepackage[dvipsnames]{xcolor}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{fontawesome5}
\usepackage{microtype}
\usepackage[hidelinks]{hyperref}

\definecolor{cvprimary}{HTML}{2C3E50}
\definecolor{cvaccent}{HTML}{34618E}
\definecolor{cvrule}{HTML}{B9C4CF}

\hypersetup{
  colorlinks=true,
  urlcolor=cvaccent,
  linkcolor=cvaccent,
  pdftitle={__PDFTITLE__},
  pdfauthor={__PDFAUTHOR__}
}

\pagestyle{plain}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.35em}

\titleformat{\section}
  {\normalfont\large\bfseries\color{cvprimary}}
  {}{0pt}{}[{\color{cvrule}\titlerule[0.8pt]}]
\titlespacing*{\section}{0pt}{1.15em}{0.55em}

\titleformat{\subsection}
  {\normalfont\normalsize\bfseries\color{cvprimary}}
  {}{0pt}{}
\titlespacing*{\subsection}{0pt}{0.75em}{0.3em}

\setlist[itemize]{leftmargin=1.1em,itemsep=0.12em,parsep=0pt,topsep=0.25em,label=\textbullet}

% Entry with a subtitle line: \cventry{Title}{Subtitle}{Right meta}
\newcommand{\cventry}[3]{%
  \vspace{0.55em}%
  {\bfseries\color{cvprimary}#1}\hfill{\bfseries #3}\par
  \vspace{0.1em}{\itshape #2}\par
  \vspace{0.15em}%
}

% Entry rendered on a single line: \cvinline{Title}{Right meta}
\newcommand{\cvinline}[2]{%
  \vspace{0.55em}%
  {\bfseries\color{cvprimary}#1}\hfill{#2}\par
  \vspace{0.15em}%
}

\newcommand{\cvsep}{\hspace{0.5em}\textbullet\hspace{0.5em}}
"""


def render_tex(doc: Document) -> str:
    m = doc.meta
    out: list[str] = []
    preamble = PREAMBLE.replace("__PDFTITLE__", f"{m['name']} - CV")
    preamble = preamble.replace("__PDFAUTHOR__", m["name"])
    out.append(preamble)
    out.append(r"\begin{document}")
    out.append("")

    # Header
    out.append(r"\begin{center}")
    out.append(r"  {\LARGE\bfseries\color{cvprimary} " + tex_escape(m["name"]) + r"}\\[0.35em]")
    out.append(r"  {\large " + tex_escape(m["title"]) + r"}\\[0.7em]")
    line1 = [
        r"\faMapMarker\," + tex_escape(m["location"]),
        r"\faPhone\," + tex_escape(str(m["phone"])),
        r"\faEnvelope\,\href{mailto:%s}{%s}" % (m["email"], tex_escape(m["email"])),
    ]
    line2 = [
        r"\faLinkedin\,\href{https://linkedin.com/in/%s}{%s}"
        % (m["linkedin"], tex_escape(m["linkedin"])),
        r"\faGithub\,\href{https://github.com/%s}{%s}" % (m["github"], tex_escape(m["github"])),
    ]
    out.append(r"  {\small " + r"\cvsep ".join(line1) + r"}\\[0.25em]")
    out.append(r"  {\small " + r"\cvsep ".join(line2) + r"}")
    out.append(r"\end{center}")
    out.append(r"\vspace{0.4em}")
    out.append("")

    for section in doc.sections:
        out.append(r"\section*{" + tex_escape(section.title) + "}")
        out.append(r"\addcontentsline{toc}{section}{" + tex_escape(section.title) + "}")

        for para in section.paragraphs:
            out.append(to_tex(para))
            out.append("")

        if section.items:
            out.append(r"\begin{itemize}")
            for item in section.items:
                out.append(r"  \item " + to_tex(item))
            out.append(r"\end{itemize}")

        for block in section.blocks:
            if isinstance(block, Group):
                out.append(r"\subsection*{" + tex_escape(block.heading) + "}")
            elif section.layout == "inline":
                right = " - ".join(p for p in (block.subtitle, block.meta) if p)
                out.append(r"\cvinline{" + to_tex(block.title) + "}{" + to_tex(right) + "}")
            else:
                out.append(
                    r"\cventry{%s}{%s}{%s}"
                    % (to_tex(block.title), to_tex(block.subtitle), to_tex(block.meta))
                )
            if block.items:
                out.append(r"\begin{itemize}")
                for item in block.items:
                    out.append(r"  \item " + to_tex(item))
                out.append(r"\end{itemize}")
        out.append("")

    out.append(r"\end{document}")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# HTML renderer
# --------------------------------------------------------------------------- #
def render_html(doc: Document) -> str:
    m = doc.meta
    o: list[str] = []
    p = o.append

    p("            <!-- Header Section -->")
    p('            <header class="cv-header">')
    p(f'                <h1 class="cv-name">{html.escape(m["name"])}</h1>')
    p(f'                <p class="cv-title">{html.escape(m["title"])}</p>')
    p('                <div class="cv-contact">')
    contacts = [
        ("📍", html.escape(m["location"])),
        ("📞", html.escape(str(m["phone"]))),
        ("📧", f'<a href="mailto:{m["email"]}">{html.escape(m["email"])}</a>'),
        (
            "🔗",
            f'<a href="https://linkedin.com/in/{m["linkedin"]}" target="_blank" '
            f'rel="noopener noreferrer">{html.escape(m["linkedin"])}</a>',
        ),
        (
            "💻",
            f'<a href="https://github.com/{m["github"]}" target="_blank" '
            f'rel="noopener noreferrer">{html.escape(m["github"])}</a>',
        ),
    ]
    for icon, value in contacts:
        p('                    <div class="cv-contact-item">')
        p(f'                        <span aria-hidden="true">{icon}</span>')
        p(f"                        <span>{value}</span>" if not value.startswith("<a") else f"                        {value}")
        p("                    </div>")
    p("                </div>")
    p("            </header>")
    p("")

    for section in doc.sections:
        sid = f"{slug(section.title)}-heading"
        p(f"            <!-- {section.title} -->")
        p(f'            <section class="cv-section" aria-labelledby="{sid}">')
        p(f'                <h2 class="text-primary" id="{sid}">{html.escape(section.title)}</h2>')

        for para in section.paragraphs:
            p(f"                <p>{to_html(para)}</p>")

        if section.items:
            p('                <ul class="experience-achievements">')
            for item in section.items:
                p(f"                    <li>{to_html(item)}</li>")
            p("                </ul>")

        for block in section.blocks:
            if isinstance(block, Group):
                p('                <div class="mb-lg">')
                p(f"                    <h3>{html.escape(block.heading)}</h3>")
                p('                    <ul class="experience-achievements">')
                for item in block.items:
                    p(f"                        <li>{to_html(item)}</li>")
                p("                    </ul>")
                p("                </div>")
                continue

            p('                <div class="experience-item">')
            p('                    <div class="experience-header">')
            p("                        <div>")
            p(f'                            <h3 class="experience-title">{to_html(block.title)}</h3>')
            if block.subtitle:
                p(
                    f'                            <h4 class="experience-company">{to_html(block.subtitle)}</h4>'
                )
            p("                        </div>")
            if block.meta:
                p(
                    f'                        <span class="experience-period">{to_html(block.meta)}</span>'
                )
            p("                    </div>")
            if block.items:
                p('                    <ul class="experience-achievements">')
                for item in block.items:
                    p(f"                        <li>{to_html(item)}</li>")
                p("                    </ul>")
            p("                </div>")

        p("            </section>")
        p("")

    return "\n".join(o)


def inject_html(fragment: str) -> None:
    page = HTML_PAGE.read_text(encoding="utf-8")
    if HTML_BEGIN not in page or HTML_END not in page:
        raise SystemExit(
            f"{HTML_PAGE.name} is missing the {HTML_BEGIN!r} / {HTML_END!r} markers"
        )
    head, rest = page.split(HTML_BEGIN, 1)
    _, tail = rest.split(HTML_END, 1)
    HTML_PAGE.write_text(
        f"{head}{HTML_BEGIN}\n{fragment}\n            {HTML_END}{tail}", encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
def build_pdf(tex_path: Path) -> bool:
    if not shutil_which("pdflatex"):
        print("! pdflatex not found - skipping PDF (install texlive)", file=sys.stderr)
        return False
    for _ in range(2):  # two passes so \hfill/page numbers settle
        proc = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=tex_path.parent,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(proc.stdout[-4000:], file=sys.stderr)
            raise SystemExit("pdflatex failed")
    produced = tex_path.with_suffix(".pdf")
    PDF_TARGET.parent.mkdir(parents=True, exist_ok=True)
    PDF_TARGET.write_bytes(produced.read_bytes())
    return True


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex-only", action="store_true", help="do not touch the HTML page")
    ap.add_argument("--no-pdf", action="store_true", help="generate .tex but do not run pdflatex")
    args = ap.parse_args()

    doc = parse(CV_MD.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tex_path = OUT_DIR / "cv.tex"
    tex_path.write_text(render_tex(doc), encoding="utf-8")
    print(f"wrote {tex_path.relative_to(ROOT)}")

    if not args.tex_only:
        inject_html(render_html(doc))
        print(f"updated {HTML_PAGE.relative_to(ROOT)}")

    if not args.no_pdf and build_pdf(tex_path):
        print(f"wrote {PDF_TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
