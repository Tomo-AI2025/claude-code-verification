"""Git operation helpers used by enforce-scope and clean-commits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from git import Repo
from git.exc import (
    BadName,
    GitCommandError,
    InvalidGitRepositoryError,
    NoSuchPathError,
)


class GitOpsError(RuntimeError):
    """Wraps gitpython errors into a single public exception."""


@dataclass
class ChangeInfo:
    file_path: str
    change_type: str   # "added" | "modified" | "deleted" | "renamed"
    additions: int
    deletions: int


@dataclass
class CommitInfo:
    sha: str
    message: str
    full_message: str
    changed_files: List[str]
    additions: int
    deletions: int
    diff_text: str


def _open_repo(repo_path: str) -> Repo:
    try:
        return Repo(repo_path, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError) as e:
        raise GitOpsError(f"not a git repository: {repo_path}") from e


def _resolve_commit(repo: Repo, commit: str):
    try:
        return repo.commit(commit)
    except (BadName, ValueError) as e:
        raise GitOpsError(f"commit not found: {commit}") from e


def get_changed_files(commit: str = "HEAD", repo_path: str = ".") -> List[str]:
    """Return paths changed in ``commit`` (using POSIX separators)."""
    repo = _open_repo(repo_path)
    c = _resolve_commit(repo, commit)
    return [p.replace("\\", "/") for p in c.stats.files.keys()]


def get_change_info(commit: str = "HEAD", repo_path: str = ".") -> List[ChangeInfo]:
    """Return structured change info for each path in ``commit``."""
    repo = _open_repo(repo_path)
    c = _resolve_commit(repo, commit)

    if c.parents:
        parent = c.parents[0]
        diffs = parent.diff(c)
    else:
        diffs = c.diff(None)

    change_types = {}
    for d in diffs:
        path = d.b_path or d.a_path
        if d.change_type == "A":
            change_types[path] = "added"
        elif d.change_type == "D":
            change_types[path] = "deleted"
        elif d.change_type == "R":
            change_types[path] = "renamed"
        else:
            change_types[path] = "modified"

    result: List[ChangeInfo] = []
    for path, stats in c.stats.files.items():
        result.append(ChangeInfo(
            file_path=path.replace("\\", "/"),
            change_type=change_types.get(path, "modified"),
            additions=stats.get("insertions", 0),
            deletions=stats.get("deletions", 0),
        ))
    return result


def get_diff_for_file(commit: str, file_path: str, repo_path: str = ".") -> str:
    repo = _open_repo(repo_path)
    c = _resolve_commit(repo, commit)
    if c.parents:
        return repo.git.diff(c.parents[0].hexsha, c.hexsha, "--", file_path)
    return repo.git.show(c.hexsha, "--", file_path)


def generate_revert_patch(commit: str, files: List[str],
                          repo_path: str = ".") -> str:
    """Produce a patch that reverts ``files`` from ``commit`` back to its parent.

    Apply with ``git apply``.
    """
    if not files:
        return ""
    repo = _open_repo(repo_path)
    c = _resolve_commit(repo, commit)
    if not c.parents:
        raise GitOpsError("cannot revert initial commit")
    return repo.git.diff(c.hexsha, c.parents[0].hexsha, "--", *files)


# ---------- commit history ----------


def _commit_diff_text(repo: Repo, c) -> str:
    if c.parents:
        return repo.git.diff(c.parents[0].hexsha, c.hexsha)
    return repo.git.show(c.hexsha, "--format=")


def get_commit_history(since: str = "HEAD~10", repo_path: str = ".") -> List[CommitInfo]:
    """Return commits in the range implied by ``since``.

    ``since`` accepts:
      - a range spec like ``"origin/main..HEAD"`` (used verbatim)
      - a single ref like ``"HEAD~10"`` (expanded to ``"<ref>..HEAD"``)
    """
    repo = _open_repo(repo_path)
    rev_range = since if ".." in since else f"{since}..HEAD"

    try:
        commits = list(repo.iter_commits(rev_range))
    except (BadName, ValueError, GitCommandError) as e:
        raise GitOpsError(f"cannot resolve commit range: {since}") from e

    result: List[CommitInfo] = []
    for c in commits:
        full = c.message.rstrip()
        first_line = full.splitlines()[0] if full else ""
        stats = c.stats.files
        additions = sum(f.get("insertions", 0) for f in stats.values())
        deletions = sum(f.get("deletions", 0) for f in stats.values())
        try:
            diff_text = _commit_diff_text(repo, c)
        except GitCommandError:
            diff_text = ""
        result.append(CommitInfo(
            sha=c.hexsha[:7],
            message=first_line,
            full_message=full,
            changed_files=list(stats.keys()),
            additions=additions,
            deletions=deletions,
            diff_text=diff_text,
        ))
    return result
