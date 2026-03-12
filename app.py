import traceback
import sys

from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV4


def start_backend():

    print("\nStarting CurioNest Backend\n")

    try:

        rag_store = ChromaRAGStore()

        agent = StudentSupportAgentV4(
            rag_store=rag_store
        )

        print("Vector DB Loaded")
        print("Agent Initialized\n")

        return agent

    except Exception:

        print("Backend startup failed\n")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":

    agent = start_backend()

    context = {
        "subject": "physics",
        "chapter": "electricity"
    }

    print("CurioNest CLI Test Mode\n")

    while True:

        try:
            question = input("\nAsk Question (or 'exit'): ")

        except EOFError:
            break

        if question.lower() == "exit":
            break

        answer = agent.receive_question(
            question,
            context,
            session_id="test_session"
        )

        print("\nAnswer:\n")
        print(answer)