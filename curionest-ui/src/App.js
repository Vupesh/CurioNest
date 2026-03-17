import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

// Environment variables with validation
const API_BASE = process.env.REACT_APP_API_BASE || "http://127.0.0.1:5000";

/* -----------------------------
Session Management
----------------------------- */
const getSessionId = () => {
  try {
    let id = localStorage.getItem("curionest_session");
    
    if (!id) {
      id = `sess_${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`;
      localStorage.setItem("curionest_session", id);
    }
    
    return id;
  } catch (error) {
    console.error("Session storage error:", error);
    return `sess_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
  }
};

/* =============================
MAIN APP
============================= */
function App() {
  // State management
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState(null);
  
  const [board, setBoard] = useState("");
  const [subject, setSubject] = useState("");
  const [chapter, setChapter] = useState("");
  
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState(null);
  
  const [showEscalation, setShowEscalation] = useState(false);
  const [escalationMessage, setEscalationMessage] = useState("");
  
  const [showLeadForm, setShowLeadForm] = useState(false);
  const [leadSubmitted, setLeadSubmitted] = useState(false);
  const [leadError, setLeadError] = useState(null);
  
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [formErrors, setFormErrors] = useState({});
  
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  /* -----------------------------
  Auto Scroll & Focus Management
  ----------------------------- */
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
  
  const subjects = board && config?.education?.[board] 
    ? Object.keys(config.education[board]) 
    : [];
  
  const chapters = board && subject && config?.education?.[board]?.[subject]
    ? config.education[board][subject] 
    : [];

  /* -----------------------------
  Load Domain Config
  ----------------------------- */
  useEffect(() => {
    let mounted = true;
    
    const loadConfig = async () => {
      try {
        setConfigError(null);
        const res = await axios.get(`${API_BASE}/domain-config`, {
          timeout: 10000, // 10 second timeout
        });
        
        if (!mounted) return;
        
        const cfg = res.data;
        setConfig(cfg);
        
        // Set default selections
        const firstBoard = Object.keys(cfg.education)[0];
        if (firstBoard) {
          const firstSubject = Object.keys(cfg.education[firstBoard])[0];
          const firstChapter = cfg.education[firstBoard][firstSubject]?.[0] || "";
          
          setBoard(firstBoard);
          setSubject(firstSubject);
          setChapter(firstChapter);
        }
      } catch (err) {
        if (!mounted) return;
        console.error("Domain config failed:", err);
        setConfigError("Failed to load configuration. Please refresh the page.");
      }
    };
    
    loadConfig();
    
    return () => {
      mounted = false;
    };
  }, []);

  /* -----------------------------
  Event Handlers
  ----------------------------- */
  const handleBoardChange = useCallback((e) => {
    const newBoard = e.target.value;
    setBoard(newBoard);
    
    if (config?.education?.[newBoard]) {
      const newSubjects = Object.keys(config.education[newBoard]);
      if (newSubjects.length > 0) {
        const firstSubject = newSubjects[0];
        setSubject(firstSubject);
        
        const firstChapter = config.education[newBoard][firstSubject]?.[0] || "";
        setChapter(firstChapter);
      }
    }
  }, [config]);

  const handleSubjectChange = useCallback((e) => {
    const newSubject = e.target.value;
    setSubject(newSubject);
    
    if (config?.education?.[board]?.[newSubject]) {
      const firstChapter = config.education[board][newSubject]?.[0] || "";
      setChapter(firstChapter);
    }
  }, [config, board]);

  const handleChapterChange = useCallback((e) => {
    setChapter(e.target.value);
  }, []);

  const validateEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const validatePhone = (phone) => /^[0-9]{10}$/.test(phone.replace(/\D/g, ''));

  const validateForm = () => {
    const errors = {};
    if (!name.trim()) errors.name = "Name is required";
    if (!email.trim()) errors.email = "Email is required";
    else if (!validateEmail(email)) errors.email = "Invalid email format";
    if (!phone.trim()) errors.phone = "Phone is required";
    else if (!validatePhone(phone)) errors.phone = "Invalid phone number (10 digits required)";
    
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  /* -----------------------------
  API Calls
  ----------------------------- */
  const askQuestion = useCallback(async () => {
    if (!question.trim()) return;
    
    const trimmedQuestion = question.trim();
    setApiError(null);
    
    // Add user message
    setMessages(prev => [...prev, { 
      role: "user", 
      text: trimmedQuestion,
      timestamp: Date.now() 
    }]);
    
    setQuestion("");
    setLoading(true);

    try {
      const res = await axios.post(`${API_BASE}/ask-question`, {
        session_id: getSessionId(),
        board,
        subject,
        chapter,
        question: trimmedQuestion
      }, {
        timeout: 30000, // 30 second timeout
        headers: {
          'Content-Type': 'application/json',
        }
      });

      const result = res?.data;
      
      if (!result) {
        throw new Error("No response from server");
      }

      // Handle different response types
      switch (result.type) {
        case "escalation":
          setMessages(prev => [...prev, { 
            role: "ai", 
            text: result.message || "A teacher can help you with this question.",
            timestamp: Date.now()
          }]);
          setShowEscalation(true);
          setEscalationMessage(result.message || "A teacher can help you with this question.");
          break;
          
        case "answer":
        case "curiosity":
          setMessages(prev => [...prev, { 
            role: "ai", 
            text: result.message || "",
            timestamp: Date.now()
          }]);
          break;
          
        case "error":
          setMessages(prev => [...prev, { 
            role: "ai", 
            text: result.message || "An error occurred. Please try again.",
            timestamp: Date.now()
          }]);
          break;
          
        default:
          console.warn("Unknown response type:", result.type);
      }
    } catch (err) {
      console.error("API error:", err);
      
      let errorMessage = "The system is temporarily unavailable.";
      if (err.code === 'ECONNABORTED') {
        errorMessage = "Request timed out. Please try again.";
      } else if (err.response?.status === 429) {
        errorMessage = "Too many requests. Please wait a moment.";
      } else if (err.response?.status >= 500) {
        errorMessage = "Server error. Please try again later.";
      }
      
      setApiError(errorMessage);
      setMessages(prev => [...prev, { 
        role: "ai", 
        text: errorMessage,
        timestamp: Date.now()
      }]);
    } finally {
      setLoading(false);
    }
  }, [question, board, subject, chapter]);

  const submitLead = useCallback(async () => {
    if (!validateForm()) return;
    
    setLeadError(null);
    
    try {
      await axios.post(`${API_BASE}/capture-lead`, {
        session_id: getSessionId(),
        name: name.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim().replace(/\D/g, '')
      }, {
        timeout: 10000,
      });
      
      setLeadSubmitted(true);
      setShowLeadForm(false);
      
      // Reset form
      setName("");
      setEmail("");
      setPhone("");
      setFormErrors({});
    } catch (err) {
      console.error("Lead capture failed:", err);
      setLeadError("Failed to submit. Please try again.");
    }
  }, [name, email, phone]);

  /* -----------------------------
  Render Helpers
  ----------------------------- */
  const renderSelect = (label, value, options, onChange, disabled = false) => (
    <div style={{ marginBottom: "1rem" }}>
      <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 600 }}>
        {label}
      </label>
      <select
        value={value}
        onChange={onChange}
        disabled={disabled || !options.length}
        style={{
          width: "100%",
          padding: "0.5rem",
          borderRadius: "4px",
          border: "1px solid #ccc",
          backgroundColor: disabled ? "#f5f5f5" : "white",
          cursor: disabled ? "not-allowed" : "pointer"
        }}
      >
        {options.length === 0 ? (
          <option value="">No options available</option>
        ) : (
          options.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))
        )}
      </select>
    </div>
  );

  const renderMessage = (message, index) => (
    <div
      key={index}
      style={{
        display: "flex",
        justifyContent: message.role === "user" ? "flex-end" : "flex-start",
        marginBottom: "1rem",
        animation: "fadeIn 0.3s ease-in"
      }}
    >
      <div
        style={{
          background: message.role === "user" ? "#DCF8C6" : "#f1f1f1",
          padding: "0.75rem 1rem",
          borderRadius: "1rem",
          maxWidth: "70%",
          lineHeight: 1.5,
          wordWrap: "break-word",
          boxShadow: "0 1px 2px rgba(0,0,0,0.1)"
        }}
      >
        <ReactMarkdown
          remarkPlugins={[remarkMath]}
          rehypePlugins={[rehypeKatex]}
          components={{
            p: ({node, ...props}) => <p style={{margin: 0}} {...props} />
          }}
        >
          {message.text}
        </ReactMarkdown>
      </div>
    </div>
  );

  const renderInput = (type, placeholder, value, onChange, error) => (
    <div style={{ marginBottom: "1rem" }}>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        style={{
          width: "100%",
          padding: "0.75rem",
          borderRadius: "4px",
          border: error ? "2px solid #ff4444" : "1px solid #ccc",
          fontSize: "1rem"
        }}
      />
      {error && (
        <small style={{ color: "#ff4444", marginTop: "0.25rem", display: "block" }}>
          {error}
        </small>
      )}
    </div>
  );

  /* -----------------------------
  Main Render
  ----------------------------- */
  if (configError) {
    return (
      <div style={{ padding: "2rem", textAlign: "center", color: "#ff4444" }}>
        <h3>Error</h3>
        <p>{configError}</p>
        <button 
          onClick={() => window.location.reload()}
          style={{
            padding: "0.5rem 1rem",
            background: "#ff4444",
            color: "white",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer"
          }}
        >
          Refresh Page
        </button>
      </div>
    );
  }

  return (
    <div style={{ 
      padding: "2rem", 
      fontFamily: "Arial, sans-serif", 
      maxWidth: "800px", 
      margin: "0 auto" 
    }}>
      <style>
        {`
          @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}
      </style>

      <header style={{ marginBottom: "2rem", textAlign: "center" }}>
        <h1 style={{ color: "#333", marginBottom: "0.5rem" }}>CurioNest</h1>
        <p style={{ color: "#666" }}>Your AI Learning Assistant</p>
      </header>

      {/* Selection Controls */}
      <div style={{ 
        background: "#f9f9f9", 
        padding: "1.5rem", 
        borderRadius: "8px", 
        marginBottom: "2rem" 
      }}>
        {renderSelect("Board", board, boards, handleBoardChange, !config)}
        {renderSelect("Subject", subject, subjects, handleSubjectChange, !board)}
        {renderSelect("Chapter", chapter, chapters, handleChapterChange, !subject)}
      </div>

      {/* Chat Messages */}
      <div style={{ 
        marginBottom: "2rem", 
        maxHeight: "400px", 
        overflowY: "auto", 
        padding: "1rem",
        border: "1px solid #eee",
        borderRadius: "8px"
      }}>
        {messages.length === 0 ? (
          <p style={{ textAlign: "center", color: "#999", padding: "2rem" }}>
            Ask a question to start learning!
          </p>
        ) : (
          messages.map(renderMessage)
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Loading Indicator */}
      {loading && (
        <div style={{ textAlign: "center", marginBottom: "1rem" }}>
          <div style={{
            display: "inline-block",
            width: "20px",
            height: "20px",
            border: "3px solid #f3f3f3",
            borderTop: "3px solid #ff9800",
            borderRadius: "50%",
            animation: "spin 1s linear infinite"
          }} />
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}

      {/* API Error Message */}
      {apiError && (
        <div style={{ 
          marginBottom: "1rem", 
          padding: "0.75rem", 
          background: "#ffebee", 
          color: "#c62828", 
          borderRadius: "4px" 
        }}>
          {apiError}
        </div>
      )}

      {/* Question Input */}
      <div style={{ marginBottom: "1rem" }}>
        <textarea
          ref={inputRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              askQuestion();
            }
          }}
          rows={3}
          style={{
            width: "100%",
            padding: "0.75rem",
            borderRadius: "4px",
            border: "1px solid #ccc",
            fontSize: "1rem",
            resize: "vertical"
          }}
          placeholder="Type your question here... (Press Enter to send, Shift+Enter for new line)"
          disabled={loading}
        />
      </div>

      {/* Action Buttons */}
      <div style={{ display: "flex", gap: "1rem", marginBottom: "2rem" }}>
        <button
          onClick={askQuestion}
          disabled={loading || !question.trim()}
          style={{
            flex: 1,
            padding: "0.75rem",
            background: loading || !question.trim() ? "#ccc" : "#ff9800",
            color: "white",
            border: "none",
            borderRadius: "4px",
            fontSize: "1rem",
            cursor: loading || !question.trim() ? "not-allowed" : "pointer",
            transition: "background 0.3s"
          }}
        >
          {loading ? "Processing..." : "Ask Question"}
        </button>

        {showEscalation && (
          <button
            onClick={() => setShowLeadForm(true)}
            style={{
              flex: 1,
              padding: "0.75rem",
              background: "#4CAF50",
              color: "white",
              border: "none",
              borderRadius: "4px",
              fontSize: "1rem",
              cursor: "pointer",
              transition: "background 0.3s"
            }}
          >
            Talk to a Teacher
          </button>
        )}
      </div>

      {/* Escalation Card */}
      {showEscalation && !showLeadForm && (
        <div style={{
          marginTop: "1rem",
          padding: "1.5rem",
          border: "2px solid #ff9800",
          background: "#fff3e0",
          borderRadius: "8px",
          animation: "fadeIn 0.3s ease-in"
        }}>
          <h3 style={{ marginBottom: "0.5rem", color: "#333" }}>
            Need Additional Help?
          </h3>
          <p style={{ marginBottom: "1rem", color: "#666" }}>
            {escalationMessage}
          </p>
        </div>
      )}

      {/* Lead Form */}
      {showLeadForm && !leadSubmitted && (
        <div style={{
          marginTop: "1rem",
          padding: "1.5rem",
          background: "white",
          border: "2px solid #ff9800",
          borderRadius: "8px",
          animation: "fadeIn 0.3s ease-in"
        }}>
          <h3 style={{ marginBottom: "1rem", color: "#333" }}>
            Connect with a Teacher
          </h3>
          
          {leadError && (
            <div style={{
              marginBottom: "1rem",
              padding: "0.75rem",
              background: "#ffebee",
              color: "#c62828",
              borderRadius: "4px"
            }}>
              {leadError}
            </div>
          )}

          {renderInput("text", "Your Name", name, (e) => setName(e.target.value), formErrors.name)}
          {renderInput("email", "Email Address", email, (e) => setEmail(e.target.value), formErrors.email)}
          {renderInput("tel", "Phone Number", phone, (e) => setPhone(e.target.value), formErrors.phone)}

          <div style={{ display: "flex", gap: "1rem" }}>
            <button
              onClick={submitLead}
              style={{
                flex: 1,
                padding: "0.75rem",
                background: "#4CAF50",
                color: "white",
                border: "none",
                borderRadius: "4px",
                fontSize: "1rem",
                cursor: "pointer"
              }}
            >
              Submit
            </button>
            <button
              onClick={() => {
                setShowLeadForm(false);
                setName("");
                setEmail("");
                setPhone("");
                setFormErrors({});
                setLeadError(null);
              }}
              style={{
                flex: 1,
                padding: "0.75rem",
                background: "#f44336",
                color: "white",
                border: "none",
                borderRadius: "4px",
                fontSize: "1rem",
                cursor: "pointer"
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Success Message */}
      {leadSubmitted && (
        <div style={{
          marginTop: "1rem",
          padding: "1.5rem",
          background: "#e8f5e8",
          color: "#2e7d32",
          borderRadius: "8px",
          textAlign: "center",
          animation: "fadeIn 0.3s ease-in"
        }}>
          ✅ Thank you! A teacher will contact you within 24 hours.
        </div>
      )}
    </div>
  );
}

export default App;