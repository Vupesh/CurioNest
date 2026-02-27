import time


class SessionEngine:

    def __init__(self):
        self.sessions = {}

    def get_session(self, session_id):

        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "question_count": 0,
                "advanced_question_count": 0,
                "escalation_count": 0,
                "chapter_frequency": {},
                "last_question_time": None,
                "engagement_score": 0
            }

        return self.sessions[session_id]

    def update_on_question(self, session_id, chapter, difficulty):

        session = self.get_session(session_id)

        session["question_count"] += 1

        if difficulty == "advanced":
            session["advanced_question_count"] += 1

        if chapter:
            session["chapter_frequency"][chapter] = \
                session["chapter_frequency"].get(chapter, 0) + 1

        session["last_question_time"] = time.time()

        return session

    def update_on_escalation(self, session_id):

        session = self.get_session(session_id)
        session["escalation_count"] += 1
        return session

    def calculate_engagement_score(self, session_id):

        session = self.get_session(session_id)

        score = (
            session["question_count"] * 1
            + session["advanced_question_count"] * 2
            + session["escalation_count"] * 3
            + max(session["chapter_frequency"].values(), default=0) * 1.5
        )

        session["engagement_score"] = score

        return score