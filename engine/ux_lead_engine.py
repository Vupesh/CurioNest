# engine/ux_lead_engine.py

class UXLeadEngine:

    def __init__(self):
        self.sessions = {}

    def evaluate(self, session_id, escalation_confidence, engagement_score):

        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "lead_prompted": False
            }

        session = self.sessions[session_id]

        combined_score = escalation_confidence + engagement_score

        eligible = (
            combined_score >= 25 and
            not session["lead_prompted"]
        )

        if eligible:
            session["lead_prompted"] = True
            return True

        return False

    def get_prompt_message(self):
        return (
            "It seems you may benefit from personalized guidance. "
            "Would you like to connect with a teacher for additional support?"
        )