import React, { useState, useEffect } from "react";
import axios from "axios";

const API = "http://127.0.0.1:5000";

function App() {

  // ================= STATE =================
  const [config, setConfig] = useState({});

  const [board, setBoard] = useState("");
  const [subject, setSubject] = useState("");
  const [chapter, setChapter] = useState("");

  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");

  const [loading, setLoading] = useState(false);
  const [showEscalation, setShowEscalation] = useState(false);

  // ================= LOAD CONFIG =================
  useEffect(() => {
    axios.get(`${API}/domain-config`)
      .then(res => {
        setConfig(res.data.education || {});
      })
      .catch(() => {
        alert("Failed to load configuration");
      });
  }, []);

  // ================= DERIVED =================
  const boards = Object.keys(config);

  const subjects = board && config[board]
    ? Object.keys(config[board])
    : [];

  const chapters = board && subject && config[board]?.[subject]
    ? config[board][subject]
    : [];

  // ================= ASK =================
  const askQuestion = async () => {

    if (!board || !subject || !chapter) {
      alert("Please select Board, Subject and Chapter");
      return;
    }

    if (!question.trim()) return;

    const q = question;

    // Add user message
    setMessages(prev => [...prev, { role: "user", text: q }]);

    setQuestion("");
    setLoading(true);
    setShowEscalation(false);

    try {
      const res = await axios.post(`${API}/ask-question`, {
        session_id: "session_1",
        board,
        subject,
        chapter,
        question: q
      });

      const data = res.data;

      // Add AI response
      setMessages(prev => [
        ...prev,
        { role: "ai", text: data.message }
      ]);

      // Escalation UI trigger
      if (data.type === "escalation") {
        setShowEscalation(true);
      }

    } catch {
      setMessages(prev => [
        ...prev,
        { role: "ai", text: "Something went wrong. Try again." }
      ]);
    }

    setLoading(false);
  };

  // ================= ESCALATION ACTIONS =================
  const handleEscalation = (choice) => {

    if (choice === "yes") {
      setMessages(prev => [
        ...prev,
        { role: "ai", text: "Great 👍 A teacher will reach out to you soon." }
      ]);
    } else {
      setMessages(prev => [
        ...prev,
        { role: "ai", text: "No problem 👍 Let’s continue learning." }
      ]);
    }

    setShowEscalation(false);
  };

  // ================= UI =================
  return (
    <div style={{ padding: 20, maxWidth: 800, margin: "auto" }}>

      <h2>CurioNest</h2>

      {/* DROPDOWNS */}
      <div style={{ marginBottom: 10 }}>
        <select
          value={board}
          onChange={(e) => {
            setBoard(e.target.value);
            setSubject("");
            setChapter("");
          }}
        >
          <option value="">Select Board</option>
          {boards.map(b => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>

        <select
          value={subject}
          onChange={(e) => {
            setSubject(e.target.value);
            setChapter("");
          }}
          style={{ marginLeft: 10 }}
        >
          <option value="">Select Subject</option>
          {subjects.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select
          value={chapter}
          onChange={(e) => setChapter(e.target.value)}
          style={{ marginLeft: 10 }}
        >
          <option value="">Select Chapter</option>
          {chapters.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* CHAT WINDOW */}
      <div style={{
        border: "1px solid #ccc",
        padding: 10,
        minHeight: 300,
        marginBottom: 10
      }}>
        {messages.map((m, i) => (
          <p key={i}>
            <b>{m.role === "user" ? "You" : "CurioNest"}:</b> {m.text}
          </p>
        ))}

        {loading && <p><i>Thinking...</i></p>}
      </div>

      {/* INPUT */}
      <textarea
        rows="3"
        style={{ width: "100%" }}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask your doubt..."
      />

      <button onClick={askQuestion} style={{ marginTop: 10 }}>
        Ask
      </button>

      {/* ESCALATION UI */}
      {showEscalation && (
        <div style={{
          marginTop: 15,
          padding: 10,
          border: "2px solid orange",
          borderRadius: 5
        }}>
          <p><b>Need help from a real teacher?</b></p>

          <button onClick={() => handleEscalation("yes")}>
            Yes
          </button>

          <button
            onClick={() => handleEscalation("no")}
            style={{ marginLeft: 10 }}
          >
            No
          </button>
        </div>
      )}

    </div>
  );
}

export default App;