class EngagementEngine:

    """
    Calculates student engagement score based on
    conversation behaviour.
    """

    def __init__(self):
        pass


    # ============================================
    # COMPUTE ENGAGEMENT SCORE
    # ============================================

    def compute_score(self, question_count, signal_strength, repeat_confusion):

        """
        Engagement score range: 0 → 100

        Factors:
        - number of questions asked
        - confusion signals detected
        - repeated confusion
        """

        score = 0

        # --------------------------------
        # Question depth
        # --------------------------------

        if question_count >= 10:
            score += 40

        elif question_count >= 5:
            score += 25

        elif question_count >= 2:
            score += 10


        # --------------------------------
        # Learning signal strength
        # --------------------------------

        if signal_strength:
            score += signal_strength * 4


        # --------------------------------
        # Repeat confusion indicator
        # --------------------------------

        if repeat_confusion:
            score += 20


        # --------------------------------
        # Clamp score
        # --------------------------------

        if score > 100:
            score = 100

        return score
        