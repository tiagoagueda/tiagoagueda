#!/usr/bin/env python3
"""Render the templates in src/ into one profile README per site and language.

    python build.py            write every README
    python build.py --check    change nothing; exit 1 if a README is out of date

The same commit is pushed to both sites, and each one picks different files:

    Forgejo  shows the README at the repository root, in the visitor's
             interface language when there is one: README.fr.md for French,
             README.pt.md for Portuguese, README.md for everyone else. It only
             looks inside .github/ when the root has no README.
    GitHub   prefers .github/README.md over the root one when both exist, for
             the profile as well as for the repository page, and shows it to
             everyone. The other languages are reached through the flag links
             at the top.

So edit the files in src/, never the READMEs: they are overwritten on every build.

    src/profile.md       English, the default
    src/profile.fr.md    French
    src/profile.pt.md    Portuguese
    src/parts/           blocks shared by all languages (badges)

Template syntax:

    <!-- include: parts/contact.md -->    replaced by that file, relative to src/

    <!-- only: github -->                 the lines up to the matching "end" are
    ...                                   kept for that site and dropped for
    <!-- end -->                          the others

    {{me}}                                replaced by the value from COMMON or
                                          from the site's entry in SITES below
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "src"

# Language -> what goes between "profile"/"README" and ".md". English is the default.
LANGUAGES = {"en": "", "fr": ".fr", "pt": ".pt"}

FLAGS = "https://cdn.jsdelivr.net/npm/flag-icons@7.6.0/flags/4x3"


def flag(country: str) -> str:
    # An image, because Windows has no glyphs for flag emoji.
    return f'<img src="{FLAGS}/{country}.svg" width="16" alt="">'


COMMON = {
    "flag_en": flag("gb"),
    "flag_fr": flag("fr"),
    "flag_pt": flag("pt"),
}

FORGEJO_FILES = "https://source.tiagoagueda.com/tiagoagueda/.profile/src/branch/main"
GITHUB_FILES = "https://github.com/tiagoagueda/tiagoagueda/blob/main/.github"

SITES = {
    "forgejo": {
        "directory": "",
        "vars": {
            "me": "https://source.tiagoagueda.com/tiagoagueda",
            "postulo": "https://source.tiagoagueda.com/postulo/postulo",
            # The profile page follows the visitor's language, so the links
            # to a given language go to the file itself.
            "en": f"{FORGEJO_FILES}/README.md",
            "fr": f"{FORGEJO_FILES}/README.fr.md",
            "pt": f"{FORGEJO_FILES}/README.pt.md",
        },
    },
    "github": {
        "directory": ".github",
        "vars": {
            "me": "https://github.com/tiagoagueda",
            "postulo": "https://github.com/tiagoagueda/postulo",
            "en": "https://github.com/tiagoagueda",
            "fr": f"{GITHUB_FILES}/README.fr.md",
            "pt": f"{GITHUB_FILES}/README.pt.md",
        },
    },
}

INCLUDE = re.compile(r"^\s*<!--\s*include:\s*(\S+)\s*-->\s*$")
ONLY = re.compile(r"^\s*<!--\s*only:\s*(\w+)\s*-->\s*$")
END = re.compile(r"^\s*<!--\s*end\s*-->\s*$")
VARIABLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def load(path: Path, depth: int = 0) -> list[tuple[str, str]]:
    """The lines of a template with its includes expanded, each with where it came from."""
    name = path.relative_to(ROOT).as_posix()
    if depth > 5:
        sys.exit(f"{name}: includes are nested too deep (does a file include itself?)")
    if not path.is_file():
        sys.exit(f"{name}: file not found")

    lines = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        include = INCLUDE.match(line)
        if include:
            lines.extend(load(SOURCE / include[1], depth + 1))
        else:
            lines.append((f"{name}:{number}", line))
    return lines


def render(template: Path, site: str) -> str:
    variables = COMMON | SITES[site]["vars"]
    kept = []
    block = None  # (site the open block is for, where it opened)

    for where, line in load(template):
        opening = ONLY.match(line)
        if opening:
            if block:
                sys.exit(f"{where}: block opened inside the one from {block[1]}")
            if opening[1] not in SITES:
                sys.exit(f"{where}: unknown site '{opening[1]}' (known: {', '.join(SITES)})")
            block = (opening[1], where)
        elif END.match(line):
            if not block:
                sys.exit(f"{where}: 'end' without an open block")
            block = None
        elif block is None or block[0] == site:
            for name in VARIABLE.findall(line):
                if name not in variables:
                    sys.exit(f"{where}: unknown variable '{name}' for {site}")
            kept.append(VARIABLE.sub(lambda match: variables[match[1]], line))

    if block:
        sys.exit(f"{block[1]}: block is never closed")

    # Dropping a block leaves the blank lines that surrounded it side by side.
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip("\n")
    source = template.relative_to(ROOT).as_posix()
    notice = f"<!-- Generated from {source} by build.py. Edit that file, not this one. -->"
    return f"{notice}\n\n{body}\n"


def main() -> int:
    check = "--check" in sys.argv[1:]
    stale = []

    for site, config in SITES.items():
        for language, suffix in LANGUAGES.items():
            name = (Path(config["directory"]) / f"README{suffix}.md").as_posix()
            output = ROOT / name
            rendered = render(SOURCE / f"profile{suffix}.md", site)
            current = output.read_text(encoding="utf-8") if output.exists() else None
            if rendered == current:
                continue
            stale.append(name)
            if not check:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8", newline="\n")
                print(f"wrote {name} ({site}, {language})")

    if check and stale:
        print(f"out of date: {', '.join(stale)}. Run: python build.py", file=sys.stderr)
        return 1
    if not stale:
        print("up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
