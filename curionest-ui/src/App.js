import React, { useState, useEffect } from "react";
import axios from "axios";

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

  useEffect(() => {
    axios.get(`${API}/domain-config`)
      .then(res => setConfig(res.data.education || {}))
      .catch(() => alert("Config load failed"));
  }, []);

  const boards = Object.keys(config);
  const subjects = board ? Object.keys(config[board] || {}) : [];
  const chapters = board && subject ? config[board][subject] || [] : [];

  const askQuestion = async () => {

    if (!board || !subject || !chapter) {
      alert("Select Board, Subject, Chapter");
      return;
    }

    if (!question.trim()) return;

    const q = question;

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

      setMessages(prev => [
        ...prev,
        { role: "ai", text: data.message }
      ]);

      if (data.type === "escalation") {
        setShowEscalation(true);
      }

    } catch {
      setMessages(prev => [
        ...prev,
        { role: "ai", text: "System error. Try again." }
      ]);
    }

    setLoading(false);
  };

  const handleEscalation = (choice) => {

    if (choice === "yes") {
      axios.post(`${API}/capture-lead`, {
        session_id: "session_1"
      });
      setMessages(prev => [
        ...prev,
        { role: "ai", text: "Teacher will contact you soon 👍" }
      ]);
    } else {
      setMessages(prev => [
        ...prev,
        { role: "ai", text: "Alright 👍 Let’s continue." }
      ]);
    }

    setShowEscalation(false);
  };

  return (
    <div style={{ padding: 20, maxWidth: 800, margin: "auto" }}>

      <h2>CurioNest</h2>

      <div>
        <select value={board} onChange={e => {
          setBoard(e.target.value);
          setSubject("");
          setChapter("");
        }}>
          <option value="">Board</option>
          {boards.map(b => <option key={b}>{b}</option>)}
        </select>

        <select value={subject} onChange={e => {
          setSubject(e.target.value);
          setChapter("");
        }}>
          <option value="">Subject</option>
          {subjects.map(s => <option key={s}>{s}</option>)}
        </select>

        <select value={chapter} onChange={e => setChapter(e.target.value)}>
          <option value="">Chapter</option>
          {chapters.map(c => <option key={c}>{c}</option>)}
        </select>
      </div>

      <div style={{ marginTop: 20, border: "1px solid #ccc", padding: 10, minHeight: 300 }}>
        {messages.map((m, i) => (
          <p key={i}><b>{m.role === "user" ? "You" : "CurioNest"}:</b> {m.text}</p>
        ))}
        {loading && <p><i>Thinking...</i></p>}
      </div>

      <textarea
  rows="3"
  style={{ width: "100%", marginTop: 10 }}
  value={question}
  onChange={(e) => setQuestion(e.target.value)}
  placeholder="Ask your doubt..."
  onKeyDown={(e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askQuestion();
    }
  }}
/>

      <button onClick={askQuestion}>Ask</button>

      {showEscalation && (
        <div style={{ border: "2px solid orange", padding: 10, marginTop: 10 }}>
          <p>Need help from a teacher?</p>
          <button onClick={() => handleEscalation("yes")}>Yes</button>
          <button onClick={() => handleEscalation("no")}>No</button>
        </div>
      )}

    </div>
  );
}

export default App;