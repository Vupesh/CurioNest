import time


class EscalationEconomicsEngine:

    def __init__(self):

        # escalation budget
        self.max_escalations_per_hour = 20

        # tracking
        self.escalation_timestamps = []

    # =============================
    # LEAD QUALITY SCORE
    # =============================

    def compute_lead_quality_score(
        self,
        confidence,
        engagement_score,
        intent_strength
    ):

        score = 0

        score += confidence * 0.6
        score += engagement_score * 1.2
        score += intent_strength * 8

        return round(score, 2)

    # =============================
    # ESCALATION BUDGET CONTROL
    # =============================

    def escalation_budget_available(self):

        current_time = time.time()

        # remove timestamps older than 1 hour
        self.escalation_timestamps = [
            ts for ts in self.escalation_timestamps
            if current_time - ts < 3600
        ]

        return len(self.escalation_timestamps) < self.max_escalations_per_hour

    # =============================
    # REGISTER ESCALATION
    # =============================

    def register_escalation(self):

        self.escalation_timestamps.append(time.time())

    # =============================
    # PRIORITY TIER
    # =============================

    def determine_priority(self, lead_score):

        if lead_score >= 70:
            return "HIGH"

        if lead_score >= 45:
            return "MEDIUM"

        return "LOW"