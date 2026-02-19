import React, { useState } from "react";
import axios from "axios";

const SUBJECTS = {
  Physics: [
    "Laws of Motion",
    "Work Energy Power",
    "Gravitation"
  ],
  Biology: [
    "Cell Structure",
    "Plant Processes"
  ],
  Chemistry: [
    "Atomic Structure",
    "Chemical Bonding"
  ]
};

function App() {
  const [subject, setSubject] = useState("Physics");
  const [chapter, setChapter] = useState(SUBJECTS["Physics"][0]);
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState("");

  const handleSubjectChange = (value) => {
    setSubject(value);
    setChapter(SUBJECTS[value][0]); // auto reset chapter
  };

  const askQuestion = async () => {
    try {
      const res = await axios.post("http://127.0.0.1:5000/ask-question", {
        question,
        subject,
        chapter,
      });

      setResponse(res.data.result);
    } catch (err) {
      if (err.response && err.response.data && err.response.data.error) {
        setResponse(err.response.data.error);
      } else {
        setResponse("Server unreachable");
      }
    }
  };

  return (
    <div style={{ padding: 40, fontFamily: "Arial" }}>
      <h2>CurioNest</h2>

      <label>Subject:</label>
      <br />
      <select
        value={subject}
        onChange={(e) => handleSubjectChange(e.target.value)}
      >
        {Object.keys(SUBJECTS).map((subj) => (
          <option key={subj} value={subj}>
            {subj}
          </option>
        ))}
      </select>

      <br /><br />

      <label>Chapter:</label>
      <br />
      <select
        value={chapter}
        onChange={(e) => setChapter(e.target.value)}
      >
        {SUBJECTS[subject].map((chap) => (
          <option key={chap} value={chap}>
            {chap}
          </option>
        ))}
      </select>

      <br /><br />

      <textarea
        placeholder="Enter question"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={4}
        cols={50}
      />

      <br /><br />

      <button onClick={askQuestion}>Ask</button>

      <h3>Response</h3>
      <div>{response}</div>
    </div>
  );
}

export default App;
