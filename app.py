import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from data.documents import DOCUMENTS

from engine.agent_v4 import StudentSupportAgentV4
from engine.rag import ChromaRAGStore
from services.email_service import EmailService

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize core components
rag_store = ChromaRAGStore(documents=DOCUMENTS)
agent = StudentSupportAgentV4(rag_store)
email_service = EmailService()


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "CurioNest AI Student Support Engine",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "ask_question": "/ask-question"
        }
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/ask-question", methods=["POST"])
def ask_question():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    question = data.get("question")
    subject = data.get("subject")
    chapter = data.get("chapter")

    if not question or not subject or not chapter:
        return jsonify({
            "error": "question, subject, and chapter are required"
        }), 400

    context = {
        "subject": subject,
        "chapter": chapter
    }

    # 1️⃣ Ask engine
    result = agent.receive_question(question, context)

    # 2️⃣ Escalation side-effect (EMAIL LIVES HERE, NOT IN ENGINE)
    if "ESCALATE" in result:
        email_service.send_escalation(
            subject=f"CurioNest Escalation | {subject} - {chapter}",
            body=f"""
Student Question:
{question}

Context:
Subject: {subject}
Chapter: {chapter}

Engine Decision:
{result}
"""
        )

    # 3️⃣ Always return engine result to client
    return jsonify({
        "result": result
    }), 200


if __name__ == "__main__":
    app.run(debug=True)
