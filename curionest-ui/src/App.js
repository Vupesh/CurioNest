import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";

const API_BASE = "http://127.0.0.1:5000";

/* SESSION */
const getSessionId = () => {
  let id = localStorage.getItem("curionest_session");
  if (!id) {
    id = "sess_" + Math.random().toString(36).substring(2) + Date.now();
    localStorage.setItem("curionest_session", id);
  }
  return id;
};

function App() {

  const [config, setConfig] = useState(null);

  const [board, setBoard] = useState("");
  const [subject, setSubject] = useState("");
  const [chapter, setChapter] = useState("");

  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");

  const [loading, setLoading] = useState(false);

  const [showEscalation, setShowEscalation] = useState(false);
  const [showLeadForm, setShowLeadForm] = useState(false);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  const chatEndRef = useRef(null);

  /* SCROLL */
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* LOAD DOMAIN CONFIG */
  useEffect(() => {
    axios.get(`${API_BASE}/domain-config`)
      .then(res => setConfig(res.data))
      .catch(() => alert("Failed to load config"));
  }, []);

  /* DERIVED */
  const boards = config ? Object.keys(config.education || {}) : [];

  const subjects =
    board && config?.education?.[board]
      ? Object.keys(config.education[board])
      : [];

  const chapters =
    board && subject && config?.education?.[board]?.[subject]
      ? config.education[board][subject]
      : [];

  // ================= ASK =================
  const askQuestion = useCallback(async () => {

    if (!question.trim()) return;

    if (!board || !subject || !chapter) {
      alert("Select Board, Subject, Chapter");
      return;
    }

    const q = question.trim();

    setMessages(prev => [...prev, { role: "user", text: q }]);
    setQuestion("");
    setLoading(true);

    // RESET escalation UI
    setShowEscalation(false);
    setShowLeadForm(false);

    try {

      const res = await axios.post(`${API_BASE}/ask-question`, {
        session_id: getSessionId(),
        board,
        subject,
        chapter,
        question: q
      });

      const result = res.data;
      const msg = result.message || "";

      // ================= SMALLTALK =================
      if (result.type === "smalltalk") {
        setMessages(prev => [...prev, { role: "ai", text: msg }]);
        return;
      }

      // ================= HARD ESCALATION =================
      if (result.type === "escalation") {
        setMessages(prev => [...prev, { role: "ai", text: msg }]);
        setShowEscalation(true);
        return;
      }

      // ================= NORMAL + SOFT ESCALATION =================
      setMessages(prev => [...prev, { role: "ai", text: msg }]);

      // 🔥 Detect soft escalation from message
      const lowerMsg = msg.toLowerCase();

      const isSoftEscalation =
        lowerMsg.includes("want help from a teacher") ||
        lowerMsg.includes("teacher can guide you");

      if (isSoftEscalation) {
        setShowEscalation(true);
      }

    } catch {

      setMessages(prev => [
        ...prev,
        { role: "ai", text: "System temporarily unavailable." }
      ]);

    } finally {
      setLoading(false);
    }

  }, [question, board, subject, chapter]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askQuestion();
    }
  };

  // ================= LEAD =================
  const submitLead = async () => {

    if (!name || !email || !phone) {
      alert("Fill all fields");
      return;
    }

    try {
      await axios.post(`${API_BASE}/capture-lead`, {
        session_id: getSessionId(),
        name,
        email,
        phone
      });

      setShowLeadForm(false);

      setMessages(prev => [
        ...prev,
        { role: "ai", text: "✅ Teacher will contact you soon." }
      ]);

    } catch {
      alert("Submission failed");
    }
  };

  const rejectTeacher = () => {

    setShowEscalation(false);
    setShowLeadForm(false);

    setMessages(prev => [
      ...prev,
      {
        role: "ai",
        text: "No problem 👍 Let’s continue. Ask your doubt."
      }
    ]);
  };

  return (
    <div style={{ padding: 20, maxWidth: 800, margin: "auto" }}>

      <h2>CurioNest</h2>

      {/* DROPDOWNS */}
      <select value={board} onChange={(e) => {
        setBoard(e.target.value);
        setSubject("");
        setChapter("");
      }}>
        <option value="">Select Board</option>
        {boards.map(b => <option key={b}>{b}</option>)}
      </select>

      <select value={subject} onChange={(e) => {
        setSubject(e.target.value);
        setChapter("");
      }}>
        <option value="">Select Subject</option>
        {subjects.map(s => <option key={s}>{s}</option>)}
      </select>

      <select value={chapter} onChange={(e) => setChapter(e.target.value)}>
        <option value="">Select Chapter</option>
        {chapters.map(c => <option key={c}>{c}</option>)}
      </select>

      {/* CHAT */}
      <div style={{ marginTop: 20 }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            textAlign: m.role === "user" ? "right" : "left",
            marginBottom: 10
          }}>
            <div style={{
              display: "inline-block",
              padding: 10,
              background: m.role === "user" ? "#DCF8C6" : "#eee",
              borderRadius: 10,
              maxWidth: "75%"
            }}>
              <ReactMarkdown>{m.text}</ReactMarkdown>
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {loading && <p>Thinking...</p>}

      {/* INPUT */}
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={3}
        style={{ width: "100%", marginTop: 20 }}
      />

      <button onClick={askQuestion}>Ask</button>

      {/* ESCALATION */}
      {showEscalation && (
        <div style={{ border: "2px solid orange", padding: 15, marginTop: 20 }}>
          <h3>Talk to a Teacher</h3>

          <button onClick={() => setShowLeadForm(true)}>Yes</button>
          <button onClick={rejectTeacher} style={{ marginLeft: 10 }}>No</button>
        </div>
      )}

      {/* LEAD FORM */}
      {showLeadForm && (
        <div style={{ marginTop: 20 }}>
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input placeholder="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <button onClick={submitLead}>Submit</button>
        </div>
      )}

    </div>
  );
}

export default App;