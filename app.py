from flask import Flask, request, jsonify
from flask_cors import CORS

from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV4

app = Flask(__name__)
CORS(app)

print("\nStarting CurioNest Backend\n")

rag_store = ChromaRAGStore()
agent = StudentSupportAgentV4(rag_store=rag_store)

print("Vector DB Loaded")
print("Agent Initialized\n")


# ---------------------------------
# Health Check
# ---------------------------------

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "CurioNest backend running"})


# ---------------------------------
# Domain Config
# (Must match vector DB metadata)
# ---------------------------------

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


# ---------------------------------
# Ask Question
# ---------------------------------

@app.route("/ask-question", methods=["POST"])
def ask_question():

    data = request.json

    session_id = data.get("session_id", "default")
    board = data.get("board", "")
    subject = data.get("subject", "")
    chapter = data.get("chapter", "")
    question = data.get("question", "")

    if not question:
        return jsonify({"result": "No question provided"}), 400

    # -----------------------------
    # Normalize values
    # -----------------------------

    board = board.strip().lower()
    subject = subject.strip().lower()
    chapter = chapter.strip().lower()

    # -----------------------------
    # Convert board+subject
    # to match vector metadata
    # -----------------------------

    subject_key = f"{board}_{subject}"

    context = {
        "subject": subject_key,
        "chapter": chapter
    }

    try:

        answer = agent.receive_question(
            question=question,
            context=context,
            session_id=session_id
        )

        return jsonify({
            "result": answer
        })

    except Exception as e:

        print("ASK QUESTION ERROR:", str(e))

        return jsonify({
            "result": "Internal server error processing question."
        })


# ---------------------------------
# Server Start
# ---------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )