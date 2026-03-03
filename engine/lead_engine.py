import time


class LeadEngine:

    # ---- Allowed Lifecycle States ----
    STATUS_QUALIFIED = "QUALIFIED"
    STATUS_CONTACT_REQUESTED = "CONTACT_REQUESTED"
    STATUS_CONTACT_CAPTURED = "CONTACT_CAPTURED"
    STATUS_DECLINED = "DECLINED"
    STATUS_EXPIRED = "EXPIRED"

    def __init__(self):
        # session_id → lead object
        self.leads = {}

    # ===============================
    # Lead Qualification
    # ===============================

    def evaluate_lead(
        self,
        session_id,
        subject,
        chapter,
        escalation_code,
        escalation_reason,
        escalation_confidence,
        engagement_score,
        intent_strength
    ):

        LEAD_THRESHOLD = 25

        # Below threshold → not a lead
        if escalation_confidence < LEAD_THRESHOLD:
            return None

        # If already exists → prevent duplicate qualification
        existing = self.leads.get(session_id)
        if existing:
            return existing

        lead = {
            "session_id": session_id,
            "subject": subject,
            "chapter": chapter,
            "escalation_code": escalation_code,
            "escalation_reason": escalation_reason,
            "escalation_confidence": escalation_confidence,
            "engagement_score": engagement_score,
            "intent_strength": intent_strength,
            "status": self.STATUS_QUALIFIED,
            "created_at": time.time(),
            "updated_at": time.time()
        }

        self.leads[session_id] = lead
        return lead

    # ===============================
    # Lifecycle Updates
    # ===============================

    def update_status(self, session_id, new_status):

        if session_id not in self.leads:
            return False

        if new_status not in {
            self.STATUS_QUALIFIED,
            self.STATUS_CONTACT_REQUESTED,
            self.STATUS_CONTACT_CAPTURED,
            self.STATUS_DECLINED,
            self.STATUS_EXPIRED
        }:
            return False

        self.leads[session_id]["status"] = new_status
        self.leads[session_id]["updated_at"] = time.time()
        return True

    # ===============================
    # Lead Retrieval
    # ===============================

    def get_lead(self, session_id):
        return self.leads.get(session_id)

    def get_all_leads(self):
        return self.leads

    # ===============================
    # Deduplication Logic
    # ===============================

    def should_send_notification(self, session_id):
        """
        Prevent repeated email dispatch.
        Only send email when lead is newly qualified.
        """

        lead = self.leads.get(session_id)
        if not lead:
            return False

        return lead["status"] == self.STATUS_QUALIFIED