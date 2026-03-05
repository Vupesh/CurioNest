from dotenv import load_dotenv
load_dotenv()

from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV4
from engine.session_engine import SessionEngine
from engine.ux_lead_engine import UXLeadEngine
from engine.lead_engine import LeadEngine


lead_engine = LeadEngine()


def run_session(agent, session_id, context, questions):
    print(f"\n===== SESSION START: {session_id} =====\n")

    for i, q in enumerate(questions, start=1):
        print(f"\n--- Q{i}: {q}")

        response = agent.receive_question(
            q,
            context,
            session_id=session_id
        )

        print("\n-----------------------------------")
        print(f"Response:\n{response}")
        print("-----------------------------------")

    print(f"\n===== SESSION END: {session_id} =====\n")


if __name__ == "__main__":

    rag = ChromaRAGStore()

    session_engine = SessionEngine()

    ux_engine = UXLeadEngine()

    agent = StudentSupportAgentV4(
        rag,
        session_engine=session_engine,
        ux_engine=ux_engine,
        lead_engine=lead_engine
    )

    context = {
        "subject": "physics",
        "chapter": "electricity"
    }

    # TEST 1 – Escalation momentum
    questions_session_1 = [
        "I need urgent help before exam tomorrow",
        "Prove Ohm's law",
        "I am still confused"
    ]

    run_session(agent, "prod1", context, questions_session_1)

    # TEST 2 – Session isolation
    questions_session_2 = [
        "Define electric current",
        "What is resistance?"
    ]

    run_session(agent, "prod2", context, questions_session_2)

    print("\nGenerated Leads:")

    print(getattr(lead_engine, "leads", "Lead list not available"))

