"""Jev fixed-choice adapter. No business labels, rubric selection, or fallback."""

import math

from pydantic import JsonValue, ValidationError

from binfocheck.domain.common import Availability, Available, Outcome
from binfocheck.domain.decisions import DecisionRecord, DecisionResult
from binfocheck.domain.interfaces import DecisionRequest

from .errors import ModelError
from .json import object_value, text_value
from .persistence import ModelAdapter


def decision_result(request: DecisionRequest, body: dict[str, JsonValue]) -> DecisionResult:
    answers = object_value(body.get("answers"))
    if set(answers) != {"q0"}:
        raise ModelError("invalid_provider_response")
    answer = object_value(answers["q0"])
    if answer.get("type") != "choice":
        raise ModelError("invalid_provider_response")
    label = text_value(answer.get("choice"))
    if label not in request.allowed_labels:
        raise ModelError("unknown_decision_label")
    confidence = answer.get("confidence")
    if (
        not isinstance(confidence, (float, int))
        or isinstance(confidence, bool)
        or not 0 <= confidence <= 1
        or not math.isfinite(confidence)
    ):
        raise ModelError("invalid_provider_response")
    raw = answer.get("probabilities")
    values: dict[str, float] | None = None
    availability = Availability.UNAVAILABLE
    reason = "Provider did not report probabilities"
    if raw is not None:
        probabilities = object_value(raw)
        values = {}
        for key, value in probabilities.items():
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not 0 <= value <= 1
                or not math.isfinite(value)
                or key not in request.allowed_labels
            ):
                raise ModelError("invalid_probabilities")
            values[key] = float(value)
        availability = (
            Availability.AVAILABLE
            if set(values) == set(request.allowed_labels)
            else Availability.INCOMPLETE
        )
        reason = "Provider reported a partial distribution"
    if request.probabilities_required and availability != Availability.AVAILABLE:
        raise ModelError("required_probabilities_missing")
    if availability == Availability.AVAILABLE and values is not None:
        if values[label] != max(values.values()):
            raise ModelError("choice_probability_mismatch")
    try:
        return DecisionResult(
            allowed_labels=request.allowed_labels,
            label=label,
            probabilities=Available(
                availability=availability,
                data=values,
                reason=None if availability == Availability.AVAILABLE else reason,
            ),
        )
    except ValidationError:
        raise ModelError("invalid_probabilities") from None


class JevDecisionModel(ModelAdapter):
    provider = "jev"

    def decide(self, request: DecisionRequest) -> Outcome[DecisionRecord]:
        return self.execute(request)
