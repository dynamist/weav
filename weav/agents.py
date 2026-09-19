"""The resources block that closes weav's help, and the skill it points at.

An AI agent that meets weav for the first time reads --help and nothing else,
so the flag that would teach it the rest has to be advertised there.
"""

from __future__ import annotations

from typing import Any

from typer.core import TyperCommand

AGENT_HELP_FOOTER = (
    "Templates: ./templates, ~/.local/share/weav/templates, ~/Documents/weav/templates\n"
    "Data:      --data, --exec, --env, --keyval, merged in that order (last wins)\n"
    "Docs:      https://github.com/dynamist/weav#readme\n"
    "Home:      https://github.com/dynamist/weav\n"
    "\n"
    "Are you an AI? Use these resources ONLY IF your task specifically asks you to:\n"
    "  Help a human install or configure weav:\n"
    "    https://github.com/dynamist/weav#readme\n"
    "  Render a Jinja2 template, or read or change a document's YAML frontmatter:\n"
    "    SKIP if a weav skill is already in your context. Otherwise run: weav --skill"
)


class AgentFooterMixin:
    """Mix into a command or group to end its help with the resources block.

    The text is written line by line rather than passed to Typer as epilog=,
    because click's default format_epilog runs it through write_text, which
    rewraps the paragraphs and drops the indentation the block is made of.
    """

    # ctx and formatter are Click objects; see the note on
    # WeavGroup.resolve_command for why they cannot be named portably here.
    def format_epilog(self, ctx: Any, formatter: Any) -> None:  # noqa: ANN401
        """Write the agent resources block at the end of the help page."""
        formatter.write_paragraph()
        for line in AGENT_HELP_FOOTER.splitlines():
            formatter.write(f"{line}\n")


class AgentFooterCommand(AgentFooterMixin, TyperCommand):
    """Leaf command whose help ends with the agent resources block.

    weav has no intermediate command groups, so `weav render --help` is where an
    agent looking for a command actually lands. Unlike phabfive, which carries
    the block on groups only, weav has to put it on the leaves as well.
    """
