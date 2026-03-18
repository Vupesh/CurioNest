class QueryGuardrail:

    SMALL_TALK = [
        "hi",
        "hello",
        "ok",
        "thanks",
        "thank you",
        "hmm",
        "huh",
        "?"
    ]

    def check(self, question: str):

        q = question.lower().strip()

        if q in self.SMALL_TALK:

            return {
                "type": "smalltalk",
                "message": "I'm here to help with your studies. Ask me a question from your chapter."
            }

        if len(q) < 3:

            return {
                "type": "ignore"
            }

        return None