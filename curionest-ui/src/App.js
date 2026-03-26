import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "katex/dist/katex.min.css";
import { BlockMath, InlineMath } from "react-katex";

const API_CANDIDATES = [
  process.env.REACT_APP_API_BASE,
  "",
  `${window.location.protocol}//${window.location.hostname}:5000`,
].filter(Boolean);

const FALLBACK_CONFIG = {
  CBSE: {
    physics: ["light_reflection_refraction", "human_eye", "electricity", "magnetic_effects_of_current"],
    chemistry: ["chemical_reactions_equations", "acid_bases_salts", "metals_non_metals", "carbon_and_its_compounds"],
    biology: ["life_processes", "control_coordinations", "how_do_organisms_reproduce", "heredity"],
  },
  ICSE: {
    physics: ["force", "work_power_energy", "light", "sound", "electricity_magnetism", "modern_physics"],
    chemistry: [
      "periodic_properties",
      "chemical_bonding",
      "acid_bases_salt",
      "analytical_chemistry",
      "mole_concept_stoichiometry",
      "electrolysis",
      "metallurgy",
      "study_of_compounds",
      "organic_chemistry",
    ],
    biology: ["basic_biology", "plant_physiology", "human_anatomy_and_physiology", "population", "human_evolution", "polution"],
  },
};

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
  const [apiBase, setApiBase] = useState(API_CANDIDATES[0] || "");

  const sessionId = "session_1";

  useEffect(() => {
    const loadConfig = async () => {
      for (const base of API_CANDIDATES) {
        try {
          const res = await axios.get(`${base}/domain-config`);
          const education = res?.data?.education;
          if (education && Object.keys(education).length > 0) {
            setApiBase(base);
            setConfig(education);
            return;
          }
        } catch {
          // try the next candidate
        }
      }

      setConfig(FALLBACK_CONFIG);
      setMessages([
        {
          role: "ai",
          text: "I loaded an offline syllabus list. If answers fail, start backend and refresh once.",
        },
      ]);
    };

    loadConfig();
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
      const res = await axios.post(`${apiBase}/ask-question`, {
        session_id: sessionId,
        board,
        subject,
        chapter,
        question: q,
      });

      const data = res.data || {};
      const reminder = (!board || !subject || !chapter)
        ? " (Tip: select Board > Subject > Chapter for exact syllabus guidance.)"
        : "";
      setMessages((prev) => [...prev, { role: "ai", text: `${data.message || "Let me try again."}${reminder}` }]);
      if (data.type === "escalation") setShowEscalation(true);
    } catch {
      const lower = q.toLowerCase().trim();
      let fallback = "I can’t reach the tutor service right now. Please ensure backend is running on port 5000.";

      if (["hi", "hello", "hey"].includes(lower)) {
        fallback = "Hi 👋 Please select Board > Subject > Chapter, then ask your doubt.";
      } else if (!board || !subject || !chapter) {
        fallback = "Please select Board > Subject > Chapter first, then I will explain simply.";
      }

      setMessages((prev) => [...prev, { role: "ai", text: fallback }]);
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
      const res = await axios.post(`${apiBase}/capture-lead`, payload);
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
