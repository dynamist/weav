"""YAML frontmatter parsing and editing for Markdown and reST documents."""

from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

# YAML spec: `---` ends the directives section, `...` ends the document.
BOM = "\ufeff"
EOD_MARKER = "---"
EOF_MARKER = "..."


class FrontmatterError(Exception):
    """Raised when a document's YAML frontmatter cannot be parsed."""


class FrontmatterDocument:
    """A text document split into a YAML frontmatter mapping and a body.

    The frontmatter block is recognised only when the document opens with a
    `---` line; the next `---` or `...` line closes it. Anything else is
    treated as body content, so a thematic break in the middle of a Markdown
    file is never mistaken for a delimiter.

    Example:
        >>> doc = FrontmatterDocument("---\\ntitle: Hello\\n---\\nBody\\n")
        >>> doc.frontmatter["title"]
        'Hello'
        >>> doc.content
        'Body\\n'
    """

    eod_marker = EOD_MARKER
    eof_marker = EOF_MARKER

    def __init__(self, text: str = "") -> None:
        """Create a document from `text` and parse it immediately."""
        self._init_yaml()
        self.bom = False
        self.newline = "\n"
        self._raw_block: str | None = None
        self.lines = text.split("\n")
        self.parse()

    def _init_yaml(self) -> None:
        """Configure a round-trip YAML instance preserving comments and quotes."""
        self.yaml = YAML(typ="rt")
        self.yaml.preserve_quotes = True

    @classmethod
    def from_file(cls, path: Path) -> FrontmatterDocument:
        """Read `path` as UTF-8, remembering its BOM and line ending."""
        # newline="" disables universal-newline translation so the original
        # line ending survives a round trip through write().
        with path.open("r", encoding="utf-8", newline="") as handle:
            raw = handle.read()

        doc = cls.__new__(cls)
        doc._init_yaml()
        doc._raw_block = None
        doc.bom = raw.startswith(BOM)
        if doc.bom:
            raw = raw[1:]
        doc.newline = "\r\n" if "\r\n" in raw else "\n"
        doc.lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        doc.parse()
        return doc

    def parse(self) -> None:
        """Split :attr:`lines` into :attr:`frontmatter` and :attr:`content`."""
        lines = self.lines
        # rstrip, not strip: an indented `  ---` is a Markdown thematic
        # break. Matching it here would open a block that the closer scan
        # (also rstrip) could never close, swallowing the body.
        leading = bool(lines) and lines[0].rstrip() == self.eod_marker
        start = 1 if leading else 0

        end = None
        close = self.eod_marker
        for index in range(start, len(lines)):
            # Exact match on the stripped line: `----` is a thematic break,
            # not a delimiter. The raw line is kept so trailing whitespace
            # survives a round trip.
            if lines[index].rstrip() in (self.eod_marker, self.eof_marker):
                end, close = index, lines[index]
                break

        if end is None:
            # No closing delimiter, so there is no frontmatter block at all.
            self._set_content_only()
            return

        # The trailing newline matters: without it ruamel reads a block scalar
        # as `|-` (strip) instead of `|` (clip).
        text = "\n".join(lines[start:end]) + "\n"
        try:
            data: Any = self.yaml.load(text)
        except YAMLError as exc:
            # Only fail when the document declared a frontmatter block. Without
            # a leading marker we are guessing, and guessing must never abort.
            if leading:
                raise FrontmatterError(f"invalid YAML frontmatter: {exc}") from exc
            self._set_content_only()
            return

        if data is None and leading:
            data = CommentedMap()

        if not isinstance(data, dict):
            # Body prose parsed as a scalar or sequence is not frontmatter.
            self._set_content_only()
            return

        self.frontmatter = data
        self.content = "\n".join(lines[end + 1 :])
        self.has_block = True
        # Retained so an unmodified block round trips exactly, including a
        # block that is only comments and therefore has no keys to hang them on.
        self._raw_block = "\n".join(lines[start:end])
        self.open_marker = lines[0] if leading else self.eod_marker
        self.close_marker = close

    def _set_content_only(self) -> None:
        """Treat the whole document as body content with no frontmatter."""
        self.frontmatter = CommentedMap()
        self.content = "\n".join(self.lines)
        self.has_block = False
        self._raw_block = None
        self.open_marker = self.eod_marker
        self.close_marker = self.eod_marker

    def patch(
        self,
        upsert: dict[str, str] | None = None,
        delete: list[str] | None = None,
    ) -> dict[str, list[str]]:
        """Insert or update keys, then delete keys, reporting what changed."""
        result: dict[str, list[str]] = {"inserted": [], "updated": [], "deleted": []}

        if upsert or delete:
            # The block is about to change, so the verbatim copy is stale.
            self._raw_block = None

        if upsert:
            # Sorted so the reported order is stable between runs.
            result["inserted"] = sorted(upsert.keys() - self.frontmatter.keys())
            result["updated"] = sorted(upsert.keys() & self.frontmatter.keys())

            # Update in place rather than rebuilding the map: a fresh
            # CommentedMap copies the items but not ruamel's .ca metadata, so
            # rebuilding would silently drop the block's comments. Existing
            # keys keep their position and new ones append either way.
            self.frontmatter.update(upsert)

        if delete:
            for key in delete:
                if key in self.frontmatter:
                    result["deleted"].append(key)
                    del self.frontmatter[key]
            result["deleted"].sort()

        return result

    def dump_frontmatter(self) -> str:
        """Return the frontmatter block including both delimiters, or ""."""
        if not (self.frontmatter or self.has_block):
            return ""

        if self._raw_block is not None:
            body = f"{self._raw_block}\n" if self._raw_block else ""
            return f"{self.open_marker}\n{body}{self.close_marker}\n"

        buf = io.StringIO()
        if self.frontmatter:
            self.yaml.dump(self.frontmatter, buf)
        return f"{self.open_marker}\n{buf.getvalue()}{self.close_marker}\n"

    def dump_content(self) -> str:
        """Return the document body."""
        return self.content

    def dumps(self) -> str:
        """Return the whole document with LF line endings."""
        return self.dump_frontmatter() + self.dump_content()

    def write(self, path: Path) -> bool:
        """Write the document to `path`, returning whether the bytes changed.

        The original BOM and line ending are restored. The content is written
        to a temporary file in the same directory and moved into place with
        :meth:`Path.replace`, so a reader never sees a partial document and a
        crash mid-write cannot destroy the original.
        """
        text = self.dumps().replace("\n", self.newline)
        payload = (BOM if self.bom else "") + text

        if path.exists() and path.read_bytes() == payload.encode("utf-8"):
            return False

        # delete=False because the file is moved into place, not discarded.
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temp = Path(handle.name)
            handle.write(payload.encode("utf-8"))
        try:
            if path.exists():
                shutil.copymode(path, temp)
            temp.replace(path)
        except OSError:
            temp.unlink(missing_ok=True)
            raise
        return True
