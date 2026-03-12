from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.rag import ChromaRAGStore
from engine.agent_v4 import StudentSupportAgentV4


app = FastAPI()

# Allow React frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("\nStarting CurioNest Backend\n")

rag_store = ChromaRAGStore()
agent = StudentSupportAgentV4(rag_store=rag_store)

print("Vector DB Loaded")
print("Agent Initialized\n")


# -------------------------------
# Request Schema
# -------------------------------

class QuestionRequest(BaseModel):
    session_id: str
    domain: str
    board: str
    subject: str
    chapter: str
    question: str


# -------------------------------
# Health Check
# -------------------------------

@app.get("/")
def health():
    return {"status": "CurioNest backend running"}


# -------------------------------
# Domain Config
# -------------------------------

@app.get("/domain-config")
def domain_config():

    return {
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
    }


# -------------------------------
# Ask Question Endpoint
# -------------------------------

@app.post("/ask-question")
def ask_question(req: QuestionRequest):

    context = {
        "subject": req.subject,
        "chapter": req.chapter
    }

    answer = agent.receive_question(
        req.question,
        context,
        req.session_id
    )

    return {
        "result": answer
    }