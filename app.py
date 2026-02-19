import os
import time
import uuid
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

from data.documents import DOCUMENTS
from engine.agent_v4 import StudentSupportAgentV4
from engine.rag import ChromaRAGStore
from services.email_service import EmailService
from services.logging_service import LoggingService

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


load_dotenv()

app = Flask(__name__)
CORS(app)  # ✅ REQUIRED for React ↔ Flask communication

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)

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
@limiter.limit("10 per minute")
def ask_question():

    logger.log("REQUEST_RECEIVED", "/ask-question")

    client_ip = request.remote_addr
    current_time = time.time()

    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        session_id = str(uuid.uuid4())

    if not hasattr(app, "session_memory"):
        app.session_memory = {}

    last_session_time = app.session_memory.get(session_id)
    if last_session_time and (current_time - last_session_time) < 1.0:
        logger.log("SESSION_BURST_BLOCKED", session_id)
        return jsonify({"error": "Session request burst detected"}), 429

    app.session_memory[session_id] = current_time

    if not hasattr(app, "request_memory"):
        app.request_memory = {}

    last_time = app.request_memory.get(client_ip)
    if last_time and (current_time - last_time) < 1.5:
        logger.log("RATE_ANOMALY_DETECTED", client_ip)
        return jsonify({"error": "Too many rapid requests"}), 429

    app.request_memory[client_ip] = current_time

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

    word_count = len(question.split())
    if word_count > 80:
        logger.log("QUESTION_COMPLEXITY_BLOCKED", word_count)
        return jsonify({"error": "Question too complex"}), 400

    if not hasattr(app, "question_memory"):
        app.question_memory = {}

    normalized_question = question.strip().lower()
    last_question = app.question_memory.get(client_ip)

    if last_question and last_question == normalized_question:
        logger.log("DUPLICATE_QUESTION_BLOCKED", {
            "ip": client_ip,
            "question": question
        })
        return jsonify({"error": "Duplicate question detected"}), 429

    app.question_memory[client_ip] = normalized_question

    logger.log("QUESTION_SIZE", len(question))
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

    response = jsonify({"result": result})
    response.headers["X-Session-ID"] = session_id

    return response, 200


if __name__ == "__main__":
    app.run(debug=True)
