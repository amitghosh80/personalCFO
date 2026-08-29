"""Best-effort Linear integration: every /api/feedback submission creates a
Bug-labeled issue in the Personal CFO project, so nothing gets lost in the
feedback table waiting to be triaged. Runs as a background task and never
raises into the request — a Linear outage or missing API key must never break
feedback submission.
"""
import logging

import requests

from ..config import get_settings

logger = logging.getLogger("personalcfo.linear")

_API_URL = "https://api.linear.app/graphql"
_TIMEOUT_SECONDS = 10

_ISSUE_CREATE_MUTATION = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue { identifier url }
  }
}
"""


def create_bug_issue(title: str, description: str) -> None:
    """Create a Bug-labeled issue from feedback. No-op if LINEAR_API_KEY isn't
    configured."""
    settings = get_settings()
    if not settings.linear_api_key:
        logger.info("LINEAR_API_KEY not set — skipping Linear issue creation")
        return
    try:
        resp = requests.post(
            _API_URL,
            json={
                "query": _ISSUE_CREATE_MUTATION,
                "variables": {
                    "input": {
                        "teamId": settings.linear_team_id,
                        "projectId": settings.linear_project_id,
                        "labelIds": [settings.linear_bug_label_id],
                        "title": title,
                        "description": description,
                    }
                },
            },
            headers={"Authorization": settings.linear_api_key, "Content-Type": "application/json"},
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = resp.json()
        result = body.get("data", {}).get("issueCreate") if body.get("data") else None
        if body.get("errors") or not (result and result.get("success")):
            logger.error(f"Linear issueCreate did not succeed: {body}")
        else:
            logger.info(f"Created Linear issue {result['issue']['identifier']} from feedback")
    except Exception:
        logger.exception("Failed to create Linear issue for feedback")
