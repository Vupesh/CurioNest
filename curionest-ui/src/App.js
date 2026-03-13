import React, { useState, useEffect } from "react";
import axios from "axios";
import "katex/dist/katex.min.css";
import { BlockMath, InlineMath } from "react-katex";

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

/* -----------------------------
Math Renderer (Production Ready)
Supports:
[ ... ]   → block math
( ... )   → inline math
----------------------------- */
function renderMath(text) {
  if (!text) return null;

  const parts = [];
  // Corrected regex: escaped [ for block math, captures block in $1, inline in $2
  const regex = /\[(.*?)\]|\((.*?)\)/g;

  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    // Push preceding plain text
    if (match.index > lastIndex) {
      parts.push(
        <span key={key++}>
          {text.substring(lastIndex, match.index)}
        </span>
      );
    }

    // Block math (captured in match[1])
    if (match[1]) {
      parts.push(
        <BlockMath key={key++} math={match[1]} />
      );
    }
    // Inline math (captured in match[2])
    else if (match[2]) {
      parts.push(
        <InlineMath key={key++} math={match[2]} />
      );
    }

    lastIndex = regex.lastIndex;
  }

  // Push remaining plain text
  if (lastIndex < text.length) {
    parts.push(
      <span key={key++}>
        {text.substring(lastIndex)}
      </span>
    );
  }

  return parts;
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
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);

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
        setResponse("System initialization failed. Please refresh.");
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
    if (!question.trim()) {
      setResponse("Please enter a question.");
      return;
    }

    if (!board || !subject || !chapter) {
      setResponse("Please select board, subject and chapter.");
      return;
    }

    setLoading(true);
    setResponse("");

    try {
      const res = await axios.post(`${API_BASE}/ask-question`, {
        session_id: getSessionId(),
        domain: "education",
        board,
        subject,
        chapter,
        question
      });

      setResponse(res.data.result);
    } catch (err) {
      console.error("API error:", err);
      setResponse("The system is temporarily unavailable.");
    }

    setLoading(false);
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

      <div
        style={{
          padding: 14,
          border: "1px solid #ccc",
          marginTop: 20,
          lineHeight: "1.6"
        }}
      >
        {renderMath(response)}
      </div>
    </div>
  );
}

export default App;