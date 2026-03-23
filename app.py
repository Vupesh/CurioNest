from dotenv import load_dotenv
load_dotenv()

import os
import traceback

from flask import Flask, request, jsonify
from flask_cors import CORS

from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV5
from engine.session_memory import SessionMemoryService
from services.logging_service import LoggingService
from capture_lead import capture_lead

app = Flask(__name__)
CORS(app)

logger = LoggingService()

# ================= SERVICES =================

rag_store = ChromaRAGStore()
session_memory = SessionMemoryService()

agent = StudentSupportAgentV5(
    rag_store=rag_store,
    session_engine=session_memory
)

# ================= ROOT =================

@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "running"})

# ================= HEALTH =================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "CurioNest Backend"
    })

# ================= DOMAIN CONFIG =================

@app.route("/domain-config", methods=["GET"])
def domain_config():
    return jsonify({
        "education": {
            "CBSE": {
                "physics": [
                    "light_reflection_refraction",
                    "human_eye_colourful_world",
                    "electricity",
                    "magnetic_effects_of_current"
                ],
                "chemistry": [
                    "chemical_reactions_equations",
                    "acids_bases_salts",
                    "metals_non_metals",
                    "carbon_compounds"
                ],
                "biology": [
                    "life_processes",
                    "control_coordination",
                    "reproduction",
                    "heredity"
                ]
            },
            "ICSE": {
                "physics": [
                    "force",
                    "work_power_energy",
                    "light",
                    "sound",
                    "electricity_magnetism",
                    "modern_physics"
                ],
                "chemistry": [
                    "periodic_properties",
                    "chemical_bonding",
                    "acids_bases_salts",
                    "analytical_chemistry",
                    "mole_concept",
                    "electrolysis",
                    "metallurgy",
                    "study_of_compounds",
                    "organic_chemistry"
                ],
                "biology": [
                    "basic_biology",
                    "plant_physiology",
                    "human_anatomy",
                    "population",
                    "human_evolution",
                    "pollution"
                ]
            }
        }
    })

# ================= ASK =================

@app.route("/ask-question", methods=["POST"])
def ask_question():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"type": "error", "message": "Invalid request"}), 400

        question = data.get("question")
        if not question:
            return jsonify({"type": "error", "message": "No question provided"}), 400

        board = data.get("board", "").strip().lower()
        subject = data.get("subject", "").strip().lower()
        chapter = data.get("chapter", "").strip().lower()
        session_id = data.get("session_id", "default")

        logger.log("QUESTION_RECEIVED", {
            "session_id": session_id,
            "subject": f"{board}_{subject}",
            "chapter": chapter,
            "question": question[:120]
        })

        response = agent.receive_question(
            question=question,
            context={
                "subject": f"{board}_{subject}",
                "chapter": chapter
            },
            session_id=session_id
        )

        return jsonify(response)

    except Exception:
        traceback.print_exc()
        return jsonify({
            "type": "error",
            "message": "Internal server error"
        }), 500

# ================= LEAD =================

@app.route("/capture-lead", methods=["POST"])
def capture_lead_route():
    return capture_lead()

# ================= START =================

if __name__ == "__main__":
    app.run(debug=True, port=5000)