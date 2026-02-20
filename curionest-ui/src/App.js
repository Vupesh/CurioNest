import React, { useState, useEffect } from "react";
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "";

const SUBJECTS = {
  Physics: ["Laws of Motion", "Work Energy Power", "Gravitation"],
  Chemistry: ["Atomic Structure", "Chemical Bonding"],
  Maths: ["Quadratic Equations", "Trigonometry"],
  Biology: ["Cell Structure", "Plant Processes"]
};

function interpretResponse(raw) {
  if (!raw) return { text: "", type: "empty" };

  if (raw.includes("Insufficient information in provided syllabus content")) {
    return {
      text:
        "I don’t have enough material in this chapter to answer confidently. " +
        "Try selecting a different chapter or rephrasing the question.",
      type: "system"
    };
  }

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

  if (raw.includes("Question too long")) {
    return {
      text: "Your question is too long. Please make it shorter and clearer.",
      type: "system"
    };
  }

  if (raw.includes("Question too complex")) {
    return {
      text: "Your question seems too complex. Please simplify it.",
      type: "system"
    };
  }

  if (raw.includes("Daily token budget exceeded")) {
    return {
      text: "The system has reached its usage limit for today. Please try later.",
      type: "system"
    };
  }

  if (raw.includes("Hourly token budget exceeded")) {
    return {
      text: "The system is temporarily busy. Please retry shortly.",
      type: "system"
    };
  }

  if (raw.includes("ESCALATE TO SME")) {
    return {
      text: "This question requires teacher assistance. It will be reviewed.",
      type: "escalation"
    };
  }

  return { text: raw, type: "ai" };
}

function interpretAxiosError(err) {
  if (err.response && err.response.data && err.response.data.error) {
    return interpretResponse(err.response.data.error);
  }

  if (err.response && err.response.status === 429) {
    return {
      text: "You just asked this question. Try modifying it slightly.",
      type: "system"
    };
  }

  return { text: "Server unreachable", type: "system" };
}

function StructuredAnswer({ text }) {
  return (
    <div>
      <div style={{ marginBottom: 6, fontWeight: "bold" }}>
        Concept Explanation
      </div>
      <div style={{ lineHeight: 1.5 }}>{text}</div>
    </div>
  );
}

function App() {
  const [subject, setSubject] = useState("Physics");
  const [chapter, setChapter] = useState(SUBJECTS["Physics"][0]);
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState({ text: "", type: "empty" });
  const [loading, setLoading] = useState(false);
  const [thinkingDots, setThinkingDots] = useState("");
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const stored = localStorage.getItem("curionest_history");
    if (stored) {
      try {
        setHistory(JSON.parse(stored));
      } catch {
        localStorage.removeItem("curionest_history");
      }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("curionest_history", JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    if (!loading) return;

    const interval = setInterval(() => {
      setThinkingDots(prev => (prev.length >= 3 ? "." : prev + "."));
    }, 400);

    return () => clearInterval(interval);
  }, [loading]);

  const handleSubjectChange = (value) => {
    if (loading) return;
    setSubject(value);
    setChapter(SUBJECTS[value][0]);
  };

  const recallInteraction = (item) => {
    if (loading) return;
    setQuestion(item.question);
    setSubject(item.subject);
    setChapter(item.chapter);
  };

  const clearHistory = () => {
    if (loading) return;

    setHistory([]);
    localStorage.removeItem("curionest_history");

    setResponse({
      text: "Conversation history cleared.",
      type: "system"
    });
  };

  const askQuestion = async () => {
    if (loading) return;

    if (!question.trim()) {
      setResponse({ text: "Please enter a question", type: "system" });
      return;
    }

    const snapshot = { question, subject, chapter };

    setLoading(true);
    setThinkingDots(".");
    setResponse({ text: "Thinking", type: "system" });

    try {
      const res = await axios.post(`${API_BASE}/ask-question`, {
        question,
        subject,
        chapter
      });

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

    } catch (err) {
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

  const responseStyle = {
    padding: 12,
    borderRadius: 6,
    minHeight: 120,
    marginTop: 10,
    border:
      response.type === "escalation"
        ? "1px solid #e67e22"
        : "1px solid #ddd",
    background:
      response.type === "escalation"
        ? "#fdf2e9"
        : response.type === "system"
        ? "#f4f6f7"
        : "#f9f9f9"
  };

  const inputStyle = {
    width: "100%",
    opacity: loading ? 0.6 : 1
  };

  return (
    <div style={{ padding: 40, fontFamily: "Arial", maxWidth: 700 }}>
      <h2>CurioNest</h2>

      <label><b>Subject</b></label><br />
      <select
        value={subject}
        onChange={(e) => handleSubjectChange(e.target.value)}
        disabled={loading}
        style={inputStyle}
      >
        {Object.keys(SUBJECTS).map((subj) => (
          <option key={subj} value={subj}>{subj}</option>
        ))}
      </select>

      <br /><br />

      <label><b>Chapter</b></label><br />
      <select
        value={chapter}
        onChange={(e) => !loading && setChapter(e.target.value)}
        disabled={loading}
        style={inputStyle}
      >
        {SUBJECTS[subject].map((chap) => (
          <option key={chap} value={chap}>{chap}</option>
        ))}
      </select>

      <br /><br />

      <label><b>Question</b></label><br />
      <textarea
        value={question}
        onChange={(e) => !loading && setQuestion(e.target.value)}
        rows={3}
        disabled={loading}
        style={inputStyle}
      />

      <br /><br />

      <button onClick={askQuestion} disabled={loading || isQuestionEmpty}>
        {loading ? "Processing..." : "Ask"}
      </button>

      {history.length > 0 && (
        <button onClick={clearHistory} disabled={loading} style={{ marginLeft: 10 }}>
          Clear History
        </button>
      )}

      <div style={{ marginTop: 20, fontSize: 14, color: "#555" }}>
        <b>Context:</b> {subject} → {chapter}
      </div>

      <div style={responseStyle}>
        <b>{headerLabel}</b>
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
              onClick={() => recallInteraction(item)}
              style={{ marginTop: 10, cursor: "pointer" }}
            >
              <div><b>Q:</b> {item.question}</div>
              <div style={{ fontSize: 12, color: "#666" }}>
                Context: {item.subject} → {item.chapter}
              </div>
              <div><b>A:</b> {item.answer}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default App;