// src/App.jsx
import React, { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import "./App.css";

const BACKEND_URL = "http://localhost:8000"; // Update this if needed

function formatMessage(content) {
  if (!content) return "";

  // If content is already HTML (contains tags), return it as-is
  if (/<[a-z][\s\S]*>/i.test(content)) {
    return content;
  }

  // Otherwise, proceed with basic formatting
  const escapeHtml = (str) =>
    str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  const escaped = escapeHtml(content);

  return escaped
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/^\d+\.\s(.*)$/gm, "<p><strong>$&</strong></p>")
    .replace(/^- (.*)$/gm, "<li>$1</li>")
    .replace(/\n{2,}/g, "<br/><br/>")
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

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        assistantMessage += chunk;
        setCurrentAssistantMessage(assistantMessage);
      }

      setMessages(prev => [...prev, { role: "assistant", content: assistantMessage }]);
      setCurrentAssistantMessage("");
    } catch (error) {
      console.error("Failed to send message:", error);
      setMessages(prev => [...prev, { role: "assistant", content: "Sorry, there was an error processing your request." }]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentAssistantMessage]);

  const getAvatar = (role) => (role === "user" ? "🧑" : "🤖");

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>🌍 TravelBot</h2>
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
      </aside>

      <main className="chat-container">
        <div className="chat-box">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`message ${msg.role === "user" ? "user" : "assistant"}`}
            >
              <span className="avatar">{getAvatar(msg.role)}</span>
              <span dangerouslySetInnerHTML={{ __html: formatMessage(msg.content) }} />
            </div>
          ))}

          {currentAssistantMessage && (
            <div className="message assistant">
              <span className="avatar">🤖</span>
              <span dangerouslySetInnerHTML={{ __html: formatMessage(currentAssistantMessage) }} />
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        <div className="input-bar">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && sendMessage()}
            placeholder="Ask me about travel plans: flights, hotels, itineraries..."
            disabled={loading}
          />
          <button onClick={sendMessage} disabled={loading || !input.trim()}>
            {loading ? "Loading..." : "Send"}
          </button>
        </div>
      </main>
    </div>
  );
};

export default App;
