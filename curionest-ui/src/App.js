import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "katex/dist/katex.min.css";
import { BlockMath, InlineMath } from "react-katex";

const API = "http://127.0.0.1:5000";

function App() {
  const [config, setConfig] = useState({});
  const [board, setBoard] = useState("");
  const [subject, setSubject] = useState("");
  const [chapter, setChapter] = useState("");

  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  const [showEscalation, setShowEscalation] = useState(false);
  const [showLeadForm, setShowLeadForm] = useState(false);
  const [leadForm, setLeadForm] = useState({ name: "", email: "", phone: "" });

  const sessionId = "session_1";

  useEffect(() => {
    axios
      .get(`${API}/domain-config`)
      .then((res) => setConfig(res.data.education || {}))
      .catch(() => {
        setMessages([{ role: "ai", text: "Unable to load syllabus config right now." }]);
      });
  }, []);

  const boards = useMemo(() => Object.keys(config), [config]);
  const subjects = useMemo(() => (board ? Object.keys(config[board] || {}) : []), [board, config]);
  const chapters = useMemo(
    () => (board && subject ? config[board][subject] || [] : []),
    [board, subject, config]
  );

  const askQuestion = async () => {
    if (!question.trim()) return;

    setMessages((prev) => [...prev, { role: "user", text: question }]);
    const q = question;
    setQuestion("");
    setLoading(true);
    setShowEscalation(false);

    try {
      const res = await axios.post(`${API}/ask-question`, {
        session_id: sessionId,
        board,
        subject,
        chapter,
        question: q,
      });

      const data = res.data || {};
      setMessages((prev) => [...prev, { role: "ai", text: data.message || "Let me try again." }]);
      if (data.type === "escalation") setShowEscalation(true);
    } catch {
      setMessages((prev) => [...prev, { role: "ai", text: "I’m still here. Please try once more." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleEscalation = (choice) => {
    if (choice === "yes") {
      setShowLeadForm(true);
      setMessages((prev) => [...prev, { role: "ai", text: "Please share details so teacher can contact you." }]);
    } else {
      setShowLeadForm(false);
      setMessages((prev) => [...prev, { role: "ai", text: "Great, let’s continue step by step." }]);
    }
    setShowEscalation(false);
  };

  const submitLead = async () => {
    try {
      const payload = { ...leadForm, session_id: sessionId };
      const res = await axios.post(`${API}/capture-lead`, payload);
      const message = res?.data?.message || "Lead captured.";
      setMessages((prev) => [...prev, { role: "ai", text: message }]);
      setShowLeadForm(false);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: "Could not capture details yet. Please verify name, email, and 10-digit phone." },
      ]);
    }
  };

  const renderMessage = (text) => {
    if (!text) return null;
    if (text.includes("$$")) {
      return text.split("$$").map((part, i) => (i % 2 ? <BlockMath key={i} math={part} /> : <span key={i}>{part}</span>));
    }
    if (text.includes("\\(")) {
      const clean = text.replace(/\\\(|\\\)/g, "");
      return <InlineMath math={clean} />;
    }
    return <span>{text}</span>;
  };

  return (
    <div style={{ padding: 20, maxWidth: 860, margin: "auto", fontFamily: "Arial, sans-serif" }}>
      <h2>CurioNest — Smart Tutor</h2>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <select value={board} onChange={(e) => { setBoard(e.target.value); setSubject(""); setChapter(""); }}>
          <option value="">Board</option>
          {boards.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>

        <select value={subject} onChange={(e) => { setSubject(e.target.value); setChapter(""); }}>
          <option value="">Subject</option>
          {subjects.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <select value={chapter} onChange={(e) => setChapter(e.target.value)}>
          <option value="">Chapter</option>
          {chapters.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      <div style={{ marginTop: 16, border: "1px solid #ddd", borderRadius: 8, padding: 12, minHeight: 320, background: "#fafafa" }}>
        {messages.map((m, i) => (
          <p key={i} style={{ margin: "8px 0" }}>
            <strong>{m.role === "user" ? "You" : "CurioNest"}:</strong> {renderMessage(m.text)}
          </p>
        ))}
        {loading && <p><i>Thinking...</i></p>}
      </div>

      <textarea
        rows="3"
        style={{ width: "100%", marginTop: 10, borderRadius: 8, padding: 8 }}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask your doubt in simple words..."
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            askQuestion();
          }
        }}
      />
      <button style={{ marginTop: 8 }} onClick={askQuestion}>Send</button>

      {showEscalation && (
        <div style={{ border: "1px solid orange", borderRadius: 8, padding: 10, marginTop: 12, background: "#fff8ec" }}>
          <p>Need help from a teacher now?</p>
          <button onClick={() => handleEscalation("yes")} style={{ marginRight: 8 }}>Yes</button>
          <button onClick={() => handleEscalation("no")}>No</button>
        </div>
      )}

      {showLeadForm && (
        <div style={{ border: "1px solid #5f8", borderRadius: 8, padding: 12, marginTop: 12 }}>
          <p><strong>Teacher Callback Details</strong></p>
          <input placeholder="Name" value={leadForm.name} onChange={(e) => setLeadForm({ ...leadForm, name: e.target.value })} style={{ width: "100%", marginBottom: 6 }} />
          <input placeholder="Email" value={leadForm.email} onChange={(e) => setLeadForm({ ...leadForm, email: e.target.value })} style={{ width: "100%", marginBottom: 6 }} />
          <input placeholder="Phone (10 digits)" value={leadForm.phone} onChange={(e) => setLeadForm({ ...leadForm, phone: e.target.value })} style={{ width: "100%", marginBottom: 6 }} />
          <button onClick={submitLead}>Submit</button>
        </div>
      )}
    </div>
  );
}

export default App;
