---
name: weav
description: "Render Jinja2 templates with data from YAML, JSON and TOML files, stdin, environment variables and command output, and edit the YAML frontmatter of Markdown or reST documents, through the weav CLI. Use when the user names weav, asks to compile or render a template from data files, or asks to read or change a document's frontmatter keys. Do not use for other template engines such as Mustache, ERB or Go templates. Needs no configuration."
---

# weav

weav is a Jinja2 template compiler with two commands. `weav render` turns a
template plus one or more data sources into text on stdout. `weav frontmatter`
adds, changes and removes keys in a document's YAML frontmatter.

There is nothing to configure: no config file, no environment variables of its
own, no server. If `weav --version` prints a version, it is ready.

```bash
weav --version
```

## Learn the installed CLI

The installed binary is the authority for command syntax. weav is pre-1.0 and
its options move, so read the help rather than trusting this file's option list:

```bash
weav --help
weav render --help
weav frontmatter --help
```

A bare `weav` with no arguments prints help to **stderr and exits 2**. That is
how it asks for a command, not a failure.

Nothing in weav is interactive and nothing prompts, so every command below is
safe to run non-interactively -- with one exception: `weav frontmatter` writes
to the file you name. See "It edits in place".

## Render a template

```bash
weav render template.j2 --keyval name=World
weav render report.j2 --data config.yaml
weav render report.j2 --data items=tasks.yaml --data config.json
```

The rendered document goes to stdout. Diagnostics, `--verbose` reports and
errors go to stderr, so capturing stdout alone is safe.

### Where templates are found

A TEMPLATE containing `/` or `\`, or one that is absolute, is used as a file
path. Anything else is a bare name, looked up in these directories in order:

1. the package's own bundled templates
2. `./templates` under the current working directory
3. `~/.local/share/weav/templates`
4. `~/Documents/weav/templates`

The bundled directory does not exist in current releases, so in practice a bare
name resolves against `./templates` and the two user directories. When a bare
name is not found, weav lists every directory it searched and every template it
did find, which is the fastest way to see what is installed.

Pass a path when you mean a specific file. `weav render report.j2` and
`weav render ./report.j2` are **not** the same lookup.

## Data sources

Every data option takes a spec with the grammar `[KEY][:FORMAT]=SOURCE`:

```bash
weav render report.j2 --data config.yaml            # SOURCE only
weav render report.j2 --data items=tasks.yaml       # wrap under "items"
weav render report.j2 --data items:json=tasks.out   # ... and force a parser
weav render report.j2 --data :json=-                # force a parser on stdin
```

A `KEY=` prefix is only recognised when KEY looks like a name: it may not
contain whitespace, `/`, `\`, `:`, `=` or `.`. That is deliberate, and it is why
a path or a command containing `=` is left alone:

```bash
weav render report.j2 --data ./my=dir/config.yaml
weav render report.j2 --exec 'phabfive --format=yaml maniphest search'
```

Neither is read as a KEY prefix; the first is a path, the second a command.

### The suffix almost never picks the parser

Only `.json` and `.toml` infer a format. **Everything else is parsed as YAML**,
including `.txt`, `.ini`, `.cfg`, `.env` and extensionless paths. YAML is a
superset of JSON, so a `.json` file happens to work either way, but a file that
is not YAML and is not named `.json` or `.toml` will fail or, worse, parse into
something unintended. Name the parser when the suffix does not:

```bash
weav render report.j2 --data settings:toml=pyproject.cfg
```

FORMAT is one of `yaml`, `json`, `toml`. Anything else is an error naming the
three valid ones.

### Wrapping

Without a KEY, a mapping is merged at the top level and its keys become template
variables directly. A list or a scalar cannot be, so it is wrapped under `data`:

```bash
echo '[1, 2, 3]' > list.yaml
weav render template.j2 --data list.yaml     # {{ data }} is [1, 2, 3]
weav render template.j2 --data nums=list.yaml  # {{ nums }} is [1, 2, 3]
```

With a KEY, the source is always wrapped under it, whatever its shape.

## How sources are merged

Sources are loaded in a fixed order and deep-merged, last wins:

1. `--data` / `-d`, in command-line order
2. `--exec` / `-x`, in command-line order
3. `--env` / `-e`
4. `--keyval` / `-k`

So `--keyval` always beats a data file, no matter where it appears on the line.
Ordering `-k` before `-d` does not change that.

The merge is recursive for mappings but **lists are replaced, not
concatenated**. Merging `items: [a, b]` with `items: [c]` yields `[c]`, not
`[a, b, c]`. Build the whole list in one source.

Use `--verbose` to see which sources were loaded and which top-level keys each
one contributed; the report goes to stderr:

```bash
weav render report.j2 --data base.yaml --data override.yaml --verbose
```

## --keyval values are always strings

`--keyval` never parses. `count=0` becomes the string `"0"`, which is **truthy**
in `{% if count %}`, and `flag=false` becomes the string `"false"`, also truthy.
The same key loaded from a data file is a real integer or boolean.

Use `--keyval` for text. For anything a template will test or do arithmetic on,
use a data file, or convert in the template with `| int` or `| float`
(Jinja has no `bool` filter; compare against the string instead).

`--keyval` never splits on commas, so a comma is just part of the value:

```bash
weav render report.j2 --keyval 'tags=a,b,c'   # one key, value "a,b,c"
weav render report.j2 --keyval a=1 --keyval b=2   # two keys
```

Note the asymmetry with `weav frontmatter --upsert`, which does split. Repeat
`--keyval` rather than relying on either behaviour.

## Environment variables

`--env PREFIX` loads every variable starting with PREFIX. The prefix is stripped
and the remaining name is lowercased, so `MYAPP_NAME` becomes `{{ name }}`:

```bash
MYAPP_NAME=World weav render template.j2 --env MYAPP_
```

`--env ''` means no filter and puts **the entire environment** into the template
context -- tokens, keys and all. Never do that for a document you will commit,
publish or send. Always pass a prefix.

## Running a command for data

`--exec` runs a command and parses its stdout:

```bash
weav render report.j2 --exec 'tasks:yaml=phabfive --format=yaml maniphest search'
weav render report.j2 --exec version:json='gh release view --json tagName'
```

- No shell is involved. The command is split with `shlex`, so pipes, redirects,
  globs and `$VAR` are **not** interpreted. Wrap a pipeline in
  `sh -c '...'` if you really need one.
- The command's stderr passes through to yours.
- A non-zero exit aborts the render with exit code 1, as does output that does
  not parse. A half-rendered document is never produced.
- Output is parsed as YAML unless `:FORMAT` says otherwise.

## Reading from stdin

`-` as the SOURCE reads stdin, parsed as YAML by default:

```bash
cat data.yaml | weav render report.j2 --data -
gh api repos/o/r --jq . | weav render report.j2 --data :json=-
some-command | weav render report.j2 --data repo:json=-
```

Only one source can read stdin: a second `-` finds the stream already
exhausted and contributes nothing.

## What rendering does to your text

- **Autoescaping is on only for HTML and XML.** A template whose name ends in
  `.html`, `.htm` or `.xml` -- with or without a trailing `.j2` -- has its
  substitutions HTML-escaped. Every other name, including `.md.j2`, `.txt` and
  extensionless, substitutes verbatim. This is what keeps `&`, `<` and quotes
  intact in Markdown and config files.
- **`trim_blocks` is on, `lstrip_blocks` is not.** The newline after a block tag
  such as `{% for %}` or `{% endif %}` is swallowed, but leading whitespace
  before the tag is kept. Use `{%-` and `-%}` for the rest.
- **Output always ends with exactly one newline.** A template with no trailing
  newline gains one; otherwise the bytes are the template's own output. Long
  lines are never wrapped and are not interpreted as markup.

## Edit frontmatter

```bash
weav frontmatter doc.md --upsert status=draft
weav frontmatter doc.md --delete status,docid
weav frontmatter doc.md --upsert lorem=ipsum --stdout
```

### It edits in place

`weav frontmatter FILE` **rewrites FILE**. There is no `--dry-run` and no
confirmation. To inspect a document, or to preview an edit, pass `--stdout`,
which prints the whole document and leaves the file untouched:

```bash
weav frontmatter doc.md --stdout            # read it, change nothing
weav frontmatter doc.md --upsert x=1 --stdout   # preview the edit
```

Run the `--stdout` form first whenever you are not certain of the result.

A run that would not change the bytes does not rewrite the file at all, so its
mtime is left alone. `--verbose` reports the inserted, updated and deleted keys
on stderr.

### What counts as frontmatter

The rules are strict on purpose, because a mis-split would destroy the document:

- The block must **open** with `---` on the very first line. A document without
  one has no frontmatter, even if a `---` appears later. Upserting into such a
  document prepends a brand-new block and leaves the existing text alone -- so a
  Markdown setext heading (`Title: subtitle` underlined by `---`) stays a
  heading rather than being swallowed as metadata.
- The block **closes on the first** `---` or `...` line after it, never the
  last. A `---` thematic break further down the body is body text.
- The delimiter must be exactly `---` or `...` on its own line. `----` and an
  indented `  ---` are body text.
- The block must parse as a **mapping**. A list or a scalar is body text.
- A YAML syntax error is only fatal when the document did open with `---`.
  Otherwise weav was guessing, and guessing must not abort or destroy.

### What survives an edit

Comments, quoting styles, block scalars, a byte order mark, CRLF line endings
and the file mode all round trip, and a symlink is followed rather than
replaced. Writes go through a temporary file and an atomic rename.

What does **not** round trip is block sequence indentation: an indented

```yaml
tags:
  - a
```

comes back as

```yaml
tags:
- a
```

Upserted values are always written as strings, so `--upsert count=1` produces
`count: '1'`, not an integer. Edit the file yourself when you need a typed
scalar, a nested key or a list -- `--upsert` only sets top-level string keys.

### --upsert splits on commas

`--upsert` accepts several pairs in one argument, splitting on `,`, but only
when every resulting piece contains a `=`:

```bash
weav frontmatter doc.md --upsert a=1,b=2          # two keys
weav frontmatter doc.md --upsert 'title=Hello, World'   # one key, comma kept
```

That heuristic gets it wrong for a value that contains both a comma and an `=`,
such as a query string. Pass one `--upsert` per key when the value is not plain
prose:

```bash
weav frontmatter doc.md --upsert a=1 --upsert b=2
```

`--delete` always splits on commas, since a key name never contains one.

## The deprecated bare-template form

`weav TEMPLATE ...` still renders, by falling through to `render`, but it prints
a warning on stderr and will be removed in weav 1.0. Always write the
subcommand:

```bash
weav render template.j2 --keyval name=World
```

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Template not found, data source failed, unknown format, `--exec` command failed, or a declared frontmatter block did not parse |
| 2 | Usage error: no command, unknown option, a malformed `--upsert` pair, or a FILE that does not exist |

Errors are printed to stderr prefixed with `Error: `.

## Rules

- Write `weav render`, never the bare-template form.
- Pass `--stdout` before any `weav frontmatter` edit you are not certain of; the
  default rewrites the file.
- Never pass `--env ''`.
- Do not assume a file's suffix picks its parser. Only `.json` and `.toml` do;
  name the format with `KEY:FORMAT=SOURCE` for anything else.
- Remember `--keyval` produces strings, so `0` and `false` are truthy.
- Build a list in one source; a later source replaces it rather than extending
  it.
- Read `weav render --help` and `weav frontmatter --help` before relying on an
  option; weav is pre-1.0.
