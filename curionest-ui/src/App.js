import React, { useState, useEffect } from "react";
import axios from "axios";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import "katex/dist/katex.min.css";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:5000";


/* -----------------------------
Session Management
----------------------------- */

function getSessionId() {

  let id = localStorage.getItem("curionest_session");

  if (!id) {
    id = "sess_" + Math.random().toString(36).substring(2, 10);
    localStorage.setItem("curionest_session", id);
  }

  return id;
}


/* =============================
MAIN APP
============================= */

function App() {

  const [config, setConfig] = useState(null);

  const [board, setBoard] = useState("");
  const [subject, setSubject] = useState("");
  const [chapter, setChapter] = useState("");

  const [question, setQuestion] = useState("");

  const [messages, setMessages] = useState([]);

  const [loading, setLoading] = useState(false);

  const [showEscalation, setShowEscalation] = useState(false);
  const [escalationMessage, setEscalationMessage] = useState("");


  /* -----------------------------
  Dropdown values
  ----------------------------- */

  const boards = config ? Object.keys(config.education || {}) : [];

  const subjects =
    board && config
      ? Object.keys(config.education[board] || {})
      : [];

  const chapters =
    board && subject && config
      ? config.education[board][subject] || []
      : [];


  /* -----------------------------
  Load Domain Config
  ----------------------------- */

  useEffect(() => {

    async function loadConfig() {

      try {

        const res = await axios.get(`${API_BASE}/domain-config`);

        const cfg = res.data;

        setConfig(cfg);

        const firstBoard = Object.keys(cfg.education)[0];
        const firstSubject = Object.keys(cfg.education[firstBoard])[0];
        const firstChapter = cfg.education[firstBoard][firstSubject][0];

        setBoard(firstBoard);
        setSubject(firstSubject);
        setChapter(firstChapter);

      } catch (err) {

        console.error("Domain config failed", err);

      }

    }

    loadConfig();

  }, []);


  /* -----------------------------
  Board Change
  ----------------------------- */

  function handleBoardChange(e) {

    const newBoard = e.target.value;

    setBoard(newBoard);

    const newSubjects = Object.keys(config.education[newBoard]);

    const firstSubject = newSubjects[0];

    setSubject(firstSubject);

    const firstChapter = config.education[newBoard][firstSubject][0];

    setChapter(firstChapter);

  }


  /* -----------------------------
  Subject Change
  ----------------------------- */

  function handleSubjectChange(e) {

    const newSubject = e.target.value;

    setSubject(newSubject);

    const firstChapter = config.education[board][newSubject][0];

    setChapter(firstChapter);

  }


  /* -----------------------------
  Chapter Change
  ----------------------------- */

  function handleChapterChange(e) {

    setChapter(e.target.value);

  }


  /* -----------------------------
  Ask Question
  ----------------------------- */

  async function askQuestion() {

    if (!question.trim()) return;

    const userMessage = question;

    setMessages(prev => [
      ...prev,
      { role: "user", text: userMessage }
    ]);

    setQuestion("");
    setLoading(true);

    try {

      const res = await axios.post(`${API_BASE}/ask-question`, {

        session_id: getSessionId(),
        board,
        subject,
        chapter,
        question: userMessage

      });

      const result = res?.data;

      if (!result) return;

      if (result.type === "escalation") {

        setMessages(prev => [
          ...prev,
          { role: "ai", text: result.message }
        ]);

        setShowEscalation(true);
        setEscalationMessage(result.message || "A teacher can help you.");
        return;

      }

      if (result.type === "answer" || result.type === "curiosity") {

        setMessages(prev => [
          ...prev,
          { role: "ai", text: result.message || "" }
        ]);

        return;

      }

      if (result.type === "error") {

        setMessages(prev => [
          ...prev,
          { role: "ai", text: result.message }
        ]);

        return;

      }

    } catch (err) {

      console.error("API error:", err);

      setMessages(prev => [
        ...prev,
        { role: "ai", text: "The system is temporarily unavailable." }
      ]);

    } finally {

      setLoading(false);

    }

  }


  /* -----------------------------
  UI
  ----------------------------- */

  return (

    <div style={{ padding: 40, fontFamily: "Arial", maxWidth: 700 }}>

      <h2>CurioNest</h2>


      <label><b>Board</b></label><br />

      <select value={board} onChange={handleBoardChange}>
        {boards.map((b) => (
          <option key={b} value={b}>{b}</option>
        ))}
      </select>

      <br /><br />


      <label><b>Subject</b></label><br />

      <select value={subject} onChange={handleSubjectChange}>
        {subjects.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>

      <br /><br />


      <label><b>Chapter</b></label><br />

      <select value={chapter} onChange={handleChapterChange}>
        {chapters.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>

      <br /><br />


      {/* Chat Messages */}

      <div style={{marginBottom:20}}>

        {messages.map((m, i) => (

          <div
            key={i}
            style={{
              display:"flex",
              justifyContent: m.role === "user" ? "flex-end" : "flex-start",
              marginBottom:10
            }}
          >

            <div
              style={{
                background: m.role === "user" ? "#DCF8C6" : "#f1f1f1",
                padding:"10px 14px",
                borderRadius:10,
                maxWidth:"70%",
                lineHeight:"1.7"
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

      </div>


      {loading && <p>Thinking...</p>}


      {/* Ask Question */}

      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={3}
        style={{ width: "100%", padding: 10 }}
        placeholder="Ask your question..."
      />

      <br /><br />

      <button onClick={askQuestion} disabled={loading}>
        {loading ? "Processing..." : "Ask"}
      </button>


      {/* ESCALATION CARD */}

      {showEscalation && (

        <div
          style={{
            marginTop: 20,
            padding: 20,
            border: "2px solid #ff9800",
            background: "#fff3e0",
            borderRadius: 6
          }}
        >

          <h3>Need help from a teacher?</h3>

          <p>{escalationMessage}</p>

          <button
            style={{
              padding: "10px 16px",
              background: "#ff9800",
              border: "none",
              color: "white",
              cursor: "pointer",
              borderRadius: 4
            }}
          >
            Request Expert Help
          </button>

        </div>

      )}

    </div>

  );

}

export default App;