import os
import time
import uuid

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV4
from engine.identity_engine import IdentityEngine
from engine.domain_engine import DomainEngine

from services.logging_service import LoggingService


# ======================================
# ENVIRONMENT INITIALIZATION
# ======================================

load_dotenv()

app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=True
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)


# ======================================
# CORE ENGINE INITIALIZATION
# ======================================

logger = LoggingService()

rag_store = ChromaRAGStore()

agent = StudentSupportAgentV4(rag_store)

identity_engine = IdentityEngine()

domain_engine = DomainEngine()


# ======================================
# MEMORY GUARDS (ANTI-ABUSE)
# ======================================

app.session_memory = {}
app.request_memory = {}
app.question_memory = {}


# ======================================
# ROOT
# ======================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "service": "CurioNest AI Student Support Engine",
        "version": "1.0",
        "status": "running",
        "phase": "Phase-1 Complete",
        "endpoints": {
            "health": "/health",
            "ask_question": "/ask-question"
        }
    })


# ======================================
# HEALTH CHECK
# ======================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({"status": "ok"}), 200


# ======================================
# MAIN API
# ======================================

@app.route("/ask-question", methods=["POST"])
@limiter.limit("10 per minute")
def ask_question():

    logger.log("REQUEST_RECEIVED", "/ask-question")

    client_ip = request.remote_addr
    current_time = time.time()

    data = request.get_json(silent=True)

    if not data:
        logger.log("INVALID_JSON", None)
        return jsonify({"error": "Invalid JSON"}), 400


# ======================================
# IDENTITY RESOLUTION
# ======================================

    identity_token = request.headers.get("X-Identity-Token")

    if not identity_token:
        identity_token = str(uuid.uuid4())

    identity_id = identity_engine.resolve_identity(identity_token)


# ======================================
# SESSION RESOLUTION
# ======================================

    session_id = request.headers.get("X-Session-ID")

    if not session_id:
        session_id = data.get("session_id")

    if not session_id:
        session_id = str(uuid.uuid4())

    identity_engine.register_session(identity_id, session_id)


# ======================================
# SESSION BURST PROTECTION
# ======================================

    last_session_time = app.session_memory.get(session_id)

    if last_session_time and (current_time - last_session_time) < 1.0:

        logger.log("SESSION_BURST_BLOCKED", session_id)

        return jsonify({
            "error": "Session request burst detected"
        }), 429

    app.session_memory[session_id] = current_time


# ======================================
# IP RATE ANOMALY PROTECTION
# ======================================

    last_ip_time = app.request_memory.get(client_ip)

    if last_ip_time and (current_time - last_ip_time) < 1.5:

        logger.log("RATE_ANOMALY_DETECTED", client_ip)

        return jsonify({
            "error": "Too many rapid requests"
        }), 429

    app.request_memory[client_ip] = current_time


# ======================================
# INPUT VALIDATION
# ======================================

    question = data.get("question")

    if not question:
        return jsonify({"error": "question required"}), 400

    if not isinstance(question, str):
        return jsonify({"error": "Invalid question type"}), 400


# ======================================
# QUESTION SAFETY CHECKS
# ======================================

    MAX_QUESTION_LENGTH = 500

    if len(question) > MAX_QUESTION_LENGTH:

        logger.log("QUESTION_TOO_LONG", len(question))

        return jsonify({"error": "Question too long"}), 400

    word_count = len(question.split())

    if word_count > 80:

        logger.log("QUESTION_COMPLEXITY_BLOCKED", word_count)

        return jsonify({"error": "Question too complex"}), 400


# ======================================
# DUPLICATE QUESTION GUARD
# ======================================

    normalized_question = question.strip().lower()

    last_question = app.question_memory.get(client_ip)

    if last_question and last_question == normalized_question:

        logger.log("DUPLICATE_QUESTION_BLOCKED", {
            "ip": client_ip,
            "question": question
        })

        return jsonify({
            "error": "Duplicate question detected"
        }), 429

    app.question_memory[client_ip] = normalized_question


# ======================================
# DOMAIN RESOLUTION (BLOCK 16)
# ======================================

    domain = domain_engine.resolve_domain(data)

    context = domain_engine.build_context(domain, data)


# ======================================
# AGENT EXECUTION
# ======================================

    logger.log("QUESTION_RECEIVED", {
        "question": question,
        "context": context,
        "session_id": session_id,
        "identity_id": str(identity_id),
        "domain": domain
    })

    try:

        result = agent.receive_question(
            question,
            context,
            session_id=session_id
        )

    except Exception as e:

        logger.log("AGENT_RUNTIME_EXCEPTION", str(e))

        return jsonify({
            "error": "Internal processing failure"
        }), 500


# ======================================
# RESPONSE
# ======================================

    logger.log("AGENT_DECISION", str(result))

    response = jsonify({
        "result": result
    })

    response.headers["X-Session-ID"] = session_id
    response.headers["X-Identity-Token"] = identity_token

    return response, 200


# ======================================
# SERVER ENTRY
# ======================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )