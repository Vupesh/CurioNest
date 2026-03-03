import time


class LeadEngine:

    def __init__(self):
        self.leads = {}  # temporary in-memory store

    def evaluate_lead(self,
                      session_id,
                      subject,
                      chapter,
                      escalation_code,
                      escalation_reason,
                      escalation_confidence,
                      engagement_score,
                      intent_strength):

        LEAD_THRESHOLD = 25  # adjustable later

        if escalation_confidence < LEAD_THRESHOLD:
            return None

        lead = {
            "session_id": session_id,
            "subject": subject,
            "chapter": chapter,
            "escalation_code": escalation_code,
            "escalation_reason": escalation_reason,
            "escalation_confidence": escalation_confidence,
            "engagement_score": engagement_score,
            "intent_strength": intent_strength,
            "timestamp": time.time(),
            "capture_status": "QUALIFIED"
        }

        self.leads[session_id] = lead
        return lead

    def get_lead(self, session_id):
        return self.leads.get(session_id)