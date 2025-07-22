// src/App.jsx
import React, { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import "./App.css";

const BACKEND_URL = "http://localhost:8000"; // Update this if needed

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
    setMessages((prev) => [...prev, { role: "user", content: input }]);
    setInput("");
    setLoading(true);

    const response = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_id: userId.current,
        thread_id: threadId.current,
        message: input,
      }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let aiMessage = "";

    const readChunk = async () => {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });

        const lines = chunk.split("\n").filter((line) => line.startsWith("data:"));
        for (let line of lines) {
          const content = line.replace("data:", "").trim();
          if (content === "[DONE]") {
            setLoading(false);

            // Replace "assistant-temp" with final assistant message
            setMessages((prev) => [
              ...prev.filter((msg) => msg.role !== "assistant-temp"),
              { role: "assistant", content: aiMessage.trim() },
            ]);

            return;
          }

          // Add a space if necessary (basic heuristic)
          const needsSpace =
            aiMessage.length > 0 &&
            !aiMessage.endsWith(" ") &&
            !content.startsWith(" ") &&
            !content.startsWith(".") &&
            !content.startsWith(",") &&
            !content.startsWith("!") &&
            !content.startsWith("?") &&
            !content.startsWith("'") &&
            !content.startsWith('"') &&
            !content.startsWith("\n");

          aiMessage += needsSpace ? ` ${content}` : content;

          // Update temporary assistant message
          setMessages((prev) => [
            ...prev.filter((msg) => msg.role !== "assistant-temp"),
            { role: "assistant-temp", content: aiMessage },
          ]);
        }
      }
      setLoading(false);
    };



    readChunk();
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
              <span>{msg.content}</span>
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
