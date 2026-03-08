# engine/ux_lead_engine.py


class UXLeadEngine:

    # ================================
    # CONFIGURATION THRESHOLDS
    # ================================

    MIN_ESCALATION_CONFIDENCE = 15
    MIN_ENGAGEMENT_SCORE = 10
    MIN_COMBINED_SCORE = 25

    # ================================
    # INITIALIZATION
    # ================================

    def __init__(self):

        # session memory
        self.sessions = {}

    # ================================
    # SESSION INITIALIZATION
    # ================================

    def _ensure_session(self, session_id):

        if session_id not in self.sessions:

            self.sessions[session_id] = {
                "lead_prompted": False,
                "contact_captured": False,
                "last_interaction": None
            }

    # ================================
    # ELIGIBILITY EVALUATION
    # ================================

    def evaluate(self, session_id, escalation_confidence, engagement_score):

        self._ensure_session(session_id)

        session = self.sessions[session_id]

        # -------------------------------
        # Combined behavioral signal
        # -------------------------------

        combined_score = escalation_confidence + engagement_score

        # -------------------------------
        # Progressive disclosure logic
        # -------------------------------

        eligible = (
            escalation_confidence >= self.MIN_ESCALATION_CONFIDENCE
            and engagement_score >= self.MIN_ENGAGEMENT_SCORE
            and combined_score >= self.MIN_COMBINED_SCORE
            and not session["lead_prompted"]
        )

        if eligible:

            session["lead_prompted"] = True

            return True

        return False

    # ================================
    # CONTACT CAPTURE FLAG
    # ================================

    def mark_contact_captured(self, session_id):

        self._ensure_session(session_id)

        self.sessions[session_id]["contact_captured"] = True

    # ================================
    # PROMPT MESSAGE
    # ================================

    def get_prompt_message(self):

        return (
            "It appears you may benefit from structured academic support. "
            "Would you like to connect with a teacher for personalized guidance?"
        )