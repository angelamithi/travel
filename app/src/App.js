// src/App.jsx
import React, { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import "./App.css";

const BACKEND_URL = "http://localhost:8000"; // Update this if needed

function formatMessage(content) {
  if (!content) return "";

  // Escape HTML first
  const escapeHtml = (str) =>
    str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  const escaped = escapeHtml(content);

  // Basic replacements: bold, newlines, bullets
  return escaped
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>") // bold
    .replace(/^\d+\.\s(.*)$/gm, "<p><strong>$&</strong></p>") // numbered list
    .replace(/^- (.*)$/gm, "<li>$1</li>")                    // unordered list
    .replace(/\n{2,}/g, "<br/><br/>")                        // double line breaks
    .replace(/\n/g, "<br/>");                                // single line breaks
}


const App = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef(null);

  const userId = useRef(localStorage.getItem("user_id") || uuidv4());
  const threadId = useRef(localStorage.getItem("thread_id") || "default");

  useEffect(() => {
    localStorage.setItem("user_id", userId.current);
    localStorage.setItem("thread_id", threadId.current);
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/history?user_id=${userId.current}&thread_id=${threadId.current}`);
      const data = await res.json();
      setMessages(data.history);
    } catch (err) {
      console.error("Failed to load history", err);
    }
  };
const sendMessage = async () => {
  if (!input.trim()) return;

  // Add user message
  setMessages((prev) => [...prev, { role: "user", content: input }]);
  const userInput = input;
  setInput("");
  setLoading(true);

  try {
    const response = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_id: userId.current,
        thread_id: threadId.current,
        message: userInput,
      }),
    });

    const data = await response.json();

    // Add assistant reply
    if (data && data.role === "assistant" && data.content) {
      setMessages((prev) => [...prev, { role: "assistant", content: data.content }]);
    }
  } catch (error) {
    console.error("Failed to send message:", error);
  } finally {
    setLoading(false);
  }
};


  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const getAvatar = (role) => {
    return role === "user" ? "🧑" : "🤖";
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>🧠 FlightBot</h2>
        <button
          onClick={fetchHistory}
          className="sidebar-button"
        >
          🔄 Refresh History
        </button>
        <button
          onClick={async () => {
            await fetch(`${BACKEND_URL}/clear_context?user_id=${userId.current}&thread_id=${threadId.current}`, {
              method: "POST",
            });
            setMessages([]);
          }}
          className="sidebar-button red"
        >
          🧹 Clear Chat
        </button>
      </aside>
      <main className="chat-container">
        <div className="chat-box">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`message ${msg.role === "user" ? "user" : "assistant"}`}
            >
              <span className="avatar">{getAvatar(msg.role)}</span>
              <span
  dangerouslySetInnerHTML={{ __html: formatMessage(msg.content) }}
/>

            </div>
          ))}
          <div ref={chatEndRef} />
        </div>
        <div className="input-bar">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask me about flights..."
          />
          <button onClick={sendMessage} disabled={loading}>
            {loading ? "Loading..." : "Send"}
          </button>
        </div>
      </main>
    </div>
  );
};

export default App;
