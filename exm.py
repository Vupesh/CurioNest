from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV4
from services.session_engine import SessionEngine   # ← FIXED
from engine.ux_lead_engine import UXLeadEngine


def run_session(agent, session_id, context, questions):
    print(f"\n===== SESSION START: {session_id} =====\n")

    for i, q in enumerate(questions, start=1):
        print(f"\n--- Q{i}: {q}")
        response = agent.receive_question(q, context, session_id=session_id)
        print(f"\nResponse:\n{response}")

    print(f"\n===== SESSION END: {session_id} =====\n")


if __name__ == "__main__":
    # Initialize systems
    rag = ChromaRAGStore()
    session_engine = SessionEngine()
    ux_engine = UXLeadEngine()

    agent = StudentSupportAgentV4(
        rag,
        session_engine=session_engine,
        ux_engine=ux_engine
    )

    context = {
        "subject": "physics",
        "chapter": "electricity"
    }

    # Test 1 – Escalation Momentum
    questions_session_1 = [
        "I need urgent help before exam tomorrow",
        "Prove Ohm's law",
        "I am still confused"
    ]

    run_session(agent, "prod1", context, questions_session_1)

    # Test 2 – Session Isolation
    questions_session_2 = [
        "Define electric current",
        "What is resistance?"
    ]

    run_session(agent, "prod2", context, questions_session_2)