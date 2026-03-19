import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:5000";

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

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);

  const [loading, setLoading] = useState(false);

  const [showEscalation, setShowEscalation] = useState(false);
  const [showLeadForm, setShowLeadForm] = useState(false);
  const [leadSubmitted, setLeadSubmitted] = useState(false);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  const chatEndRef = useRef(null);

  // ---------------- SCROLL ----------------
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ---------------- LOAD CONFIG ----------------
  useEffect(() => {
    axios.get(`${API_BASE}/domain-config`)
      .then(res => setConfig(res.data))
      .catch(() => alert("Failed to load config"));
  }, []);

  const boards = config ? Object.keys(config.education || {}) : [];

  const subjects =
    board && config?.education?.[board]
      ? Object.keys(config.education[board])
      : [];

  const chapters =
    board && subject && config?.education?.[board]?.[subject]
      ? config.education[board][subject]
      : [];

  // ---------------- HUMAN THINKING EFFECT ----------------
  const simulateTyping = (text) => {
    return new Promise(resolve => {
      setTimeout(() => resolve(text), 500 + Math.random() * 800);
    });
  };

  // ---------------- ASK QUESTION ----------------
  const askQuestion = useCallback(async () => {

    if (!question.trim()) return;

    if (!board || !subject || !chapter) {
      alert("Please select Board, Subject and Chapter");
      return;
    }

    const q = question.trim();

    setMessages(prev => [...prev, { role: "user", text: q }]);
    setQuestion("");
    setLoading(true);

    try {

      const res = await axios.post(`${API_BASE}/ask-question`, {
        session_id: getSessionId(),
        board,
        subject,
        chapter,
        question: q
      });

      const result = res.data;

      // ---------------- ESCALATION ----------------
      if (result.type === "escalation") {

        const msg = await simulateTyping(result.message);

        setMessages(prev => [
          ...prev,
          { role: "ai", text: msg }
        ]);

        // delay CTA (feels human)
        setTimeout(() => {
          setShowEscalation(true);
        }, 800);

        return;
      }

      // ---------------- NORMAL RESPONSE ----------------
      const msg = await simulateTyping(result.message);

      setMessages(prev => [
        ...prev,
        { role: "ai", text: msg }
      ]);

    } catch {

      setMessages(prev => [
        ...prev,
        { role: "ai", text: "Hmm… something went wrong. Try again." }
      ]);

    } finally {
      setLoading(false);
    }

  }, [question, board, subject, chapter]);

  // ---------------- ENTER SEND ----------------
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askQuestion();
    }
  };

  // ---------------- VALIDATION ----------------
  const isValidEmail = (email) =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const isValidPhone = (phone) =>
    /^[6-9]\d{9}$/.test(phone);

  // ---------------- SUBMIT LEAD ----------------
  const submitLead = async () => {

    if (!name || !isValidEmail(email) || !isValidPhone(phone)) {
      alert("Enter valid details");
      return;
    }

    try {

      await axios.post(`${API_BASE}/capture-lead`, {
        session_id: getSessionId(),
        name,
        email,
        phone
      });

      setLeadSubmitted(true);
      setShowLeadForm(false);

    } catch {
      alert("Failed to submit");
    }
  };

  return (
    <div style={{ padding: 30, maxWidth: 800, margin: "auto" }}>

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
              padding: 12,
              background: m.role === "user" ? "#DCF8C6" : "#f1f1f1",
              borderRadius: 12,
              maxWidth: "75%"
            }}>
              <ReactMarkdown>{m.text}</ReactMarkdown>
            </div>
          </div>
        ))}

        <div ref={chatEndRef} />
      </div>

      {loading && <p>Thinking…</p>}

      {/* INPUT */}

      <textarea
        placeholder="Ask your question clearly... (Enter to send)"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={3}
        style={{ width: "100%", marginTop: 20 }}
      />

      <button onClick={askQuestion}>Ask</button>

      {/* ESCALATION */}

      {showEscalation && !showLeadForm && (
        <div style={{
          marginTop: 20,
          padding: 20,
          border: "2px solid #ffa500",
          borderRadius: 10
        }}>
          <h3>Want help from a real teacher?</h3>
          <p>This topic can be easier with personal guidance.</p>
          <button onClick={() => setShowLeadForm(true)}>
            Talk to a Teacher
          </button>
        </div>
      )}

      {/* LEAD FORM */}

      {showLeadForm && !leadSubmitted && (
        <div style={{ marginTop: 20 }}>
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input placeholder="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <button onClick={submitLead}>Submit</button>
        </div>
      )}

      {/* SUCCESS */}

      {leadSubmitted && (
        <div style={{ marginTop: 20 }}>
          <h3>✅ A teacher will contact you soon</h3>
          <p>You can continue learning meanwhile.</p>
        </div>
      )}

    </div>
  );
}

export default App;