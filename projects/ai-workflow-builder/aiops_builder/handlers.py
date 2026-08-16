"""Node handlers for workflows a user builds in the canvas.

Project 6 registers handlers that know about incidents and bookings. A workflow
someone assembles here has no such context, so these are generic: they read
their instructions from the node's own `config` and operate on whatever is in
the run context.

Two node types have no handler here, on purpose.

**Webhook** would make a real request to a real address someone typed into a
form on a public website. **Database** would run a write against the shared
production database this demo runs on. Both are trivially easy to implement and
neither should exist, so the palette shows them as unavailable and says why,
rather than shipping versions that quietly do nothing — a node that appears to
work and does not is exactly the fake functionality Section 2 bans.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aiops_adapters import get_email_provider
from aiops_ai import get_provider
from aiops_ai.base import AIProvider
from aiops_config import Settings, get_settings
from aiops_utils import ValidationError, get_logger
from aiops_workflow import NodeType, WorkflowEngine, WorkflowNode

logger = get_logger(__name__)

#: Node types a user can add and actually run.
RUNNABLE_TYPES: tuple[NodeType, ...] = (
    NodeType.TRIGGER,
    NodeType.CONDITION,
    NodeType.TRANSFORM,
    NodeType.AI_CLASSIFICATION,
    NodeType.AI_EXTRACTION,
    NodeType.AI_SUMMARIZATION,
    NodeType.AI_GENERATION,
    NodeType.HUMAN_APPROVAL,
    NodeType.NOTIFICATION,
    NodeType.EMAIL,
)

#: Node types shown in the palette but not executable, and the honest reason.
UNAVAILABLE_TYPES: dict[NodeType, str] = {
    NodeType.WEBHOOK: (
        "Not available in this demo. A webhook node would send a real request "
        "to whatever address was typed into it, from a public website."
    ),
    NodeType.DATABASE: (
        "Not available in this demo. A database node would run writes against "
        "the shared database this deployment uses."
    ),
}

#: AI node types, for counting requests before a run.
AI_TYPES: frozenset[NodeType] = frozenset(
    {
        NodeType.AI_CLASSIFICATION,
        NodeType.AI_EXTRACTION,
        NodeType.AI_SUMMARIZATION,
        NodeType.AI_GENERATION,
    }
)


# ------------------------------------------------------------------ AI shapes


class _Classification(BaseModel):
    category: str = Field(description="One of the categories offered. Never a new one.")
    confidence: float = Field(ge=0, le=1, description="How sure you are, 0 to 1.")
    reasoning_summary: str = Field(description="One sentence explaining the choice.")


class _Extraction(BaseModel):
    fields: dict[str, str] = Field(
        description="The requested fields. Use an empty string when not present in the input."
    )


class _Summary(BaseModel):
    summary: str = Field(description="A short summary of the input.")


class _Generation(BaseModel):
    text: str = Field(description="The generated text.")


def _input_text(node: WorkflowNode, context: dict[str, Any]) -> str:
    """The text a node operates on.

    Reads the context field named in `config["input_field"]`, defaulting to
    `input`. Missing input is an error rather than an empty string — an AI node
    silently classifying nothing wastes a request and returns nonsense.
    """
    field = node.config.get("input_field") or "input"
    value = context.get(field)
    if value is None or str(value).strip() == "":
        raise ValidationError(
            f"{node.label!r} reads {field!r} from the run input, and it is empty.",
            user_message=(
                f"The step {node.label!r} needs {field!r} in the run input, and "
                "nothing was supplied. Add it in the Run panel."
            ),
        )
    return str(value)


def register_builder_handlers(
    engine: WorkflowEngine,
    *,
    settings: Settings | None = None,
    provider_override: AIProvider | None = None,
) -> WorkflowEngine:
    """Register every handler a user-built workflow may need."""
    settings = settings or get_settings()

    def _provider() -> AIProvider:
        return provider_override or get_provider(settings)

    def _record_ai(node: WorkflowNode, result: Any, extra: dict[str, Any]) -> dict[str, Any]:
        return {
            **extra,
            "_ai_model": result.model,
            "_ai_cost": result.usage.estimated_cost_usd,
        }

    def classify(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        categories = node.config.get("categories") or []
        if not categories:
            raise ValidationError(
                f"{node.label!r} has no categories configured.",
                user_message=f"The step {node.label!r} needs at least two categories.",
            )
        text = _input_text(node, context)
        result = _provider().generate_structured_output(
            f"Classify the following into exactly one of these categories: "
            f"{', '.join(categories)}.\n\n{text}",
            output_model=_Classification,
            system=(
                "You are an operations assistant at a B2B travel company. Choose "
                "only from the categories offered — never invent one. If none fit "
                "well, choose the closest and say so in your reasoning."
            ),
        )
        value = result.value
        # Written into the context so a downstream Condition can branch on it.
        context["category"] = value.category
        context["confidence"] = value.confidence
        return _record_ai(
            node,
            result,
            {
                "category": value.category,
                "confidence": value.confidence,
                "reasoning_summary": value.reasoning_summary,
            },
        )

    def extract(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        fields = node.config.get("fields") or []
        if not fields:
            raise ValidationError(
                f"{node.label!r} has no fields configured.",
                user_message=f"The step {node.label!r} needs at least one field to extract.",
            )
        text = _input_text(node, context)
        result = _provider().generate_structured_output(
            f"Extract these fields: {', '.join(fields)}.\n\n{text}",
            output_model=_Extraction,
            system=(
                "Extract only what is present in the text. Where a field is not "
                "stated, return an empty string for it — never guess a value."
            ),
        )
        context.update(result.value.fields)
        return _record_ai(node, result, {"fields": result.value.fields})

    def summarize(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        text = _input_text(node, context)
        focus = node.config.get("focus")
        result = _provider().generate_structured_output(
            (f"Summarise the following, focusing on {focus}.\n\n" if focus else "Summarise:\n\n")
            + text,
            output_model=_Summary,
            system="Summarise faithfully. Add nothing that is not in the text.",
        )
        context["summary"] = result.value.summary
        return _record_ai(node, result, {"summary": result.value.summary})

    def generate(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        instruction = node.config.get("instruction")
        if not instruction:
            raise ValidationError(
                f"{node.label!r} has no instruction configured.",
                user_message=f"The step {node.label!r} needs an instruction telling it what to write.",
            )
        text = _input_text(node, context)
        result = _provider().generate_structured_output(
            f"{instruction}\n\nContext:\n{text}",
            output_model=_Generation,
            system=(
                "You draft operational communications for a B2B travel company. "
                "Never invent a booking reference, a refund amount, a policy or a "
                "time that was not given to you. Where something is unknown, say "
                "it is unknown."
            ),
        )
        context["draft"] = result.value.text
        return _record_ai(node, result, {"text": result.value.text})

    def notify(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        message = node.config.get("message") or context.get("draft") or "(no message)"
        logger.info(
            "workflow notification",
            extra={"node": node.label, "length": len(str(message))},
        )
        return {"notified": True, "message": str(message)[:500]}

    def send_email(node: WorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        """Record an approved message. Reachable only after an approval node.

        The engine refuses to run a workflow where this node can be reached
        without approval, so arriving here means a person said yes. The context
        is checked anyway: a handler that trusted its position in a graph would
        be one rewiring away from being wrong.
        """
        approver = str(context.get("approved_by") or "").strip()
        if not context.get("approved") or not approver:
            raise ValidationError(f"{node.label!r} ran without an approval in the run context.")

        recipient = node.config.get("recipient") or context.get("recipient") or ""
        subject = node.config.get("subject") or "Operations update"
        body = str(context.get("draft") or node.config.get("body") or "")
        if not body.strip():
            raise ValidationError(
                f"{node.label!r} has nothing to send.",
                user_message=(
                    f"The step {node.label!r} had no message to send. A drafting "
                    "step before it should produce one."
                ),
            )

        message_id = get_email_provider().send_message(
            recipient=str(recipient) or "operations@example-travel.test",
            subject=str(subject),
            body=body,
            approved_by=approver,
        )
        # `transmitted` is reported explicitly so the execution log says what
        # actually happened rather than implying delivery.
        return {"recorded_message_id": message_id, "transmitted": 0, "approved_by": approver}

    engine.register(NodeType.AI_CLASSIFICATION, classify)
    engine.register(NodeType.AI_EXTRACTION, extract)
    engine.register(NodeType.AI_SUMMARIZATION, summarize)
    engine.register(NodeType.AI_GENERATION, generate)
    engine.register(NodeType.NOTIFICATION, notify)
    engine.register(NodeType.EMAIL, send_email)
    return engine


def expected_ai_requests(nodes: list[WorkflowNode]) -> int:
    """How many AI requests a run of these nodes would spend, at most.

    Shown on the Run button. An upper bound rather than an estimate: a
    Condition may skip a branch, so a run can cost less, never more.
    """
    return sum(1 for node in nodes if node.type in AI_TYPES)
