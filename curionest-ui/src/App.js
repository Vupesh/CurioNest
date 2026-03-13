import React, { useState, useEffect } from "react";
import axios from "axios";

const API_BASE =
  process.env.REACT_APP_API_BASE || "http://127.0.0.1:5000";

function getSessionId() {

  let id = localStorage.getItem("curionest_session");

  if (!id) {

    id = "sess_" + Math.random().toString(36).substring(2, 10);
    localStorage.setItem("curionest_session", id);

  }

  return id;
}

function App() {

  const [config, setConfig] = useState(null);

  const [board, setBoard] = useState("");
  const [subject, setSubject] = useState("");
  const [chapter, setChapter] = useState("");

  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState("");

  const [loading, setLoading] = useState(false);


  /* --------------------------------
     Derived dropdown values
  -------------------------------- */

  const boards = config ? Object.keys(config.education || {}) : [];

  const subjects =
    board && config
      ? Object.keys(config.education[board] || {})
      : [];

  const chapters =
    board && subject && config
      ? config.education[board][subject] || []
      : [];


  /* --------------------------------
     Load domain configuration
  -------------------------------- */

  useEffect(() => {

    async function loadConfig() {

      try {

        const res = await axios.get(
          `${API_BASE}/domain-config`
        );

        const cfg = res.data;

        setConfig(cfg);

        const firstBoard = Object.keys(cfg.education)[0];
        const firstSubject =
          Object.keys(cfg.education[firstBoard])[0];

        const firstChapter =
          cfg.education[firstBoard][firstSubject][0];

        setBoard(firstBoard);
        setSubject(firstSubject);
        setChapter(firstChapter);

      } catch (err) {

        console.error("Domain config failed", err);
        setResponse(
          "System initialization failed. Please refresh."
        );

      }

    }

    loadConfig();

  }, []);


  /* --------------------------------
     Board change
  -------------------------------- */

  function handleBoardChange(e) {

    const newBoard = e.target.value;

    setBoard(newBoard);

    const newSubjects =
      Object.keys(config.education[newBoard]);

    const firstSubject = newSubjects[0];

    setSubject(firstSubject);

    const firstChapter =
      config.education[newBoard][firstSubject][0];

    setChapter(firstChapter);

  }


  /* --------------------------------
     Subject change
  -------------------------------- */

  function handleSubjectChange(e) {

    const newSubject = e.target.value;

    setSubject(newSubject);

    const firstChapter =
      config.education[board][newSubject][0];

    setChapter(firstChapter);

  }


  /* --------------------------------
     Chapter change
  -------------------------------- */

  function handleChapterChange(e) {

    setChapter(e.target.value);

  }


  /* --------------------------------
     Ask question
  -------------------------------- */

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

    try {

      const res = await axios.post(
        `${API_BASE}/ask-question`,
        {
          session_id: getSessionId(),
          domain: "education",
          board,
          subject,
          chapter,
          question
        }
      );

      setResponse(res.data.result);

    } catch (err) {

      console.error("API error:", err);

      setResponse(
        "The system is temporarily unavailable."
      );

    }

    setLoading(false);

  }


  /* --------------------------------
     UI
  -------------------------------- */

  return (

    <div style={{ padding: 40, fontFamily: "Arial", maxWidth: 700 }}>

      <h2>CurioNest</h2>


      {/* BOARD */}

      <label><b>Board</b></label><br />

      <select value={board} onChange={handleBoardChange}>

        {boards.map((b) => (

          <option key={b} value={b}>{b}</option>

        ))}

      </select>


      <br /><br />


      {/* SUBJECT */}

      <label><b>Subject</b></label><br />

      <select value={subject} onChange={handleSubjectChange}>

        {subjects.map((s) => (

          <option key={s} value={s}>{s}</option>

        ))}

      </select>


      <br /><br />


      {/* CHAPTER */}

      <label><b>Chapter</b></label><br />

      <select value={chapter} onChange={handleChapterChange}>

        {chapters.map((c) => (

          <option key={c} value={c}>{c}</option>

        ))}

      </select>


      <br /><br />


      {/* QUESTION INPUT */}

      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={3}
        style={{ width: "100%" }}
        placeholder="Ask your question..."
      />


      <br /><br />


      {/* ASK BUTTON */}

      <button onClick={askQuestion} disabled={loading}>

        {loading ? "Processing..." : "Ask"}

      </button>


      {/* RESPONSE */}

      <div style={{ padding: 14, border: "1px solid #ccc", marginTop: 20 }}>

        {response}

      </div>

    </div>

  );

}

export default App;