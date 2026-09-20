"""YAML frontmatter parsing and editing for Markdown and reST documents."""

from __future__ import annotations

import io
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

# This module's full public surface. The package's own __all__ in
# weav/__init__.py is the narrower, curated promise; anything listed here
# but not there is public but reached one import deeper.
__all__ = [
    "BOM",
    "DEFAULT_INDENT",
    "EOD_MARKER",
    "EOF_MARKER",
    "UNLIMITED_WIDTH",
    "FrontmatterDocument",
    "FrontmatterError",
    "detect_indent",
]

# YAML spec: `---` ends the directives section, `...` ends the document.
BOM = "\ufeff"
EOD_MARKER = "---"
EOF_MARKER = "..."

# ruamel carries one global indentation setting rather than recording one per
# node, so a block whose style is not measured is re-emitted with these: a
# nested mapping two columns in, and a block sequence whose dash sits in its
# parent key's own column.
DEFAULT_INDENT = (2, 2, 0)

# ruamel folds a plain or quoted scalar at its `width` -- 80 by default -- and
# leaves a trailing space on the line it breaks. No document has a width the
# way it has an indentation style, so there is nothing to measure: a value the
# author wrote on one line is emitted on one line, whatever its length. The
# number is a ceiling no real line reaches rather than a limit meant to apply;
# ruamel only compares against it, so an unreachable one disables the fold.
UNLIMITED_WIDTH = 2**20

# A block sequence entry. Whatever follows the dash starts a column of its
# own, which is why the content column is taken from the match span.
_ENTRY = re.compile(r"^(?P<indent> *)-(?: +(?P<rest>.*?))?\s*$")
# A mapping key, quoted or plain, with the value it carries. YAML requires a
# space after the colon, so `key:value` is a plain scalar and must not match.
_KEY = re.compile(r"""^(?:"[^"]*"|'[^']*'|[^\s#][^:]*?):(?: +(?P<value>\S.*?))?\s*$""")
_BLANK_OR_COMMENT = re.compile(r"^\s*(?:#.*)?$")
# `|` and `>`, with their chomping and explicit indentation indicators.
_BLOCK_SCALAR = re.compile(r"^[|>][\d+-]{0,2}$")


def detect_indent(block: str) -> tuple[int, int, int]:
    """Measure `block`'s own indentation as ruamel emitter settings.

    Returns `(mapping, sequence, offset)`. The two styles are measured
    independently, and each only from an unambiguous case: a line whose
    immediately preceding structural line is a key that opened a block.
    Nothing else can be trusted to be structure at all -- a plain scalar's
    continuation lines, a flow collection split over several lines and the
    second key of a sequence entry all follow a key that already had a value,
    so none of them are measured. A block scalar's body is skipped outright.

    A style the block does not exercise, or exercises inconsistently, falls
    back to :data:`DEFAULT_INDENT`. Matching one of two mixed styles would
    reflow the other, so an inconsistent block is left to the emitter.
    """
    mappings: set[int] = set()
    offsets: set[int] = set()
    # The previous structural line: its column, and whether it opened a block.
    previous: tuple[int, bool] = (0, False)
    scalar: int | None = None

    for line in block.split("\n"):
        if scalar is not None:
            # A block scalar runs until a line indented no further than its key.
            if not line.strip() or _column(line) > scalar:
                continue
            scalar = None
        if _BLANK_OR_COMMENT.match(line):
            continue

        column, opens = previous
        entry = _ENTRY.match(line)
        if entry is not None:
            dash = len(entry["indent"])
            # The offset is the dash's column within its parent key's block,
            # so a sequence flush with its key measures 0 -- hence `<=`.
            if opens and column <= dash:
                offsets.add(dash - column)
            text = entry["rest"] or ""
            here = entry.start("rest") if text else dash
        else:
            text = line.lstrip(" ")
            here = _column(line)

        key = _KEY.match(text)
        if key is None:
            previous = (here, False)
            continue
        # A key on the dash's own line is indented by the sequence, not by the
        # mapping, so `- name: a` measures nothing.
        if entry is None and opens and column < here:
            mappings.add(here - column)
        value = key["value"]
        # A trailing comment is not a value: `key:  # note` still opens a block.
        if value is None or value.startswith("#"):
            previous = (here, True)
        else:
            previous = (here, False)
            if _BLOCK_SCALAR.match(value):
                scalar = here

    mapping, sequence, offset = DEFAULT_INDENT
    if len(mappings) == 1:
        mapping = mappings.pop()
    if len(offsets) == 1:
        offset = offsets.pop()
        # ruamel places the dash at `offset` and the entry's content at
        # `sequence`; the dash and the space after it are the two between them.
        sequence = offset + 2
    return mapping, sequence, offset


def _column(line: str) -> int:
    """Return the column at which `line`'s content starts."""
    return len(line) - len(line.lstrip(" "))


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
        self._raw_block: str | None = None
        self._adopt(text)
        self.parse()

    def _adopt(self, text: str) -> None:
        """Take `text` as this document's source, normalising it to LF.

        The one decoding path, shared with from_file(), because the two
        disagreeing is a corruption bug rather than an inconsistency: text
        whose BOM was left in place does not match a leading `---`, so the
        document parses as having no frontmatter at all, and the next patch()
        prepends a second block while the real one stays behind in the body.

        A byte order mark belongs to the encoding rather than the document, so
        it is recorded and stripped; line endings are folded so the parser and
        the emitter only ever see "\n". write() restores both.
        """
        self.bom = text.startswith(BOM)
        if self.bom:
            text = text[1:]
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    def _init_yaml(self) -> None:
        """Configure a round-trip YAML instance preserving comments and quotes.

        The emitter is given an unreachable line width so a long scalar is
        never re-wrapped. Folding one is not a round trip in either direction:
        it adds a trailing space at the break, and ruamel does not record a
        plain scalar's own line breaks, so a hand-wrapped value is re-broken at
        the library's points rather than the author's whatever the width is.
        """
        self.yaml = YAML(typ="rt")
        self.yaml.preserve_quotes = True
        self.yaml.width = UNLIMITED_WIDTH
        self._set_indent(DEFAULT_INDENT)

    def _set_indent(self, indent: tuple[int, int, int]) -> None:
        """Point the emitter at an indentation style."""
        mapping, sequence, offset = indent
        self.yaml.indent(mapping=mapping, sequence=sequence, offset=offset)

    @classmethod
    def from_file(cls, path: Path) -> FrontmatterDocument:
        """Read `path` as UTF-8, remembering its BOM and line ending."""
        # newline="" disables universal-newline translation so the original
        # line ending survives a round trip through write().
        with path.open("r", encoding="utf-8", newline="") as handle:
            raw = handle.read()

        # Just the constructor: reading a file is only a way of obtaining the
        # text, and everything after that is the same document.
        return cls(raw)

    def parse(self) -> None:
        """Split :attr:`lines` into :attr:`frontmatter` and :attr:`content`."""
        lines = self.lines
        # rstrip, not strip: an indented `  ---` is a Markdown thematic
        # break. Matching it here would open a block that the closer scan
        # (also rstrip) could never close, swallowing the body.
        leading = bool(lines) and lines[0].rstrip() == self.eod_marker
        if not leading:
            # Without an opening delimiter there is no frontmatter. Guessing
            # would consume a setext h2 -- "Title: subtitle" underlined by
            # `---` is ordinary Markdown -- and silently promote a heading
            # into metadata.
            self._set_content_only()
            return

        start = 1

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
            raise FrontmatterError(f"invalid YAML frontmatter: {exc}") from exc

        if data is None:
            data = CommentedMap()

        if not isinstance(data, dict):
            # Body prose parsed as a scalar or sequence is not frontmatter.
            self._set_content_only()
            return

        # Indentation is not round-tripped per node, so a re-dump would
        # otherwise flatten an indented block sequence and normalise a mapping
        # indented by anything but two -- a diff the caller never asked for on
        # a file that is edited in place by default.
        self._set_indent(detect_indent(text))

        self.frontmatter = data
        self.content = "\n".join(lines[end + 1 :])
        self.has_block = True
        # Retained so an unmodified block round trips exactly, including a
        # block that is only comments and therefore has no keys to hang them on.
        self._raw_block = "\n".join(lines[start:end])
        self.open_marker = lines[0]
        self.close_marker = close

    def _set_content_only(self) -> None:
        """Treat the whole document as body content with no frontmatter."""
        # There is no block to take a style from, and parse() is re-runnable:
        # a style measured on an earlier pass must not outlive its block.
        self._set_indent(DEFAULT_INDENT)
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

        if any(result.values()):
            # Only now is the verbatim copy stale. Clearing it earlier would
            # re-dump the block for a delete that matched nothing, reflowing
            # the author's spacing and indentation for no reason.
            self._raw_block = None

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
        to a temporary file beside the target and moved into place with
        :meth:`Path.replace`, so a reader never sees a partial document and a
        crash mid-write cannot destroy the original.

        A symlink is followed rather than replaced, so the canonical file is
        the one updated. Only the mode is carried over -- ownership, ACLs and
        extended attributes are not -- and a hardlinked file's link count is
        broken, which is inherent to replacing rather than truncating.
        """
        text = self.dumps().replace("\n", self.newline)
        payload = ((BOM if self.bom else "") + text).encode("utf-8")

        # Resolve first: replacing `path` itself would swap out a symlink and
        # leave its target stale. The temp file has to live in the resolved
        # parent too, or the rename could cross a filesystem and fail.
        target = path.resolve()

        if target.exists() and target.read_bytes() == payload:
            return False

        # delete=False because the file is moved into place, not discarded.
        with tempfile.NamedTemporaryFile(
            dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False
        ) as handle:
            temp = Path(handle.name)
            handle.write(payload)
        try:
            if target.exists():
                shutil.copymode(target, temp)
            temp.replace(target)
        except OSError:
            temp.unlink(missing_ok=True)
            raise
        return True
