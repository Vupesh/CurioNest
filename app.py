from flask import Flask, request, jsonify
from flask_cors import CORS
import traceback

from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV5
from services.logging_service import LoggingService


# ====================================
# APP INITIALIZATION
# ====================================

app = Flask(__name__)
CORS(app)

logger = LoggingService()

print("\nStarting CurioNest Backend\n")


# ====================================
# LOAD RAG + AGENT
# ====================================

rag_store = ChromaRAGStore()
agent = StudentSupportAgentV5(rag_store=rag_store)

print("Vector DB Loaded")
print("Agent V5 Initialized\n")


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
# ROOT (OPTIONAL)
# ====================================

@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "message": "CurioNest backend running"
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

        # --------------------------------
        # Normalize inputs
        # --------------------------------

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

        # --------------------------------
        # AI Agent Processing
        # --------------------------------

        response = agent.receive_question(
            question=question,
            context=context,
            session_id=session_id
        )

        # Response already structured
        return jsonify(response)

    except Exception as e:

        print("\nASK QUESTION ERROR\n")
        traceback.print_exc()

        logger.log("ASK_QUESTION_ERROR", str(e))

        return jsonify({
            "type": "error",
            "message": "Internal server error processing question."
        }), 500


# ====================================
# SERVER START
# ====================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )