import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:5000";

/* -----------------------------
Session Management
----------------------------- */
const getSessionId = () => {
  try {
    let id = localStorage.getItem("curionest_session");

    if (!id) {
      id =
        "sess_" +
        Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15);

      localStorage.setItem("curionest_session", id);
    }

    return id;
  } catch {
    return `sess_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
  }
};

/* -----------------------------
Lead Validation
----------------------------- */

const validateEmail = (email) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
};

const validatePhone = (phone) => {
  return /^[0-9]{10}$/.test(phone);
};

function App() {

  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState(null);

  const [board, setBoard] = useState("");
  const [subject, setSubject] = useState("");
  const [chapter, setChapter] = useState("");

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);

  const [loading, setLoading] = useState(false);

  const [showEscalation, setShowEscalation] = useState(false);
  const [escalationMessage, setEscalationMessage] = useState("");

  const [showLeadForm, setShowLeadForm] = useState(false);
  const [leadSubmitted, setLeadSubmitted] = useState(false);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  /* -----------------------------
  Auto Scroll
  ----------------------------- */
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!loading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [loading]);

  /* -----------------------------
  Derived State
  ----------------------------- */

  const boards = config ? Object.keys(config.education || {}) : [];

  const subjects =
    board && config?.education?.[board]
      ? Object.keys(config.education[board])
      : [];

  const chapters =
    board && subject && config?.education?.[board]?.[subject]
      ? config.education[board][subject]
      : [];

  /* -----------------------------
  Load Domain Config
  ----------------------------- */

  useEffect(() => {

    let mounted = true;

    const loadConfig = async () => {

      try {

        const res = await axios.get(`${API_BASE}/domain-config`);

        if (!mounted) return;

        const cfg = res.data;

        setConfig(cfg);

        const firstBoard = Object.keys(cfg.education)[0];

        if (firstBoard) {

          const firstSubject = Object.keys(cfg.education[firstBoard])[0];

          const firstChapter =
            cfg.education[firstBoard][firstSubject]?.[0] || "";

          setBoard(firstBoard);
          setSubject(firstSubject);
          setChapter(firstChapter);

        }

      } catch (err) {

        console.error("Domain config error", err);
        setConfigError("Failed to load configuration.");

      }

    };

    loadConfig();

    return () => { mounted = false };

  }, []);

  /* -----------------------------
  Dropdown Handlers
  ----------------------------- */

  const handleBoardChange = (e) => {

    const newBoard = e.target.value;

    setBoard(newBoard);

    const newSubjects = Object.keys(config.education[newBoard]);

    const firstSubject = newSubjects[0];

    setSubject(firstSubject);

    const firstChapter =
      config.education[newBoard][firstSubject]?.[0] || "";

    setChapter(firstChapter);

  };

  const handleSubjectChange = (e) => {

    const newSubject = e.target.value;

    setSubject(newSubject);

    const firstChapter =
      config.education[board][newSubject]?.[0] || "";

    setChapter(firstChapter);

  };

  const handleChapterChange = (e) => {
    setChapter(e.target.value);
  };

  /* -----------------------------
  Ask Question
  ----------------------------- */

  const askQuestion = useCallback(async () => {

    if (!question.trim() || loading) return;

    const trimmedQuestion = question.trim();

    setShowEscalation(false);

    setMessages(prev => [
      ...prev,
      { role: "user", text: trimmedQuestion }
    ]);

    setQuestion("");
    setLoading(true);

    try {

      const res = await axios.post(`${API_BASE}/ask-question`, {

        session_id: getSessionId(),
        board,
        subject,
        chapter,
        question: trimmedQuestion

      });

      const result = res.data;

      if (result.type === "escalation") {

        setMessages(prev => [
          ...prev,
          { role: "ai", text: result.message }
        ]);

        setShowEscalation(true);
        setEscalationMessage(result.message);

        return;

      }

      if (result.type === "answer" || result.type === "curiosity") {

        setMessages(prev => [
          ...prev,
          { role: "ai", text: result.message }
        ]);

      }

    } catch (err) {

      console.error("API error", err);

      setMessages(prev => [
        ...prev,
        { role: "ai", text: "⚠️ System temporarily unavailable. Please try again." }
      ]);

    } finally {

      setLoading(false);

    }

  }, [question, board, subject, chapter, loading]);

  /* -----------------------------
  Submit Lead
  ----------------------------- */

  const submitLead = async () => {

    const cleanName = name.trim();
    const cleanEmail = email.trim();
    const cleanPhone = phone.trim();

    if (!cleanName) {
      alert("Please enter your name");
      return;
    }

    if (!validateEmail(cleanEmail)) {
      alert("Please enter a valid email");
      return;
    }

    if (!validatePhone(cleanPhone)) {
      alert("Please enter a valid 10 digit mobile number");
      return;
    }

    try {

      await axios.post(`${API_BASE}/capture-lead`, {

        session_id: getSessionId(),
        name: cleanName,
        email: cleanEmail,
        phone: cleanPhone

      });

      setLeadSubmitted(true);
      setShowLeadForm(false);

      setName("");
      setEmail("");
      setPhone("");

    } catch (err) {

      console.error("Lead submit error", err);
      alert("Lead submission failed. Please try again.");

    }

  };

  /* -----------------------------
  UI
  ----------------------------- */

  if (configError) {
    return <div>{configError}</div>;
  }

  return (

    <div style={{ padding: 40, maxWidth: 800, margin: "auto" }}>

      <h2>CurioNest</h2>

      <select value={board} onChange={handleBoardChange}>
        {boards.map(b => <option key={b}>{b}</option>)}
      </select>

      <select value={subject} onChange={handleSubjectChange}>
        {subjects.map(s => <option key={s}>{s}</option>)}
      </select>

      <select value={chapter} onChange={handleChapterChange}>
        {chapters.map(c => <option key={c}>{c}</option>)}
      </select>

      {/* Chat */}

      <div style={{ marginTop: 20 }}>

        {messages.map((m, i) => (

          <div
            key={i}
            style={{
              textAlign: m.role === "user" ? "right" : "left",
              marginBottom: 10
            }}
          >

            <div
              style={{
                display: "inline-block",
                padding: 10,
                background: m.role === "user" ? "#DCF8C6" : "#eee",
                borderRadius: 10,
                maxWidth: "70%"
              }}
            >

              <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
              >
                {m.text}
              </ReactMarkdown>

            </div>

          </div>

        ))}

        <div ref={chatEndRef} />

      </div>

      {loading && <p>Thinking...</p>}

      <textarea
        ref={inputRef}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={3}
        style={{ width: "100%", marginTop: 20 }}
      />

      <button onClick={askQuestion} disabled={loading}>
        Ask
      </button>

      {/* Escalation */}

      {showEscalation && !showLeadForm && (

        <div
          style={{
            marginTop: 20,
            padding: 20,
            border: "2px solid orange",
            background: "#fff3e0"
          }}
        >

          <h3>Need help from a teacher?</h3>

          <p>{escalationMessage}</p>

          <button onClick={() => setShowLeadForm(true)}>
            Talk to a Teacher
          </button>

        </div>

      )}

      {/* Lead Form */}

      {showLeadForm && !leadSubmitted && (

        <div style={{ marginTop: 20 }}>

          <input
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <input
            type="tel"
            placeholder="Mobile Number"
            value={phone}
            onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
            maxLength={10}
          />

          <button onClick={submitLead}>Submit</button>

        </div>

      )}

      {/* Lead Success */}

      {leadSubmitted && (

        <div
          style={{
            marginTop: 20,
            padding: 15,
            background: "#e8f5e9",
            border: "1px solid #4caf50",
            borderRadius: 6
          }}
        >

          <h3>✅ A teacher will contact you within 24 hours</h3>

          <p>
            You can continue chatting while waiting.
          </p>

        </div>

      )}

    </div>

  );

}

export default App;