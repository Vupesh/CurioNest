import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from data.documents import DOCUMENTS

from engine.agent_v4 import StudentSupportAgentV4
from engine.rag import ChromaRAGStore
from services.email_service import EmailService
from services.logging_service import LoggingService

# ✅ Rate limiter
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# Load environment variables
load_dotenv()

app = Flask(__name__)

# ✅ Attach limiter (per-IP protection)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

# Initialize core components
rag_store = ChromaRAGStore(documents=DOCUMENTS)
agent = StudentSupportAgentV4(rag_store)
email_service = EmailService()
logger = LoggingService()


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
@limiter.limit("10 per minute")  # ✅ Explicit protection
def ask_question():

    logger.log("REQUEST_RECEIVED", "/ask-question")

    data = request.get_json(silent=True)

    if not data:
        logger.log("INVALID_JSON", None)
        return jsonify({"error": "Invalid JSON"}), 400

    question = data.get("question")
    subject = data.get("subject")
    chapter = data.get("chapter")

    if not question or not subject or not chapter:
        logger.log("VALIDATION_FAILED", data)
        return jsonify({
            "error": "question, subject, and chapter are required"
        }), 400

    if not isinstance(question, str) or not isinstance(subject, str) or not isinstance(chapter, str):
        logger.log("TYPE_VALIDATION_FAILED", {
            "question_type": str(type(question)),
            "subject_type": str(type(subject)),
            "chapter_type": str(type(chapter))
        })
        return jsonify({"error": "Invalid data types"}), 400

    MAX_QUESTION_LENGTH = 500
    if len(question) > MAX_QUESTION_LENGTH:
        logger.log("QUESTION_TOO_LONG", len(question))
        return jsonify({"error": "Question too long"}), 400

    logger.log("QUESTION_RECEIVED", {
        "question": question,
        "subject": subject,
        "chapter": chapter
    })

    context = {
        "subject": subject,
        "chapter": chapter
    }

    logger.log("AGENT_CALL", {
        "component": "StudentSupportAgentV4",
        "operation": "receive_question"
    })

    # ✅ CRITICAL FIX — Proper exception boundary
    try:
        result = agent.receive_question(question, context)
    except Exception as e:
        logger.log("AGENT_RUNTIME_EXCEPTION", str(e))
        return jsonify({"error": "Internal processing failure"}), 500

    logger.log("AGENT_DECISION", str(result))

    if "ESCALATE" in str(result):

        logger.log("ESCALATION_TRIGGERED", {
            "reason": str(result),
            "question": question,
            "subject": subject,
            "chapter": chapter
        })

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

    return jsonify({"result": result}), 200


if __name__ == "__main__":
    app.run(debug=True)
