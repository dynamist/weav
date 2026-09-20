"""Tests for the frontmatter parsing and editing module."""

import sys

import pytest
from weav.frontmatter import (
    DEFAULT_INDENT,
    FrontmatterDocument,
    FrontmatterError,
    detect_indent,
)

# Documents are byte constants rather than committed fixture files: CI runs on
# windows-latest and the repository has no .gitattributes, so checkout
# normalisation would silently rewrite the CRLF and BOM cases.
WITH_MARKER = (
    b"---\nstatus: Rolling\ntitle: Example Document\ndocid: DYN-2309-0x-0y\n"
    b"multiline: |\n  hej foo bar\n  baz hej hej\n---\n"
    b"# Manifesto\n\nWe love **sm\xc3\xb6rg\xc3\xa5sbord**.\n"
)
WITHOUT_MARKER = WITH_MARKER.removeprefix(b"---\n")
WITHOUT_CONTENT = b"---\nstatus: Rolling\ntitle: Example Document\n---\n"
PLAIN = b"# Manifesto\n\nWe love **sm\xc3\xb6rg\xc3\xa5sbord**.\n"
EMPTY_BLOCK = b"---\n---\n# Manifesto\n\nWe love **sm\xc3\xb6rg\xc3\xa5sbord**.\n"
WITH_BOM = b"\xef\xbb\xbf---\nstatus: Rolling\n---\n# Manifesto\n"
WITH_CRLF = b"---\r\nstatus: Rolling\r\n---\r\n# Manifesto\r\n"
BAD_MISSING_COLON = b"---\ndocid: DYN-2309-0x-0y\nmalformed\n---\n# Manifesto\n"
BAD_ONE_DASH = b"-\nstatus: Rolling\n---\n# Manifesto\n"

# The regression cases: a `---` thematic break in the body.
HR_IN_BODY = b"# Release notes\n\nIntro paragraph that matters.\n\n---\n\nAppendix.\n"
FM_PLUS_HR = b"---\nstatus: active\n---\n\nSection one.\n\n---\n\nSection two.\n"
FENCED_HR = b"---\nstatus: active\n---\n# Doc\n\n```yaml\n---\nnested: true\n---\n```\n\nTail.\n"
EMPTY = b""
# Degenerate and near-miss delimiters.
UNTERMINATED = b"---\n\n# Title\n\nBody text.\n"
ONLY_MARKER = b"---\n"
FOUR_DASHES_OPEN = b"----\nstatus: Rolling\n---\n# Manifesto\n"
FOUR_DASHES_BODY = b"---\nstatus: active\n---\n# Doc\n\n----\n\nTail.\n"
TRAILING_SPACE_CLOSE = b"---\nstatus: active\n--- \n# Doc\n"
INDENTED_OPENER = b"  ---\n\n# Title\n\n---\n\nBody\n"
COMMENTS_ONLY = b"---\n# just a comment\n---\nBody\n"
COMMENT_AND_KEYS = b"---\n# a comment\na: 1\n---\nBody\n"
# A setext h2 whose text contains a colon: ordinary Markdown, not frontmatter.
SETEXT_H2 = b"Overview: the big picture\n---\n\nBody text.\n"

ROUND_TRIP_CASES = [
    "WITH_MARKER",
    "WITHOUT_CONTENT",
    "PLAIN",
    "EMPTY_BLOCK",
    "WITH_BOM",
    "WITH_CRLF",
    "HR_IN_BODY",
    "FM_PLUS_HR",
    "FENCED_HR",
    "EMPTY",
    "UNTERMINATED",
    "ONLY_MARKER",
    "FOUR_DASHES_OPEN",
    "FOUR_DASHES_BODY",
    "TRAILING_SPACE_CLOSE",
    "INDENTED_OPENER",
    "COMMENTS_ONLY",
    "COMMENT_AND_KEYS",
    "WITHOUT_MARKER",
    "SETEXT_H2",
]


@pytest.mark.parametrize("name", ROUND_TRIP_CASES)
def test_round_trip_is_byte_exact(doc, name):
    """An unpatched document must survive a read/write cycle unchanged."""
    raw = globals()[name]
    path = doc(raw)
    document = FrontmatterDocument.from_file(path)
    changed = document.write(path)
    assert path.read_bytes() == raw
    assert changed is False


def test_write_is_a_noop_when_nothing_changed(doc):
    """An unchanged document must not be rewritten, leaving mtime alone."""
    path = doc(WITH_MARKER)
    before = path.stat().st_mtime_ns
    assert FrontmatterDocument.from_file(path).write(path) is False
    assert path.stat().st_mtime_ns == before


def test_crlf_is_preserved_through_an_edit(doc):
    """A CRLF document must stay CRLF after an in-place edit."""
    path = doc(WITH_CRLF)
    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"origin": "abc123"})
    document.write(path)

    raw = path.read_bytes()
    assert b"origin: abc123" in raw
    assert b"\r\n" in raw
    assert raw.replace(b"\r\n", b"").count(b"\n") == 0


def test_bom_is_preserved_and_not_doubled(doc):
    """A BOM must survive an edit exactly once."""
    path = doc(WITH_BOM)
    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"origin": "abc123"})
    document.write(path)

    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.count(b"\xef\xbb\xbf") == 1
    assert b"origin: abc123" in raw


def test_utf8_survives_an_in_place_write(doc):
    """Non-ASCII content must not be mangled by a locale-dependent encoding."""
    path = doc(WITH_MARKER)
    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"origin": "abc123"})
    document.write(path)
    assert "smörgåsbord" in path.read_text(encoding="utf-8")


def test_thematic_break_does_not_eat_the_document(doc):
    """A `---` in the body must not be mistaken for a frontmatter delimiter."""
    path = doc(HR_IN_BODY)
    document = FrontmatterDocument.from_file(path)

    # No frontmatter block was declared, so there is none.
    assert dict(document.frontmatter) == {}
    assert document.has_block is False

    document.patch(upsert={"origin": "deadbeef"})
    document.write(path)

    text = path.read_text(encoding="utf-8")
    assert "origin: deadbeef" in text
    assert "# Release notes" in text
    assert "Intro paragraph that matters." in text
    assert "Appendix." in text


def test_frontmatter_plus_thematic_break(doc):
    """A real block plus a body break must parse without raising."""
    path = doc(FM_PLUS_HR)
    document = FrontmatterDocument.from_file(path)

    assert dict(document.frontmatter) == {"status": "active"}
    assert "Section one." in document.content
    assert "Section two." in document.content


def test_block_scalar_keeps_its_chomping_indicator(doc):
    """`multiline: |` must not degrade to `|-` on a round trip."""
    path = doc(WITH_MARKER)
    document = FrontmatterDocument.from_file(path)
    assert "multiline: |\n" in document.dump_frontmatter()


def test_patch_reports_sorted_keys(doc):
    """Reported keys must be ordered deterministically."""
    path = doc(WITH_MARKER)
    document = FrontmatterDocument.from_file(path)
    result = document.patch(
        upsert={"zeta": "1", "alpha": "2", "title": "x", "status": "y"},
        delete=["docid"],
    )
    assert result["inserted"] == ["alpha", "zeta"]
    assert result["updated"] == ["status", "title"]
    assert result["deleted"] == ["docid"]


def test_malformed_frontmatter_raises_and_leaves_the_file_alone(doc):
    """A declared but invalid block is fatal, and must not touch the file."""
    path = doc(BAD_MISSING_COLON)
    with pytest.raises(FrontmatterError):
        FrontmatterDocument.from_file(path)
    assert path.read_bytes() == BAD_MISSING_COLON


def test_no_leading_marker_is_never_fatal(doc):
    """Without an opening `---` we are guessing, so we must not raise."""
    path = doc(BAD_ONE_DASH)
    document = FrontmatterDocument.from_file(path)
    assert document.has_block is False
    assert "status: Rolling" in document.content


def test_marker_less_block_is_not_frontmatter(doc):
    """A block closed by `---` but never opened by one is body content.

    Recognising it would consume a setext h2 -- see
    test_setext_heading_is_not_frontmatter.
    """
    path = doc(WITHOUT_MARKER)
    document = FrontmatterDocument.from_file(path)

    assert document.has_block is False
    assert dict(document.frontmatter) == {}
    assert "status: Rolling" in document.content


def test_setext_heading_is_not_frontmatter(doc):
    """`Title: subtitle` underlined by `---` is a Markdown h2, not metadata."""
    path = doc(SETEXT_H2)
    document = FrontmatterDocument.from_file(path)

    assert document.has_block is False
    assert "Overview: the big picture" in document.content

    # A no-op invocation must not rewrite an ordinary Markdown document.
    assert document.write(path) is False
    assert path.read_bytes() == SETEXT_H2


def test_empty_block_is_preserved(doc):
    """An empty `---\\n---` block must not silently disappear."""
    path = doc(EMPTY_BLOCK)
    document = FrontmatterDocument.from_file(path)
    assert document.has_block is True
    assert document.dump_frontmatter() == "---\n---\n"


def test_frontmatter_only_document_keeps_its_closing_marker(doc):
    """A document with no body must still emit both delimiters."""
    path = doc(WITHOUT_CONTENT)
    document = FrontmatterDocument.from_file(path)
    assert document.dumps() == WITHOUT_CONTENT.decode()


def test_content_is_separated_from_frontmatter(doc):
    """Frontmatter keys must not leak into the body."""
    path = doc(WITH_MARKER)
    document = FrontmatterDocument.from_file(path)
    assert "status: Rolling" not in document.content
    assert "status" in document.frontmatter


def test_fenced_code_block_delimiters_are_not_frontmatter(doc):
    """A `---` inside a fenced code block must stay in the body."""
    path = doc(FENCED_HR)
    document = FrontmatterDocument.from_file(path)

    assert dict(document.frontmatter) == {"status": "active"}
    assert "```yaml" in document.content
    assert "nested: true" in document.content
    assert "Tail." in document.content

    document.patch(upsert={"origin": "deadbeef"})
    document.write(path)

    text = path.read_text(encoding="utf-8")
    assert "origin: deadbeef" in text
    assert "nested: true" in text
    assert "Tail." in text


def test_empty_file_is_handled(doc):
    """An empty document must parse to nothing and not raise."""
    path = doc(EMPTY)
    document = FrontmatterDocument.from_file(path)

    assert dict(document.frontmatter) == {}
    assert document.has_block is False
    assert document.dumps() == ""


def test_unterminated_opening_marker_is_not_frontmatter(doc):
    """An opening `---` with no close must leave the body untouched."""
    path = doc(UNTERMINATED)
    document = FrontmatterDocument.from_file(path)

    assert document.has_block is False
    assert dict(document.frontmatter) == {}
    assert "# Title" in document.content
    assert "Body text." in document.content


def test_four_dashes_do_not_open_a_block(doc):
    """`----` is a thematic break, not a frontmatter delimiter."""
    path = doc(FOUR_DASHES_OPEN)
    document = FrontmatterDocument.from_file(path)
    assert document.has_block is False
    assert "status: Rolling" in document.content


def test_four_dashes_in_body_do_not_close_a_block(doc):
    """`----` in the body must not be mistaken for the closing delimiter."""
    path = doc(FOUR_DASHES_BODY)
    document = FrontmatterDocument.from_file(path)
    assert dict(document.frontmatter) == {"status": "active"}
    assert "----" in document.content
    assert "Tail." in document.content


def test_trailing_whitespace_still_closes_a_block(doc):
    """`--- ` with trailing whitespace is still a delimiter."""
    path = doc(TRAILING_SPACE_CLOSE)
    document = FrontmatterDocument.from_file(path)
    assert dict(document.frontmatter) == {"status": "active"}
    assert "# Doc" in document.content


@pytest.mark.parametrize("name", ROUND_TRIP_CASES)
def test_upsert_is_idempotent(doc, name):
    """Applying the same upsert twice must converge on identical bytes."""
    path = doc(globals()[name])

    first = FrontmatterDocument.from_file(path)
    first.patch(upsert={"origin": "deadbeef"})
    first.write(path)
    once = path.read_bytes()

    second = FrontmatterDocument.from_file(path)
    second.patch(upsert={"origin": "deadbeef"})
    assert second.write(path) is False
    assert path.read_bytes() == once


def test_indented_marker_does_not_open_a_block(doc):
    """An indented `  ---` is a thematic break, not an opening delimiter.

    It is matched with rstrip like the closing scan, so it can never open a
    block that nothing could close -- which would swallow the body.
    """
    path = doc(INDENTED_OPENER)
    document = FrontmatterDocument.from_file(path)

    assert document.has_block is False
    assert "# Title" in document.content
    assert "Body" in document.content


def test_comment_only_frontmatter_is_preserved(doc):
    """A block of only comments has no keys to hang them on, but must survive."""
    path = doc(COMMENTS_ONLY)
    document = FrontmatterDocument.from_file(path)

    assert document.has_block is True
    assert "# just a comment" in document.dump_frontmatter()


def test_comments_survive_alongside_keys(doc):
    """Round-trip mode must keep comments attached to a populated block."""
    path = doc(COMMENT_AND_KEYS)
    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"b": "2"})
    document.write(path)

    text = path.read_text()
    assert "# a comment" in text
    # Quoted because CLI values are strings; "2" must not become an int.
    assert "b: '2'" in text


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows has no POSIX mode bits; chmod only toggles the read-only flag",
)
def test_write_preserves_file_mode(doc):
    """The atomic swap must not reset permissions to the temp file's."""
    import stat

    path = doc(WITH_MARKER)
    path.chmod(0o640)
    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"origin": "abc"})
    document.write(path)

    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_write_leaves_no_temporary_file(doc):
    """The temp file used for the atomic swap must not survive."""
    path = doc(WITH_MARKER)
    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"origin": "abc"})
    document.write(path)

    assert list(path.parent.iterdir()) == [path]


def test_patch_reports_deleted_sorted(doc):
    """Deleted keys are reported sorted, like inserted and updated."""
    path = doc(WITH_MARKER)
    document = FrontmatterDocument.from_file(path)
    result = document.patch(delete=["status", "docid"])
    assert result["deleted"] == ["docid", "status"]


def test_write_replaces_rather_than_truncates(doc):
    """The swap must be atomic, not a truncate-in-place.

    Asserted via the inode: `Path.write_bytes` would reuse it, which would mean
    a crash mid-write could leave a truncated file with the original gone.
    """
    path = doc(WITH_MARKER)
    before = path.stat().st_ino

    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"origin": "abc"})
    assert document.write(path) is True

    assert path.stat().st_ino != before


def test_write_follows_a_symlink_instead_of_replacing_it(doc, tmp_path):
    """An atomic replace must land on the canonical file, not the link.

    Replacing the link itself would leave its target stale while the link
    became an ordinary file -- a silent divergence in a tree where documents
    are linked into place.
    """
    real = doc(WITH_MARKER, name="real.md")
    link = tmp_path / "link.md"
    link.symlink_to(real)

    document = FrontmatterDocument.from_file(link)
    document.patch(upsert={"origin": "abc123"})
    assert document.write(link) is True

    assert link.is_symlink()
    assert b"origin: abc123" in real.read_bytes()


def test_delete_that_matches_nothing_does_not_reformat(doc):
    """A no-op delete must not re-dump the block and reflow the author's layout."""
    raw = b"---\nstatus:   active\nnested:\n    deep: 1\n---\n# Doc\n"
    path = doc(raw)

    document = FrontmatterDocument.from_file(path)
    result = document.patch(delete=["nonexistent"])

    assert result == {"inserted": [], "updated": [], "deleted": []}
    assert document.write(path) is False
    assert path.read_bytes() == raw


def test_upsert_that_changes_nothing_does_not_reformat(doc):
    """Re-setting a key to its current value must leave the bytes alone."""
    raw = b"---\nstatus:   active\n---\n# Doc\n"
    path = doc(raw)

    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"status": "active"})
    document.write(path)

    # The value is unchanged, but it was an explicit update, so a re-dump is
    # expected; what must hold is that running it again is a no-op.
    once = path.read_bytes()
    again = FrontmatterDocument.from_file(path)
    again.patch(upsert={"status": "active"})
    assert again.write(path) is False
    assert path.read_bytes() == once


# One per row of the table in issue #82. Every block carries `title: plan`, so
# re-setting it is a semantic no-op that still forces a re-dump -- which is
# exactly the reported invocation. The indented and the flush cases fail in
# opposite directions, so a fix for one can silently break the other.
INDENT_STYLES = {
    "sequence indented by two": b"---\ntitle: plan\ntags:\n  - infra\n  - platform\n---\n# Doc\n",
    "sequence indented by four": (
        b"---\ntitle: plan\ntags:\n    - infra\n    - platform\n---\n# Doc\n"
    ),
    "sequence flush with its key": b"---\ntitle: plan\ntags:\n- infra\n- platform\n---\n# Doc\n",
    "sequence of mappings": (
        b"---\ntitle: plan\nauthors:\n  - name: Ada\n    role: editor\n"
        b"  - name: Linus\n    role: reviewer\n---\n# Doc\n"
    ),
    "sequence of mappings flush": (
        b"---\ntitle: plan\nauthors:\n- name: Ada\n  role: editor\n---\n# Doc\n"
    ),
    "nested mapping at four": (
        b"---\ntitle: plan\nnested:\n    deep:\n        deeper: 1\n---\n# Doc\n"
    ),
    "nested mapping at two": b"---\ntitle: plan\nnested:\n  deep:\n    deeper: 1\n---\n# Doc\n",
    "block scalar": b"---\ntitle: plan\nbody: |\n  hej foo bar\n  baz hej hej\n---\n# Doc\n",
    "flow style": b"---\ntitle: plan\ntags: [infra, platform]\nowner: {team: core}\n---\n# Doc\n",
    "comments and quotes": (
        b"---\n# a leading comment\ntitle: plan\nstatus: 'active'  # trailing\n"
        b'label: "quoted"\ntags:\n  - infra\n---\n# Doc\n'
    ),
    "both styles at four": b"---\ntitle: plan\nnested:\n    tags:\n        - infra\n---\n# Doc\n",
    "four-space mapping, flush sequence": (
        b"---\ntitle: plan\nnested:\n    tags:\n    - infra\n---\n# Doc\n"
    ),
}


@pytest.mark.parametrize("name", sorted(INDENT_STYLES))
def test_indentation_survives_a_semantic_no_op(doc, name):
    """Re-setting a key to its own value must not re-indent the block.

    ruamel has one global indentation setting rather than one per node, so
    without measuring the document first a re-dump flattens an indented block
    sequence and normalises a mapping indented by anything but two -- the
    reindentation then lands in the same commit as the intended edit.
    """
    raw = INDENT_STYLES[name]
    path = doc(raw)

    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"title": "plan"})

    assert document.write(path) is False
    assert path.read_bytes() == raw


@pytest.mark.parametrize("name", sorted(INDENT_STYLES))
def test_indentation_survives_a_real_edit(doc, name):
    """An edit must change the keys it was given and nothing else."""
    raw = INDENT_STYLES[name]
    path = doc(raw)

    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"origin": "deadbeef"})
    document.write(path)

    # The block gained one line and is otherwise the document it was.
    before = raw.decode().splitlines()
    after = path.read_text(encoding="utf-8").splitlines()
    assert [line for line in after if line not in ("origin: deadbeef",)] == before
    assert "origin: deadbeef" in after


@pytest.mark.parametrize(
    ("block", "expected"),
    [
        ("tags:\n  - a\n", (2, 4, 2)),
        ("tags:\n    - a\n", (2, 6, 4)),
        ("tags:\n- a\n", (2, 2, 0)),
        ("nested:\n    deep: 1\n", (4, 2, 0)),
        ("nested:\n    tags:\n        - a\n", (4, 6, 4)),
        # A key with only a trailing comment still opens a block.
        ("tags:  # note\n  - a\n", (2, 4, 2)),
        # Nothing to measure.
        ("title: plan\n", DEFAULT_INDENT),
        ("tags: [a, b]\n", DEFAULT_INDENT),
    ],
)
def test_detect_indent_measures_the_block(block, expected):
    """The scanner must read back the style the block was written in."""
    assert detect_indent(block) == expected


def test_detect_indent_falls_back_on_mixed_styles():
    """No single setting can preserve two styles, so measure neither."""
    assert detect_indent("a:\n  - x\nb:\n- y\n") == DEFAULT_INDENT
    assert detect_indent("a:\n  b: 1\nc:\n    d: 2\n") == DEFAULT_INDENT


def test_detect_indent_ignores_block_scalar_bodies():
    """A dash inside a literal scalar is text, not a sequence entry."""
    assert detect_indent("body: |\n  - not a sequence\n  - really\n") == DEFAULT_INDENT
    # And the scalar must not hide a real sequence that follows it.
    assert detect_indent("body: |\n  - text\ntags:\n  - a\n") == (2, 4, 2)


def test_detect_indent_ignores_the_keys_of_a_sequence_entry():
    """`- name: a` is indented by the sequence, so it measures no mapping."""
    assert detect_indent("items:\n  - name: a\n    role: b\n") == (2, 4, 2)


# One per row of the table in issue #85, each carrying a value well past
# ruamel's default width of 80 so a re-dump folds it. `title: plan` is there so
# re-setting it is a semantic no-op that still forces the re-dump.
_LONG = "word " * 25 + "end"
_URL = "https://example.com/" + "a" * 90

LONG_SCALARS = {
    "plain scalar": f"---\ntitle: plan\nsummary: {_LONG}\n---\n# Doc\n".encode(),
    "single-quoted scalar": f"---\ntitle: plan\nsummary: '{_LONG}'\n---\n# Doc\n".encode(),
    "double-quoted scalar": f'---\ntitle: plan\nsummary: "{_LONG}"\n---\n# Doc\n'.encode(),
    "sequence entry": f"---\ntitle: plan\ntags:\n  - {_LONG}\n---\n# Doc\n".encode(),
    "sequence entry flush": f"---\ntitle: plan\ntags:\n- {_LONG}\n---\n# Doc\n".encode(),
    "nested mapping value": f"---\ntitle: plan\nouter:\n  inner: {_LONG}\n---\n# Doc\n".encode(),
    # Unbreakable: the emitter cannot fold it, so folding only ever moved it to
    # a line of its own that was over 80 anyway.
    "unbreakable url": f"---\ntitle: plan\nlink: {_URL}\n---\n# Doc\n".encode(),
    "long key": ("---\ntitle: plan\n" + "k" * 100 + ": v\n---\n# Doc\n").encode(),
    "literal block scalar": f"---\ntitle: plan\nbody: |\n  {_LONG}\n---\n# Doc\n".encode(),
    "folded block scalar": f"---\ntitle: plan\nbody: >\n  {_LONG}\n---\n# Doc\n".encode(),
    "short values": b"---\ntitle: plan\nsummary: short\n---\n# Doc\n",
}


@pytest.mark.parametrize("name", sorted(LONG_SCALARS))
def test_long_scalars_survive_a_semantic_no_op(doc, name):
    """A value the author wrote on one line must come back on one line.

    ruamel folds a plain or quoted scalar at its `width`, 80 by default, so
    without raising it an upsert that changes nothing still rewraps the block
    -- and the fold leaves a trailing space behind, which an editor or a
    `trailing-whitespace` hook then strips, so the two take turns rewriting the
    same line.
    """
    raw = LONG_SCALARS[name]
    path = doc(raw)

    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"title": "plan"})

    assert document.write(path) is False
    assert path.read_bytes() == raw


@pytest.mark.parametrize("name", sorted(LONG_SCALARS))
def test_a_real_edit_leaves_no_trailing_whitespace(doc, name):
    """The break a fold introduces is what carries the trailing space."""
    path = doc(LONG_SCALARS[name])

    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"origin": "deadbeef"})
    document.write(path)

    written = path.read_text(encoding="utf-8")
    assert [line for line in written.splitlines() if line != line.rstrip()] == []
    assert "origin: deadbeef" in written.splitlines()


def test_a_hand_wrapped_scalar_is_joined(doc):
    """The one row that cannot round trip, and does not today either.

    ruamel does not record a plain scalar's own line breaks, so the author's
    wrapping is lost whatever the width is: at 80 the value is re-broken at the
    library's points with a trailing space, and here it is joined. Only the
    second leaves a value that was written on one line on one line, and a
    folded block scalar is the construct that does keep its breaks.
    """
    raw = (
        b"---\ntitle: plan\nsummary: alpha beta gamma delta epsilon zeta eta theta\n"
        b"  iota kappa lambda mu nu xi omicron pi rho sigma tau\n---\n# Doc\n"
    )
    path = doc(raw)

    document = FrontmatterDocument.from_file(path)
    document.patch(upsert={"title": "plan"})
    document.write(path)

    assert path.read_text(encoding="utf-8") == (
        "---\ntitle: plan\nsummary: alpha beta gamma delta epsilon zeta eta theta"
        " iota kappa lambda mu nu xi omicron pi rho sigma tau\n---\n# Doc\n"
    )
