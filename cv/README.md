# CV

`cv.md` is the **single source of truth**. The PDF and the HTML page are generated
outputs — never edit them by hand.

```
cv/cv.md  ──build.py──┬──▶ cv/out/cv.tex ──pdflatex──▶ assets/willian_cesar_cv_professional.pdf
                      └──▶ willian_cesar_cv_professional.html  (between the CV:BEGIN/CV:END markers)
```

## Build

```bash
python3 cv/build.py             # tex + pdf + html page
python3 cv/build.py --no-pdf    # skip pdflatex
python3 cv/build.py --tex-only  # tex (+pdf) only, leave the HTML page alone
```

## Dependencies

- Python 3 with `pyyaml`
- TeX Live: `sudo pacman -S --needed texlive-basic texlive-latex texlive-latexrecommended \
  texlive-latexextra texlive-fontsrecommended texlive-fontsextra texlive-bin`

## Markdown contract

| Syntax | Meaning |
|---|---|
| YAML frontmatter | `name`, `title`, `location`, `phone`, `email`, `linkedin`, `github` |
| `## Section` | a CV section |
| `<!-- entry-layout: inline \| list \| stacked -->` | how the section's entries render (default `stacked`) |
| `### Title \| Subtitle \| Meta` | an entry — title left, meta right, subtitle underneath |
| `### Heading` | a skill group (no pipes) |
| `- item` | bullet; supports `**bold**`, `` `code` `` and `[text](url)` |
| plain text | paragraph |

`inline` joins subtitle and meta on one right-hand line (used by Personal Projects).
`list` sections carry bullets directly, with no `###` entries.

## Note on the LaTeX

The original `.tex` for the 2025 PDF was lost, so `build.py` regenerates it from
scratch. The visual result is deliberately close to the original: A4, Latin Modern,
FontAwesome 5 contact icons, ruled section headings.

`fontawesome5` as packaged for Arch exposes `\faMapMarker` but **not**
`\faMapMarkerAlt` — keep that in mind before changing the contact icons.
