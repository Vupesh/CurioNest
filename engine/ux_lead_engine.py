# engine/ux_lead_engine.py

class UXLeadEngine:

    def __init__(self):
        self.sessions = {}

    def _ensure_session(self, session_id):
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "lead_prompted": False
            }

    def evaluate(self, session_id, escalation_confidence, engagement_score):

        self._ensure_session(session_id)

        session = self.sessions[session_id]

        # --- Combined behavioral signal ---
        combined_score = escalation_confidence + engagement_score

        # --- Progressive disclosure logic ---
        eligible = (
            escalation_confidence >= 15 and     # strong escalation signal
            engagement_score >= 10 and          # real engagement depth
            combined_score >= 25 and            # combined intent threshold
            not session["lead_prompted"]        # only once per session
        )

        if eligible:
            session["lead_prompted"] = True
            return True

        return False

    def get_prompt_message(self):
        return (
            "It appears you may benefit from structured academic support. "
            "Would you like to connect with a teacher for personalized guidance?"
        )