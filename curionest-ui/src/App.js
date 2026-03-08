import React, { useState, useEffect } from "react";
import axios from "axios";

/* ===============================
   API BASE
================================= */

const API_BASE =
  process.env.REACT_APP_API_BASE || "http://127.0.0.1:5000";

/* ===============================
   SUBJECTS
================================= */

const SUBJECTS = {
  Physics: ["Electricity"],
  Chemistry: ["Atomic Structure", "Chemical Bonding"],
  Maths: ["Quadratic Equations", "Trigonometry"],
  Biology: ["Cell Structure", "Plant Processes"]
};

/* ===============================
   SESSION MANAGEMENT
================================= */

function getSessionId() {
  let id = localStorage.getItem("curionest_session");

  if (!id) {
    id = "sess_" + Math.random().toString(36).substring(2, 10);
    localStorage.setItem("curionest_session", id);
  }

  return id;
}

/* ===============================
   RESPONSE INTERPRETER
================================= */

function interpretResponse(raw) {
  if (!raw) return { text: "", type: "empty" };

  if (raw.includes("Duplicate")) {
    return {
      text: "You just asked this question. Try modifying it slightly.",
      type: "system"
    };
  }

  if (raw.includes("Too many rapid requests")) {
    return {
      text: "You're asking questions too quickly. Please wait a moment.",
      type: "system"
    };
  }

  if (raw.includes("ESCALATE TO SME")) {
    return {
      text:
        "This question may require teacher assistance. A teacher will review it.",
      type: "escalation"
    };
  }

  return { text: raw, type: "ai" };
}

/* ===============================
   AXIOS ERROR INTERPRETER
================================= */

function interpretAxiosError(err) {

  if (err.response) {

    if (err.response.data && err.response.data.error) {
      return interpretResponse(err.response.data.error);
    }

    return {
      text: `Server error (${err.response.status})`,
      type: "system"
    };
  }

  if (err.request) {
    return {
      text: "Backend not responding",
      type: "system"
    };
  }

  return {
    text: "Request failed",
    type: "system"
  };
}

/* ===============================
   STRUCTURED ANSWER
================================= */

function StructuredAnswer({ text }) {

  return (
    <div>
      <div style={{ marginBottom: 6, fontWeight: "bold" }}>
        Concept Explanation
      </div>

      <div style={{ lineHeight: 1.5 }}>
        {text}
      </div>
    </div>
  );
}

/* ===============================
   MAIN APP
================================= */

function App() {

  const [subject, setSubject] = useState("Physics");
  const [chapter, setChapter] = useState(SUBJECTS["Physics"][0]);

  const [question, setQuestion] = useState("");

  const [response, setResponse] = useState({
    text: "",
    type: "empty"
  });

  const [loading, setLoading] = useState(false);

  const [thinkingDots, setThinkingDots] = useState("");

  const [history, setHistory] = useState([]);

  const [abortController, setAbortController] = useState(null);

  /* ===============================
     LOAD HISTORY
  ================================= */

  useEffect(() => {

    const stored = localStorage.getItem("curionest_history");

    if (stored) {

      try {
        setHistory(JSON.parse(stored));
      }
      catch {
        localStorage.removeItem("curionest_history");
      }

    }

  }, []);

  /* ===============================
     SAVE HISTORY
  ================================= */

  useEffect(() => {

    localStorage.setItem(
      "curionest_history",
      JSON.stringify(history)
    );

  }, [history]);

  /* ===============================
     THINKING DOTS ANIMATION
  ================================= */

  useEffect(() => {

    if (!loading) return;

    const interval = setInterval(() => {

      setThinkingDots(prev =>
        prev.length >= 3 ? "." : prev + "."
      );

    }, 400);

    return () => clearInterval(interval);

  }, [loading]);

  /* ===============================
     SUBJECT CHANGE
  ================================= */

  const handleSubjectChange = (value) => {

    if (loading) return;

    setSubject(value);

    setChapter(SUBJECTS[value][0]);

  };

  /* ===============================
     HISTORY RECALL
  ================================= */

  const recallInteraction = (item) => {

    if (loading) return;

    setQuestion(item.question);

    setSubject(item.subject);

    setChapter(item.chapter);

  };

  /* ===============================
     CLEAR HISTORY
  ================================= */

  const clearHistory = () => {

    if (loading) return;

    setHistory([]);

    localStorage.removeItem("curionest_history");

    setResponse({
      text: "Conversation history cleared.",
      type: "system"
    });

  };

  /* ===============================
     ASK QUESTION
  ================================= */

  const askQuestion = async () => {

    if (loading) return;

    if (!question.trim()) {

      setResponse({
        text: "Please enter a question",
        type: "system"
      });

      return;
    }

    if (abortController) {
      abortController.abort();
    }

    const controller = new AbortController();

    setAbortController(controller);

    const snapshot = { question, subject, chapter };

    setLoading(true);

    setThinkingDots(".");

    setResponse({
      text: "Thinking",
      type: "system"
    });

    try {

      const res = await axios.post(

        `${API_BASE}/ask-question`,

        {
          domain: "education",
          session_id: getSessionId(),
          question,
          subject,
          chapter
        },

        {
          signal: controller.signal
        }

      );

      const interpreted = interpretResponse(res.data.result);

      setResponse(interpreted);

      setHistory(prev => [

        {
          question: snapshot.question,
          subject: snapshot.subject,
          chapter: snapshot.chapter,
          answer: interpreted.text
        },

        ...prev

      ].slice(0, 5));

      setQuestion("");

    }
    catch (err) {

      if (
        err.name === "CanceledError" ||
        err.code === "ERR_CANCELED"
      ) {
        return;
      }

      setResponse(interpretAxiosError(err));

    }

    setLoading(false);

  };

  const isQuestionEmpty = !question.trim();

  const headerLabel =
    response.type === "ai"
      ? "AI Answer"
      : response.type === "escalation"
      ? "Teacher Review Required"
      : "System Message";

  const displayText =
    loading && response.text === "Thinking"
      ? `Thinking${thinkingDots}`
      : response.text;

  /* ===============================
     RENDER
  ================================= */

  return (

    <div style={{ padding: 40, fontFamily: "Arial", maxWidth: 700 }}>

      <h2>CurioNest</h2>

      <label><b>Subject</b></label><br />

      <select
        value={subject}
        onChange={(e) => !loading && handleSubjectChange(e.target.value)}
        disabled={loading}
      >

        {Object.keys(SUBJECTS).map((subj) => (

          <option key={subj} value={subj}>
            {subj}
          </option>

        ))}

      </select>

      <br /><br />

      <label><b>Chapter</b></label><br />

      <select
        value={chapter}
        onChange={(e) => !loading && setChapter(e.target.value)}
        disabled={loading}
      >

        {SUBJECTS[subject].map((chap) => (

          <option key={chap} value={chap}>
            {chap}
          </option>

        ))}

      </select>

      <br /><br />

      <label><b>Question</b></label><br />

      <textarea
        value={question}
        onChange={(e) => !loading && setQuestion(e.target.value)}
        rows={3}
        disabled={loading}
        style={{ width: "100%" }}
      />

      <br /><br />

      <button
        onClick={askQuestion}
        disabled={loading || isQuestionEmpty}
      >
        {loading ? "Processing..." : "Ask"}
      </button>

      {history.length > 0 && (

        <button
          onClick={clearHistory}
          style={{ marginLeft: 10 }}
        >
          Clear History
        </button>

      )}

      <div style={{ marginTop: 20 }}>
        <b>Context:</b> {subject} → {chapter}
      </div>

      <div
        style={{
          padding: 14,
          border: "1px solid #d5dbdb",
          marginTop: 12
        }}
      >

        <div style={{ fontWeight: "bold" }}>
          {headerLabel}
        </div>

        <div style={{ marginTop: 8 }}>

          {response.type === "ai"
            ? <StructuredAnswer text={displayText} />
            : displayText}

        </div>

      </div>

      {history.length > 0 && (

        <div style={{ marginTop: 30 }}>

          <b>Recent Questions</b>

          {history.map((item, idx) => (

            <div
              key={idx}
              onClick={() => !loading && recallInteraction(item)}
              style={{ marginTop: 10, cursor: "pointer" }}
            >

              <div>
                <b>Q:</b> {item.question}
              </div>

              <div style={{ fontSize: 12, color: "#666" }}>
                Context: {item.subject} → {item.chapter}
              </div>

              <div>
                <b>A:</b> {item.answer}
              </div>

            </div>

          ))}

        </div>

      )}

    </div>

  );
}

export default App;