import React, { useState, useEffect } from "react";
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:5000";

function getSessionId() {
  let id = localStorage.getItem("curionest_session");

  if (!id) {
    id = "sess_" + Math.random().toString(36).substring(2, 10);
    localStorage.setItem("curionest_session", id);
  }

  return id;
}

function App() {

  const [config, setConfig] = useState({});
  const [board, setBoard] = useState("");
  const [subject, setSubject] = useState("");
  const [chapter, setChapter] = useState("");

  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);

  const boards = Object.keys(config.education || {});
  const subjects = board ? Object.keys(config.education[board] || {}) : [];
  const chapters = board && subject ? config.education[board][subject] || [] : [];

  useEffect(() => {

    async function loadConfig() {

      try {

        const res = await axios.get(`${API_BASE}/domain-config`);

        setConfig(res.data);

        const firstBoard = Object.keys(res.data.education)[0];
        const firstSubject = Object.keys(res.data.education[firstBoard])[0];
        const firstChapter = res.data.education[firstBoard][firstSubject][0];

        setBoard(firstBoard);
        setSubject(firstSubject);
        setChapter(firstChapter);

      } catch (err) {

        console.error("Failed to load domain config");

      }

    }

    loadConfig();

  }, []);


  async function askQuestion() {

    if (!question.trim()) return;

    setLoading(true);

    try {

      const res = await axios.post(`${API_BASE}/ask-question`, {

        session_id: getSessionId(),
        domain: "education",
        board: board,
        subject: subject,
        chapter: chapter,
        question: question

      });

      setResponse(res.data.result);

    } catch (err) {

      setResponse("Backend not responding");

    }

    setLoading(false);

  }


  return (

    <div style={{ padding: 40, fontFamily: "Arial", maxWidth: 700 }}>

      <h2>CurioNest</h2>

      <label><b>Board</b></label><br />

      <select value={board} onChange={(e) => setBoard(e.target.value)}>

        {boards.map((b) => (

          <option key={b} value={b}>{b}</option>

        ))}

      </select>

      <br /><br />

      <label><b>Subject</b></label><br />

      <select value={subject} onChange={(e) => setSubject(e.target.value)}>

        {subjects.map((s) => (

          <option key={s} value={s}>{s}</option>

        ))}

      </select>

      <br /><br />

      <label><b>Chapter</b></label><br />

      <select value={chapter} onChange={(e) => setChapter(e.target.value)}>

        {chapters.map((c) => (

          <option key={c} value={c}>{c}</option>

        ))}

      </select>

      <br /><br />

      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={3}
        style={{ width: "100%" }}
      />

      <br /><br />

      <button onClick={askQuestion} disabled={loading}>

        {loading ? "Processing..." : "Ask"}

      </button>

      <div style={{ padding: 14, border: "1px solid #ccc", marginTop: 20 }}>

        {response}

      </div>

    </div>

  );

}

export default App;