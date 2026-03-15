from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV5

print("\nStarting Agent Debug\n")

rag = ChromaRAGStore()
agent = StudentSupportAgentV5(rag_store=rag)

context = {
    "subject": "cbse_physics",
    "chapter": "electricity"
}

while True:

    question = input("\nAsk Question > ")

    if question == "exit":
        break

    result = agent.receive_question(
        question=question,
        context=context,
        session_id="debug_session"
    )

    print("\nResponse:\n")
    print(result)