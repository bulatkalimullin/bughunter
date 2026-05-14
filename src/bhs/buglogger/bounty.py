from __future__ import annotations

from bhs.state import BugSchema, Impact, Reproducibility, Severity


def bounty_usd(bug: BugSchema, complexity_bonus: bool = False) -> float:
    """
    bounty = base_severity × reproducibility_multiplier × impact_factor × complexity_bonus
    complexity_bonus: ×1.2 if multi-step / memory+runtime combo (caller sets).
    """
    sev = bug.severity if isinstance(bug.severity, Severity) else Severity(str(bug.severity))
    repro = (
        bug.reproducibility
        if isinstance(bug.reproducibility, Reproducibility)
        else Reproducibility(str(bug.reproducibility))
    )
    impact = bug.impact if isinstance(bug.impact, Impact) else Impact(str(bug.impact))
    base = {
        Severity.CRITICAL: 100.0,
        Severity.HIGH: 50.0,
        Severity.MEDIUM: 25.0,
        Severity.LOW: 10.0,
        Severity.INFO: 0.0,
    }[sev]
    repro_m = {
        Reproducibility.ALWAYS: 1.0,
        Reproducibility.OFTEN: 0.7,
        Reproducibility.RARE: 0.3,
        Reproducibility.ONE_OFF: 0.1,
    }[repro]
    impact_f = {
        Impact.DATA_LOSS: 1.5,
        Impact.CRASH: 1.3,
        Impact.LEAK: 1.2,
        Impact.SLOWDOWN: 1.0,
        Impact.PRIVILEGE_ESCALATION: 2.0,
    }[impact]
    mult = 1.2 if complexity_bonus else 1.0
    return round(base * repro_m * impact_f * mult, 2)
