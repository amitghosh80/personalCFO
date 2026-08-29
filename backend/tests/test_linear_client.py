"""Unit tests for the Linear integration: must never raise, regardless of
missing config, network failure, or an unsuccessful Linear response."""
from types import SimpleNamespace

from app.services import linear_client


def _settings(**overrides):
    base = dict(
        linear_api_key="lin_api_test",
        linear_team_id="team-1",
        linear_project_id="project-1",
        linear_bug_label_id="label-1",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_noop_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(linear_client, "get_settings", lambda: _settings(linear_api_key=""))
    called = []
    monkeypatch.setattr(linear_client.requests, "post", lambda *a, **k: called.append(1))
    linear_client.create_bug_issue("title", "description")
    assert called == []


def test_posts_expected_graphql_payload(monkeypatch):
    monkeypatch.setattr(linear_client, "get_settings", lambda: _settings())
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"data": {"issueCreate": {"success": True, "issue": {"identifier": "AMI-99", "url": "http://x"}}}},
        )

    monkeypatch.setattr(linear_client.requests, "post", fake_post)
    linear_client.create_bug_issue("[Feedback] title", "description text")

    assert captured["url"] == "https://api.linear.app/graphql"
    assert captured["headers"]["Authorization"] == "lin_api_test"
    variables = captured["json"]["variables"]["input"]
    assert variables["teamId"] == "team-1"
    assert variables["projectId"] == "project-1"
    assert variables["labelIds"] == ["label-1"]
    assert variables["title"] == "[Feedback] title"
    assert variables["description"] == "description text"


def test_never_raises_on_network_error(monkeypatch):
    monkeypatch.setattr(linear_client, "get_settings", lambda: _settings())

    def boom(*a, **k):
        raise ConnectionError("network down")

    monkeypatch.setattr(linear_client.requests, "post", boom)
    linear_client.create_bug_issue("title", "description")  # must not raise


def test_never_raises_on_unsuccessful_response(monkeypatch):
    monkeypatch.setattr(linear_client, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        linear_client.requests,
        "post",
        lambda *a, **k: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"data": {"issueCreate": {"success": False}}},
        ),
    )
    linear_client.create_bug_issue("title", "description")  # must not raise
