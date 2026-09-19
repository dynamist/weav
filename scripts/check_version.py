#!/usr/bin/env python3
"""Refuse a release whose tag and pyproject.toml disagree about the version.

The tag says which version is being released; pyproject.toml says which version
gets built. They are set by hand, in the same commit by convention and in
different ones by accident, so they can disagree -- and nothing downstream
notices, because every artifact is named after pyproject.toml while the release
is named after the tag.

phabfive tagged v0.10.0-rc.1 over a pyproject.toml that still read 0.10.0-dev.0
and published a release candidate whose wheel, sdist and six executables were
all named for the dev version. That is what this refuses.

It runs before anything is built, so the answer arrives in seconds rather than
after six PyInstaller builds. The smoke tests check the same thing again from
the other end, against the version the built artifact actually reports.

    python3 scripts/check_version.py v0.3.0-rc.1
    python3 scripts/check_version.py v0.3.0-rc.1 path/to/pyproject.toml

Stdlib only, like scripts/smoke.py: it runs on a bare CI runner.
"""

import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smoke import canonical_version

# The release workflow bumps to a .dev version after every release, so a tag
# that names one is a tag pushed before the bump -- caught even when
# pyproject.toml agrees with it, which is the case equality alone lets through.
DEV_MARKERS = ("dev",)


def project_version(pyproject: Path) -> str:
    """The version pyproject.toml declares, and that hatchling will build."""
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)

    try:
        return data["project"]["version"]
    except KeyError:
        sys.exit(f"{pyproject} declares no [project] version")


def main(argv: list[str]) -> int:
    if not 2 <= len(argv) <= 3:
        sys.exit("usage: check_version.py TAG [PYPROJECT]")

    tag = argv[1]
    # The workflow only triggers on "v*", but the leading v is not part of the
    # version and canonical_version() does not drop letters.
    tagged = tag[1:] if tag.startswith("v") else tag

    # The second argument exists so the tests can point it at a fixture; the
    # release always checks the pyproject.toml next to this script.
    default = Path(__file__).resolve().parent.parent / "pyproject.toml"
    pyproject = Path(argv[2]) if len(argv) == 3 else default
    declared = project_version(pyproject)

    print(f"tag            {tag}")
    print(f"pyproject.toml {declared}")

    # Compared with the separators dropped, so the tag spelling v0.3.0-rc.1 and
    # the canonical PEP 440 0.3.0rc1 that hatchling builds are the same release.
    if canonical_version(tagged) != canonical_version(declared):
        print()
        print(f"tag {tag} would release artifacts named {declared}.")
        print("Set the version in pyproject.toml, commit, and move the tag.")
        return 1

    if any(marker in canonical_version(declared) for marker in DEV_MARKERS):
        print()
        print(f"{declared} is a development version and must not be released.")
        print("Bump pyproject.toml to the version being released first.")
        return 1

    print("\nok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
