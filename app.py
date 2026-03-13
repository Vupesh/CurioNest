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
# ---------------------------------

@app.route("/domain-config", methods=["GET"])
def domain_config():

    return jsonify({
        "education": {

            "CBSE": {

                "physics": [
                    "light_reflection_refraction",
                    "human_eye_colourful_world",
                    "electricity",
                    "magnetic_effects_current"
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
                    "organisms_reproduce",
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

# ---------------------------------
# Ask Question
# ---------------------------------

@app.route("/ask-question", methods=["POST"])
def ask_question():

    data = request.json

    session_id = data.get("session_id", "default")
    subject = data.get("subject")
    chapter = data.get("chapter")
    question = data.get("question")
    
    context = {
        "subject": subject,
        "chapter": chapter
    }

    answer = agent.receive_question(
        question,
        context,
        session_id
    )

    return jsonify({
        "result": answer
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