import json
import types
import os
import sys

import pytest

# Ensure app package import path for in-repo tests
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Add repo root to sys.path so that 'app' package is importable
sys.path.insert(0, BASE)

from app.discovery.answer_extractor import AnswerExtractor
from app.discovery.question_selector import QuestionSelector
from app.discovery.question_intents import QUESTION_INTENTS
from app.discovery.progress_summary_service import ProgressSummaryService
from app.discovery.chat_service import ChatService


def test_answer_extractor_updates_product_goal():
    extractor = AnswerExtractor()
    checklist = [{"key": "product_goal", "status": "missing"}]
    delta = extractor.extract("Our goal is to build a marketplace-style app", checklist, None)
    updates = delta.get("updates", [])
    assert any(u.get("key") == "product_goal" for u in updates)
    assert delta.get("answered_keys") is not None

def test_question_selector_deterministic():
    selector = QuestionSelector()
    checklist = [
        {"key": "repo_exists", "status": "missing", "priority": "high"},
        {"key": "product_goal", "status": "missing", "priority": "high"},
    ]
    chosen = selector.select(checklist, [], [], {"status": "not_ready"})
    assert chosen in ("repo_exists", "product_goal")

def test_progress_summary_basic():
    ps = ProgressSummaryService()
    checklist = [
        {"key": "a", "status": "confirmed"},
        {"key": "b", "status": "missing"},
        {"key": "c", "status": "completed"},
    ]
    res = ps.compute_progress(checklist, {"status": "ready_for_architecture", "coverage": 0.6})
    assert res["completed"] == 2
    assert res["total"] == 3
    assert 0 <= res["percentage"] <= 100

def test_lifecycle_repository_mock(monkeypatch):
    calls = []
    class FakeRepo:
        def __init__(self, project_id):
            self.project_id = project_id
        def upsert(self, intent_key, status, answer_message_id=None):
            calls.append((self.project_id, intent_key, status, answer_message_id))
            return {}
    monkeypatch.setattr("app.discovery.lifecycle_repository.DiscoveryQuestionLifecycleRepository", FakeRepo)
    from app.discovery.question_lifecycle_service import QuestionLifecycleService
    svc = QuestionLifecycleService()
    svc.mark_asked("p1", "prod_goal")
    svc.mark_answered("p1", "prod_goal")
    assert calls[0] == ("p1", "prod_goal", "open", None)
    assert calls[1] == ("p1", "prod_goal", "answered", None)
