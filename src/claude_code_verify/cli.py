"""Main CLI entry point for claude-code-verify."""

import click
from rich.console import Console
from claude_code_verify import __version__

console = Console()


@click.group()
@click.version_option(__version__)
def main():
    """claude-code-verify: Auto-fix Claude Code specifications at the spec layer.

    Five commands to catch and fix the 4 patterns documented in Part 2:

    \b
      check-spec      Detect and fix phantom API references (Pattern #7)
      verify-wiring   Detect orphan functions (silent failure)
      enforce-scope   Revert scope violations (Pattern #8)
      fix-terms       Fix terminology ambiguity (Pattern #9)
      clean-commits   Rewrite dishonest commit messages

    See README-part2.md for background and examples.
    """
    pass


@main.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--fix", is_flag=True, help="Apply fixes instead of just reporting")
@click.option("--codebase", default=".", help="Path to codebase root")
def check_spec(spec_path, fix, codebase):
    """Detect phantom API references in a spec document."""
    from claude_code_verify.commands.check_spec import run
    run(spec_path, fix=fix, codebase=codebase)


@main.command()
@click.argument("target_dir", type=click.Path(exists=True), default=".")
@click.option("--fix", is_flag=True, help="Apply fixes instead of just reporting")
def verify_wiring(target_dir, fix):
    """Detect orphan functions (defined but never called)."""
    from claude_code_verify.commands.verify_wiring import run
    run(target_dir, fix=fix)


@main.command()
@click.option("--spec", required=True, type=click.Path(exists=True), help="Spec file with prohibitions")
@click.option("--commit", default="HEAD", help="Commit SHA to check (default: HEAD)")
@click.option("--fix", is_flag=True, help="Generate revert patches")
def enforce_scope(spec, commit, fix):
    """Enforce 'DO NOT MODIFY' rules declared in spec."""
    from claude_code_verify.commands.enforce_scope import run
    run(spec, commit=commit, fix=fix)


@main.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--fix", is_flag=True, help="Apply fixes instead of just reporting")
def fix_terms(spec_path, fix):
    """Detect and fix terminology ambiguity in spec."""
    from claude_code_verify.commands.fix_terms import run
    run(spec_path, fix=fix)


@main.command()
@click.option("--since", default="HEAD~10", help="Commit range to check")
@click.option("--fix", is_flag=True, help="Rewrite commit messages")
def clean_commits(since, fix):
    """Detect and fix commit messages that lie about changes."""
    from claude_code_verify.commands.clean_commits import run
    run(since=since, fix=fix)


@main.command()
@click.option("--force", is_flag=True,
              help="Overwrite existing .claude-code-verify.yml")
def init(force):
    """Initialize .claude-code-verify.yml in current directory."""
    from claude_code_verify.commands.init_config import run
    run(force=force)


if __name__ == "__main__":
    main()
