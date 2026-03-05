class SessionEngine:

    def __init__(self):
        self.sessions = {}

    # ================= QUESTION EVENT =================

    def update_on_question(self, session_id, chapter=None, difficulty=None):

        session = self.sessions.get(session_id)

        if not session:
            session = {
                "questions": 0,
                "escalations": 0,
                "chapters": set(),
                "difficulty_hits": 0
            }

        session["questions"] += 1

        if chapter:
            session["chapters"].add(chapter)

        if difficulty == "advanced":
            session["difficulty_hits"] += 1

        self.sessions[session_id] = session


    # ================= ESCALATION EVENT =================

    def update_on_escalation(self, session_id):

        session = self.sessions.get(session_id)

        if not session:
            return

        session["escalations"] += 1


    # ================= ENGAGEMENT SCORE =================

    def calculate_engagement_score(self, session_id):

        session = self.sessions.get(session_id)

        if not session:
            return 0

        questions = session["questions"]
        escalations = session["escalations"]
        difficulty_hits = session["difficulty_hits"]
        chapter_depth = len(session["chapters"])

        score = (
            questions * 3 +
            escalations * 10 +
            difficulty_hits * 5 +
            chapter_depth * 2
        )

        return min(score, 100)
