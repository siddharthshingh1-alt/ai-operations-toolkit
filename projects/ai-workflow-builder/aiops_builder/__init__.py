"""Project 4 — AI Workflow Builder (CLAUDE.md Section 12).

The visual editor on top of the shared workflow engine from Section 7. This
package contains no execution logic: it stores definitions, renders them, and
calls the engine's own `run()` and `resume()`.
"""

from aiops_builder.handlers import (
    AI_TYPES,
    RUNNABLE_TYPES,
    UNAVAILABLE_TYPES,
    expected_ai_requests,
    register_builder_handlers,
)
from aiops_builder.models import ExecutionRecord, WorkflowRecord
from aiops_builder.service import (
    ai_request_estimate,
    create_workflow,
    definition_of,
    delete_workflow,
    duplicate_workflow,
    get_execution,
    get_workflow,
    issues_for,
    list_executions,
    list_workflows,
    resume_execution,
    run_workflow,
    save_workflow,
    seed_templates,
)
from aiops_builder.templates import all_templates, booking_complaint_template

__all__ = [
    "AI_TYPES",
    "RUNNABLE_TYPES",
    "UNAVAILABLE_TYPES",
    "ExecutionRecord",
    "WorkflowRecord",
    "ai_request_estimate",
    "all_templates",
    "booking_complaint_template",
    "create_workflow",
    "definition_of",
    "delete_workflow",
    "duplicate_workflow",
    "expected_ai_requests",
    "get_execution",
    "get_workflow",
    "issues_for",
    "list_executions",
    "list_workflows",
    "register_builder_handlers",
    "resume_execution",
    "run_workflow",
    "save_workflow",
    "seed_templates",
]
