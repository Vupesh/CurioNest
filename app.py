from dotenv import load_dotenv
load_dotenv()

import os
import traceback

from flask import Flask, request, jsonify
from flask_cors import CORS

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV5
from engine.session_memory import SessionMemoryService

from services.logging_service import LoggingService

from capture_lead import capture_lead


# ====================================
# APP INITIALIZATION
# ====================================

app = Flask(__name__)
CORS(app)

logger = LoggingService()


# ====================================
# RATE LIMITER (PRODUCTION PROTECTION)
# ====================================

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["100 per hour"]
)

print("\nStarting CurioNest Backend\n")


# ====================================
# LOAD CORE SERVICES
# ====================================

try:

    rag_store = ChromaRAGStore()

    session_memory = SessionMemoryService()

    agent = StudentSupportAgentV5(
        rag_store=rag_store,
        session_engine=session_memory
    )

    print("Vector DB Loaded")
    print("Agent V5 Initialized\n")

except Exception as e:

    print("\nSYSTEM STARTUP ERROR\n")
    traceback.print_exc()
    raise e


# ====================================
# ROOT ROUTE
# ====================================

@app.route("/", methods=["GET"])
def root():

    return jsonify({
        "service": "CurioNest Backend",
        "status": "running"
    })


# ====================================
# HEALTH CHECK
# ====================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "ok",
        "service": "CurioNest Backend"
    })


# ====================================
# DOMAIN CONFIG
# ====================================

@app.route("/domain-config", methods=["GET"])
def domain_config():

    return jsonify({
        "education": {

            "CBSE": {

                "physics": [
                    "light_reflection_refraction",
                    "human_eye",
                    "electricity",
                    "magnetic_effects_of_current"
                ],

                "chemistry": [
                    "chemical_reactions_equations",
                    "acid_bases_salts",
                    "metals_non_metals",
                    "carbon_and_its_compounds"
                ],

                "biology": [
                    "life_processes",
                    "control_coordinations",
                    "how_do_organisms_reproduce",
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
                    "acid_bases_salt",
                    "analytical_chemistry",
                    "mole_concept_stoichiometry",
                    "electrolysis",
                    "metallurgy",
                    "study_of_compounds",
                    "organic_chemistry"
                ],

                "biology": [
                    "basic_biology",
                    "plant_physiology",
                    "human_anatomy_and_physiology",
                    "population",
                    "human_evolution",
                    "polution"
                ]
            }

        }
    })


# ====================================
# ASK QUESTION API
# ====================================

@app.route("/ask-question", methods=["POST"])
@limiter.limit("10 per minute")
def ask_question():

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "type": "error",
                "message": "Invalid request"
            }), 400

        session_id = data.get("session_id", "default")

        board = data.get("board", "")
        subject = data.get("subject", "")
        chapter = data.get("chapter", "")
        question = data.get("question", "")

        if not question:
            return jsonify({
                "type": "error",
                "message": "No question provided"
            }), 400

        # ---------------- NORMALIZE INPUT ----------------

        board = board.strip().lower()
        subject = subject.strip().lower()
        chapter = chapter.strip().lower()

        subject_key = f"{board}_{subject}"

        context = {
            "subject": subject_key,
            "chapter": chapter
        }

        logger.log("QUESTION_RECEIVED", {
            "session_id": session_id,
            "subject": subject_key,
            "chapter": chapter,
            "question": question[:120]
        })

        # ---------------- AGENT PROCESSING ----------------

        response = agent.receive_question(
            question=question,
            context=context,
            session_id=session_id
        )

        return jsonify(response)

    except Exception as e:

        print("\nASK QUESTION ERROR\n")
        traceback.print_exc()

        logger.log("ASK_QUESTION_ERROR", str(e))

        return jsonify({
            "type": "error",
            "message": "System temporarily unavailable."
        }), 500


# ====================================
# LEAD CAPTURE API
# ====================================

@app.route("/capture-lead", methods=["POST"])
def capture_lead_route():

    try:

        return capture_lead()

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "status": "error",
            "message": "Lead capture failed"
        }), 500


# ====================================
# SERVER START
# ====================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=False
    )