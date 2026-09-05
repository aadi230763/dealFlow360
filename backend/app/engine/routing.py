"""Pure routing. A rule triggers if ANY of its non-null thresholds is met; the required
chain is every triggered rule, in sequence. No rules triggered -> auto-approve."""

from dataclasses import dataclass
from decimal import Decimal

from app.engine.risk import RiskResult


@dataclass
class ApprovalRuleData:
    id: str
    name: str
    level: int
    min_blended: Decimal | None
    min_peak: Decimal | None
    min_erosion_amount: Decimal | None
    required_roles: list[str]
    sequence: int
    is_active: bool


@dataclass
class ApprovalStep:
    rule_id: str
    rule_name: str
    level: int
    required_role: str
    sequence: int
    reason: str


def determine_chain(risk: RiskResult, rules: list[ApprovalRuleData]) -> list[ApprovalStep]:
    chain: list[ApprovalStep] = []
    for rule in sorted((r for r in rules if r.is_active), key=lambda r: r.sequence):
        reasons = []
        if rule.min_blended is not None and risk.blended >= rule.min_blended:
            reasons.append(f"blended overage {risk.blended} points meets the {rule.min_blended} threshold")
        if rule.min_peak is not None and risk.peak >= rule.min_peak:
            reasons.append(f"peak overage {risk.peak} points meets the {rule.min_peak} threshold")
        if rule.min_erosion_amount is not None and risk.erosion >= rule.min_erosion_amount:
            reasons.append(f"erosion amount {risk.erosion} meets the {rule.min_erosion_amount} threshold")

        if reasons:
            role = rule.required_roles[0] if rule.required_roles else "ADMIN"
            chain.append(
                ApprovalStep(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    level=rule.level,
                    required_role=role,
                    sequence=rule.sequence,
                    reason=f"{role.replace('_', ' ').title()} required: " + "; ".join(reasons) + f" on rule '{rule.name}'.",
                )
            )
    return chain


def explain(chain: list[ApprovalStep]) -> list[str]:
    if not chain:
        return ["No rule triggered -- auto-approved, straight to fulfillment."]
    return [step.reason for step in chain]
