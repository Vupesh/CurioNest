from dotenv import load_dotenv
load_dotenv()

import os
import traceback
import psycopg2

from flask import Flask, request, jsonify
from flask_cors import CORS

from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV5
from engine.session_memory import SessionMemoryService
from services.logging_service import LoggingService

from capture_lead import capture_lead

# ====================================
# APP INIT
# ====================================

app = Flask(__name__)
CORS(app)

logger = LoggingService()

# ====================================
# SERVICES
# ====================================

rag_store = ChromaRAGStore()
session_memory = SessionMemoryService()

agent = StudentSupportAgentV5(
    rag_store=rag_store,
    session_engine=session_memory
)

# ====================================
# DB CONNECTION (FOR ADMIN USE)
# ====================================

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# ====================================
# ROOT HEALTH CHECK
# ====================================

@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "status": "running",
        "service": "CurioNest API"
    })

# ====================================
# DOMAIN CONFIG (UI DROPDOWNS)
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
# MAIN QUESTION API
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

        board = data.get("board", "").strip().lower()
        subject = data.get("subject", "").strip().lower()
        chapter = data.get("chapter", "").strip().lower()
        question = data.get("question", "").strip()

        if not question:
            return jsonify({
                "type": "error",
                "message": "No question provided"
            }), 400

        subject_key = f"{board}_{subject}"

        context = {
            "subject": subject_key,
            "chapter": chapter
        }

        # LOG INPUT
        logger.log("QUESTION_RECEIVED", {
            "session_id": session_id,
            "subject": subject_key,
            "chapter": chapter,
            "question": question[:120]
        })

        # AGENT EXECUTION
        response = agent.receive_question(
            question=question,
            context=context,
            session_id=session_id
        )

        # LOG OUTPUT
        logger.log("QUESTION_RESPONSE", {
            "session_id": session_id,
            "response_type": response.get("type"),
            "message": response.get("message", "")[:120]
        })

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
    return capture_lead()

# ====================================
# LEADS FETCH (ADMIN INTERNAL)
# ====================================

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

# ====================================
# UPDATE LEAD STATUS
# ====================================

@app.route("/leads/<lead_id>", methods=["PATCH"])
def update_lead(lead_id):

    try:
        data = request.json
        status = data.get("status")

        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            "UPDATE leads SET status=%s WHERE id=%s",
            (status, lead_id)
        )

        conn.commit()

        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        print("UPDATE ERROR:", e)
        return jsonify({"success": False})

# ====================================
# RUN
# ====================================

if __name__ == "__main__":
    app.run(debug=True, port=5000)