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
                    "electricity",
                    "light_reflection_refraction"
                ],
                "chemistry": [
                    "acids_bases_salts"
                ],
                "biology": [
                    "life_processes"
                ]
            },
            "ICSE": {
                "physics": [
                    "force",
                    "light",
                    "sound"
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