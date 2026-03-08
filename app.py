import os
import time
import uuid
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV4
from engine.identity_engine import IdentityEngine
from engine.domain_engine import DomainEngine
from engine.lead_persistence import LeadPersistenceService

from services.logging_service import LoggingService


# ======================================
# ENVIRONMENT INITIALIZATION
# ======================================

load_dotenv()

app: Flask = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=True
)

limiter: Limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["10 per minute"]
)


# ======================================
# CORE ENGINE INITIALIZATION
# ======================================

logger: LoggingService = LoggingService()

rag_store: ChromaRAGStore = ChromaRAGStore()

agent: StudentSupportAgentV4 = StudentSupportAgentV4(rag_store)

identity_engine: IdentityEngine = IdentityEngine()

domain_engine: DomainEngine = DomainEngine()

lead_persistence: LeadPersistenceService = LeadPersistenceService()


# ======================================
# MEMORY GUARDS
# ======================================

app.session_memory = {}
app.request_memory = {}
app.question_memory = {}

MEMORY_TTL: int = 60


def cleanup_memory(
    memory_dict: Dict[str, Any],
    current_time: float
) -> None:

    expired: list[str] = []

    for key, timestamp in memory_dict.items():
        if isinstance(timestamp, (int, float)) and current_time - timestamp > MEMORY_TTL:
            expired.append(key)

    for key in expired:
        del memory_dict[key]


# ======================================
# ROOT
# ======================================

@app.route("/", methods=["GET"])
def home() -> tuple[dict[str, Any], int]:

    return (
        jsonify({
            "service": "CurioNest AI Student Support Engine",
            "version": "1.0",
            "status": "running",
            "phase": "Phase-1 Complete",
            "endpoints": {
                "health": "/health",
                "ask_question": "/ask-question",
                "capture_contact": "/capture-contact"
            }
        }),
        200
    )


# ======================================
# HEALTH CHECK
# ======================================

@app.route("/health", methods=["GET"])
def health() -> tuple[dict[str, str], int]:

    return jsonify({"status": "ok"}), 200


# ======================================
# MAIN API
# ======================================

@app.route("/ask-question", methods=["POST"])
@limiter.limit("10 per minute")
def ask_question() -> tuple[Any, int]:

    logger.log("REQUEST_RECEIVED", "/ask-question")

    client_ip: Optional[str] = request.remote_addr
    current_time: float = time.time()

    cleanup_memory(app.session_memory, current_time)
    cleanup_memory(app.request_memory, current_time)

    data: Optional[Dict[str, Any]] = request.get_json(silent=True)

    if not data:
        logger.log("INVALID_JSON", None)
        return jsonify({"error": "Invalid JSON"}), 400


# ======================================
# IDENTITY RESOLUTION
# ======================================

    identity_token: str = request.headers.get("X-Identity-Token", str(uuid.uuid4()))

    identity_id: str = identity_engine.resolve_identity(identity_token)


# ======================================
# SESSION RESOLUTION
# ======================================

    session_id: str = request.headers.get(
        "X-Session-ID",
        data.get("session_id", str(uuid.uuid4()))
    )

    identity_engine.register_session(identity_id, session_id)


# ======================================
# SESSION BURST PROTECTION
# ======================================

    last_session_time: Optional[float] = app.session_memory.get(session_id)

    if last_session_time and (current_time - last_session_time) < 1.0:
        logger.log("SESSION_BURST_BLOCKED", session_id)
        return jsonify({"error": "Session request burst detected"}), 429

    app.session_memory[session_id] = current_time


# ======================================
# IP RATE PROTECTION
# ======================================

    if client_ip:

        last_ip_time: Optional[float] = app.request_memory.get(client_ip)

        if last_ip_time and (current_time - last_ip_time) < 1.5:
            logger.log("RATE_ANOMALY_DETECTED", client_ip)
            return jsonify({"error": "Too many rapid requests"}), 429

        app.request_memory[client_ip] = current_time


# ======================================
# INPUT VALIDATION
# ======================================

    question: Optional[str] = data.get("question")

    if not question:
        return jsonify({"error": "question required"}), 400

    if not isinstance(question, str):
        return jsonify({"error": "Invalid question type"}), 400


# ======================================
# QUESTION SAFETY
# ======================================

    MAX_QUESTION_LENGTH: int = 500

    if len(question) > MAX_QUESTION_LENGTH:
        logger.log("QUESTION_TOO_LONG", len(question))
        return jsonify({"error": "Question too long"}), 400

    word_count: int = len(question.split())

    if word_count > 80:
        logger.log("QUESTION_COMPLEXITY_BLOCKED", word_count)
        return jsonify({"error": "Question too complex"}), 400


# ======================================
# DUPLICATE QUESTION GUARD
# ======================================

    normalized_question: str = " ".join(question.lower().split())

    last_question: Optional[str] = app.question_memory.get(client_ip) if client_ip else None

    if last_question and last_question == normalized_question:
        logger.log("DUPLICATE_QUESTION_BLOCKED", client_ip)
        return jsonify({"error": "Duplicate question detected"}), 429

    if client_ip:
        app.question_memory[client_ip] = normalized_question


# ======================================
# DOMAIN RESOLUTION
# ======================================

    domain: str = domain_engine.resolve_domain(data)

    context: Dict[str, Any] = domain_engine.build_context(domain, data)


# ======================================
# AGENT EXECUTION
# ======================================

    logger.log("QUESTION_RECEIVED", {
        "question": question,
        "session_id": session_id,
        "domain": domain
    })

    try:
        result: str = agent.receive_question(
            question,
            context,
            session_id=session_id
        )
    except Exception as e:
        logger.log("AGENT_RUNTIME_EXCEPTION", str(e))
        return jsonify({"error": "Internal processing failure"}), 500


# ======================================
# RESPONSE
# ======================================

    logger.log("AGENT_DECISION", str(result))

    response = jsonify({"result": result})

    response.headers["X-Session-ID"] = session_id
    response.headers["X-Identity-Token"] = identity_token

    return response, 200


# ======================================
# CONTACT CAPTURE ENDPOINT
# ======================================

@app.route("/capture-contact", methods=["POST"])
@limiter.limit("10 per minute")
def capture_contact() -> tuple[Any, int]:

    logger.log("CONTACT_CAPTURE_REQUEST", "/capture-contact")

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    lead_id = data.get("lead_id")
    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")

    if not lead_id:
        return jsonify({"error": "lead_id required"}), 400

    success = lead_persistence.save_contact(
        lead_id=lead_id,
        name=name,
        email=email,
        phone=phone
    )

    if not success:
        logger.log("CONTACT_CAPTURE_FAILED", lead_id)
        return jsonify({"error": "Contact save failed"}), 500

    logger.log("CONTACT_CAPTURE_SUCCESS", lead_id)

    return jsonify({"status": "contact saved"}), 200


# ======================================
# SERVER ENTRY
# ======================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=bool(int(os.getenv("FLASK_DEBUG", 0))),
    )