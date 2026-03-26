from dotenv import load_dotenv

load_dotenv()

import os
import traceback

import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS

from capture_lead import capture_lead
from engine.agent_v4 import StudentSupportAgentV5
from engine.rag import ChromaRAGStore
from engine.session_memory import SessionMemoryService
from services.logging_service import LoggingService

app = Flask(__name__)
CORS(app)
logger = LoggingService()

rag_store = ChromaRAGStore()
session_memory = SessionMemoryService()
agent = StudentSupportAgentV5(rag_store=rag_store, session_engine=session_memory)

DOMAIN_CONFIG = {
    "education": {
        "CBSE": {
            "physics": [
                "light_reflection_refraction",
                "human_eye",
                "electricity",
                "magnetic_effects_of_current",
            ],
            "chemistry": [
                "chemical_reactions_equations",
                "acid_bases_salts",
                "metals_non_metals",
                "carbon_and_its_compounds",
            ],
            "biology": [
                "life_processes",
                "control_coordinations",
                "how_do_organisms_reproduce",
                "heredity",
            ],
        },
        "ICSE": {
            "physics": [
                "force",
                "work_power_energy",
                "light",
                "sound",
                "electricity_magnetism",
                "modern_physics",
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
                "organic_chemistry",
            ],
            "biology": [
                "basic_biology",
                "plant_physiology",
                "human_anatomy_and_physiology",
                "population",
                "human_evolution",
                "polution",
            ],
        },
    }
}


def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def _is_valid_selection(board, subject, chapter):
    board_map = DOMAIN_CONFIG["education"].get(board.upper())
    if not board_map:
        return False
    chapters = board_map.get(subject.lower())
    if not chapters:
        return False
    return chapter.lower() in [c.lower() for c in chapters]


@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "running", "service": "CurioNest API"})


@app.route("/domain-config", methods=["GET"])
def domain_config():
    return jsonify(DOMAIN_CONFIG)


@app.route("/ask-question", methods=["POST"])
def ask_question():
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id", "default")
        board = (data.get("board") or "").strip()
        subject = (data.get("subject") or "").strip()
        chapter = (data.get("chapter") or "").strip()
        question = (data.get("question") or "").strip()

        if not question:
            return jsonify({"type": "message", "message": "Please type your question first."}), 200

        if not board or not subject or not chapter:
            return jsonify(
                {
                    "type": "message",
                    "message": (
                        "I’m ready to help 👍 Please select Board > Subject > Chapter first, "
                        "then ask your doubt or exam goal."
                    ),
                }
            ), 200

        if not _is_valid_selection(board, subject, chapter):
            return jsonify(
                {
                    "type": "message",
                    "message": "Selection is not valid. Please ask under correct subject > chapter",
                }
            ), 200

        context = {
            "board": board.lower(),
            "subject": subject.lower(),
            "chapter": chapter.lower(),
        }

        logger.log(
            "QUESTION_RECEIVED",
            {
                "session_id": session_id,
                "board": board,
                "subject": subject,
                "chapter": chapter,
                "question": question[:160],
            },
        )

        response = agent.receive_question(question=question, context=context, session_id=session_id)

        logger.log(
            "QUESTION_RESPONSE",
            {
                "session_id": session_id,
                "response_type": response.get("type"),
                "message": response.get("message", "")[:160],
            },
        )

        return jsonify(response)

    except Exception as e:
        print("\nASK QUESTION ERROR\n")
        traceback.print_exc()
        logger.log("ASK_QUESTION_ERROR", str(e))
        return jsonify({"type": "message", "message": "I’m here. Please ask again in simple words."}), 200


@app.route("/capture-lead", methods=["POST"])
def capture_lead_route():
    return capture_lead()


@app.route("/leads", methods=["GET"])
def get_leads():
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT 100")

        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

        result = [dict(zip(columns, row)) for row in rows]

        cur.close()
        conn.close()

        return jsonify(result)

    except Exception as e:
        print("LEADS ERROR:", e)
        return jsonify([])


@app.route("/leads/<lead_id>", methods=["PATCH"])
def update_lead(lead_id):
    try:
        data = request.json
        status = data.get("status")

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("UPDATE leads SET status=%s WHERE id=%s", (status, lead_id))

        conn.commit()

        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        print("UPDATE ERROR:", e)
        return jsonify({"success": False})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
