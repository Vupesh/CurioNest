import React, { useState } from "react";
import axios from "axios";

const SUBJECTS = {
  Physics: ["Laws of Motion", "Work Energy Power", "Gravitation"],
  Chemistry: ["Atomic Structure", "Chemical Bonding"],
  Maths: ["Quadratic Equations", "Trigonometry"],
  Biology: ["Cell Structure", "Plant Processes"]
};

function App() {
  const [subject, setSubject] = useState("Physics");
  const [chapter, setChapter] = useState(SUBJECTS["Physics"][0]);
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubjectChange = (value) => {
    setSubject(value);
    setChapter(SUBJECTS[value][0]);
  };

  const askQuestion = async () => {
    if (loading) return; // ✅ Prevent double clicks

    setLoading(true);
    setResponse("Thinking...");

    try {
      const res = await axios.post("http://127.0.0.1:5000/ask-question", {
        question,
        subject,
        chapter
      });

      setResponse(res.data.result);
    } catch (err) {
      if (err.response && err.response.data && err.response.data.error) {
        setResponse(err.response.data.error);
      } else {
        setResponse("Server unreachable");
      }
    }

    setLoading(false);
  };

  return (
    <div style={{ padding: 40, fontFamily: "Arial", maxWidth: 600 }}>
      <h2>CurioNest</h2>

      <label><b>Subject</b></label><br />
      <select
        value={subject}
        onChange={(e) => handleSubjectChange(e.target.value)}
      >
        {Object.keys(SUBJECTS).map((subj) => (
          <option key={subj} value={subj}>{subj}</option>
        ))}
      </select>

      <br /><br />

      <label><b>Chapter</b></label><br />
      <select
        value={chapter}
        onChange={(e) => setChapter(e.target.value)}
      >
        {SUBJECTS[subject].map((chap) => (
          <option key={chap} value={chap}>{chap}</option>
        ))}
      </select>

      <br /><br />

      <label><b>Question</b></label><br />
      <textarea
        placeholder="Enter your question"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={4}
        cols={50}
        style={{ width: "100%" }}
      />

      <br /><br />

      <button
        onClick={askQuestion}
        disabled={loading}
        style={{
          padding: "8px 16px",
          cursor: loading ? "not-allowed" : "pointer"
        }}
      >
        {loading ? "Please wait..." : "Ask"}
      </button>

      <br /><br />

      <div style={{
        padding: 12,
        border: "1px solid #ddd",
        borderRadius: 6,
        minHeight: 60,
        background: "#f9f9f9"
      }}>
        <b>Response</b>
        <div style={{ marginTop: 8 }}>{response}</div>
      </div>
    </div>
  );
}

export default App;