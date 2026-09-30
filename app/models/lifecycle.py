"""活动生命周期状态机定义。"""

from __future__ import annotations

from enum import Enum


class LifecycleStatus(str, Enum):
    DRAFT = "draft"
    PLAN_REVIEW = "plan_review"
    SENT_TO_AGENT2 = "sent_to_agent2"
    RESOURCE_CONFIG = "resource_config"
    TODO_EXECUTION = "todo_execution"
    TESTING = "testing"
    SCHEDULED = "scheduled"
    LIVE = "live"
    MONITORING = "monitoring"
    REVIEW = "review"
    ARCHIVED = "archived"


VALID_TRANSITIONS: dict[LifecycleStatus, list[LifecycleStatus]] = {
    LifecycleStatus.DRAFT: [LifecycleStatus.PLAN_REVIEW],
    LifecycleStatus.PLAN_REVIEW: [LifecycleStatus.SENT_TO_AGENT2, LifecycleStatus.DRAFT],
    LifecycleStatus.SENT_TO_AGENT2: [LifecycleStatus.RESOURCE_CONFIG],
    LifecycleStatus.RESOURCE_CONFIG: [LifecycleStatus.TODO_EXECUTION],
    LifecycleStatus.TODO_EXECUTION: [LifecycleStatus.TESTING],
    LifecycleStatus.TESTING: [LifecycleStatus.SCHEDULED, LifecycleStatus.TODO_EXECUTION],
    LifecycleStatus.SCHEDULED: [LifecycleStatus.LIVE],
    LifecycleStatus.LIVE: [LifecycleStatus.MONITORING],
    LifecycleStatus.MONITORING: [LifecycleStatus.REVIEW],
    LifecycleStatus.REVIEW: [LifecycleStatus.ARCHIVED],
    LifecycleStatus.ARCHIVED: [],
}


def can_transition(from_status: str, to_status: str) -> bool:
    try:
        src = LifecycleStatus(from_status)
        dst = LifecycleStatus(to_status)
    except ValueError:
        return False
    return dst in VALID_TRANSITIONS.get(src, [])
