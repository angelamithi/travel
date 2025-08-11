// src/App.jsx
import React, { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import "./App.css";

const BACKEND_URL = "http://localhost:8000"; // Update this if needed

function formatMessage(content) {
  if (!content) return "";

  if (/<[a-z][\s\S]*>/i.test(content)) {
    return content;
  }

  const escapeHtml = (str) =>
    str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  let escaped = escapeHtml(content);

  // --- STEP 1: Insert line breaks before each flight option ---
  escaped = escaped.replace(/(###\s*✈️\s*Option\s*\d+:)/g, "\n$1\n");

  // --- STEP 2: Insert breaks before each bolded field ---
  escaped = escaped.replace(/(\*\*🛫 Departure:|\*\*🛬 Arrival:|\*\*⏱️ Duration:|\*\*🛋️ Cabin:|💰)/g, "\n$1");

  // --- STEP 3: Split flight options into blocks ---
  if (/###\s*✈️\s*Option\s*\d+:/i.test(escaped)) {
    const parts = escaped.trim().split(/\n(?=###\s*✈️\s*Option\s*\d+:)/);

    return parts
      .map((part) => {
        const lines = part.trim().split("\n").filter(Boolean);
        const title = lines.shift() || "";
        const details = lines
          .map((line) =>
            `<li>${line.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")}</li>`
          )
          .join("");

        return `
          <div class="flight-option">
            <h3>${title.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")}</h3>
            <ul>${details}</ul>
          </div>
        `;
      })
      .join("");
  }

  // Default formatting if not flight options
  return escaped
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/^- (.*)$/gm, "<li>$1</li>")
    .replace(/\n/g, "<br/>");
}


const App = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentAssistantMessage, setCurrentAssistantMessage] = useState("");
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

    const newMessages = [...messages, { role: "user", content: input }];
    setMessages(newMessages);
    const userInput = input;
    setInput("");
    setLoading(true);
    setCurrentAssistantMessage("");

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

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const reader = response.body.getReader();
const decoder = new TextDecoder();
let assistantMessage = "";
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });

  // Split on double newlines (SSE message delimiter)
  let parts = buffer.split("\n\n");
  buffer = parts.pop(); // keep incomplete chunk

  for (let part of parts) {
    if (part.startsWith("data: ")) {
      const text = part.replace(/^data: /, "");
      assistantMessage += text;
      setCurrentAssistantMessage(assistantMessage); // live update
    }
  }
}

setMessages(prev => [...prev, { role: "assistant", content: assistantMessage }]);
setCurrentAssistantMessage("");

       } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentAssistantMessage]);

  const getAvatar = (role) => (role === "user" ? "🧳" : "🌍");

  return (
    <div className="app">
     
<aside className="sidebar">
  <div className="sidebar-header">
    <h2>Tara</h2>
    <p>Your Travel Mate</p>
  </div>
  
  <div className="search-options">

    <ul>
      <li>✈️ Flight bookings</li>
      <li>🏨 Hotel accommodations</li>
      <li>🗺️ Travel itineraries</li>
      <li>🌤️ Weather information</li>
      <li>🍽️ Restaurant recommendations</li>
      <li>🚗 Car rentals</li>
      <li>🎟️ Tour packages</li>
    </ul>
  </div>
  
  <div className="sidebar-buttons-container">
    <button onClick={fetchHistory} className="sidebar-button">
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
  </div>
</aside>
      <main className="chat-container">
        <div className="chat-header">
          <h1>Tara - Your Travel Mate</h1>
          <p className="tagline">"Explore the world with confidence and ease!"</p>
        </div>
        
        <div className="chat-box">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`message ${msg.role === "user" ? "user" : "assistant"}`}
            >
              <span className="avatar">{getAvatar(msg.role)}</span>
              <div 
                dangerouslySetInnerHTML={{ 
                  __html: formatMessage(msg.content) 
                }} 
                style={{ 
                  display: 'inline-block',
                  maxWidth: '100%',
                  overflowX: 'auto'
                }}
              />
            </div>
          ))}
          
          {currentAssistantMessage && (
            <div className="message assistant">
              <span className="avatar">🌍</span>
              <span dangerouslySetInnerHTML={{ __html: formatMessage(currentAssistantMessage) }} />
            </div>
          )}

          {loading && (
            <div className="loading-indicator">
              <div className="loading-spinner"></div>
              <span>Planning your adventure...</span>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        <div className="input-container">
          <div className="input-bar">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && !loading && sendMessage()}
              placeholder="Where would you like to go today? Ask about flights, hotels, or destinations..."
              disabled={loading}
            />
            <button onClick={sendMessage} disabled={loading || !input.trim()}>
              {loading ? "✈️ Planning..." : "✈️ Send"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;