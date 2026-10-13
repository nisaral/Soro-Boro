"""Soro-Boro Reference Integration: GitHub Issue / Ops Ticket Creation.

Demonstrates:
1. Preventing duplicate ticket/issue creation on network timeouts.
2. Generating stable operation identity from repository and issue title.
3. Authoritative title-search reconciler with fail-closed safety.
"""

from __future__ import annotations

import time
from typing import Any

from soro_boro.boundary import TimeoutException, soro_wrap
from soro_boro.identity import OperationIdentity
from soro_boro.lifecycle import (
    ProviderLifecycleState,
    ReconciliationResult,
    SideEffectClass,
)


class MockGitHubBackend:
    """Mock GitHub Issues API with network fault injection."""

    def __init__(self):
        self.issues: list[dict[str, Any]] = []
        self.drop_ack: bool = False
        self.duplicate_issues_count: int = 0

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str,
        op_id: str,
    ) -> dict[str, Any]:
        # Check for duplicates by title in same repo
        for iss in self.issues:
            if iss["repo"] == repo and iss["title"] == title:
                self.duplicate_issues_count += 1

        issue_num = len(self.issues) + 1
        issue_obj = {
            "number": issue_num,
            "repo": repo,
            "title": title,
            "body": body,
            "op_id": op_id,
            "created_at": time.time(),
        }
        self.issues.append(issue_obj)

        if self.drop_ack:
            self.drop_ack = False
            raise TimeoutException("504 Gateway Timeout while waiting for GitHub API response")

        return issue_obj

    def find_issue_by_op_id(self, repo: str, op_id: str) -> dict[str, Any] | None:
        for iss in self.issues:
            if iss["repo"] == repo and iss["op_id"] == op_id:
                return iss
        return None


def build_github_reconciler(backend: MockGitHubBackend, repo: str):
    def reconciler(op: OperationIdentity) -> ReconciliationResult:
        found = backend.find_issue_by_op_id(repo, op.operation_id)
        if found:
            return ReconciliationResult(
                state=ProviderLifecycleState.SUCCEEDED,
                authoritative=True,
                raw_response=found,
            )
        return ReconciliationResult(
            state=ProviderLifecycleState.NOT_FOUND,
            authoritative=True,
            consistency_observed="strong",
        )

    return reconciler
