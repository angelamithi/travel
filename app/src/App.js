// src/App.jsx
import React, { useEffect, useRef, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import "./App.css";
import { marked } from "marked";

const BACKEND_URL = "http://localhost:8000"; // Update this if needed

function formatMessage(rawText) {
  // Remove bold markdown markers
  let formattedText = rawText.replace(/\*\*/g, '');

  // --- Parse HTML so we can clean up images and links ---
  const parser = new DOMParser();
  const doc = parser.parseFromString(marked.parse(formattedText), "text/html");

  // ✅ Replace long links with "View more details"
  doc.querySelectorAll("a").forEach(a => {
    a.textContent = "View more details";
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
  });

  // ✅ Keep images as actual <img> and style them
  doc.querySelectorAll("img").forEach(img => {
    img.style.maxWidth = "100%";
    img.style.borderRadius = "8px";
    img.style.margin = "8px 0";
  });

  // Return cleaned HTML string
  return doc.body.innerHTML;
}


// Function to parse HTML and extract option cards
function parseOptionsFromHTML(htmlContent) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(htmlContent, 'text/html');

  const options = [];
  const headings = doc.querySelectorAll('h3, h2');

  headings.forEach((heading, index) => {
    const headingText = heading.textContent;
    let content = '';
    let currentElement = heading.nextElementSibling;

    while (currentElement && !['H1', 'H2', 'H3'].includes(currentElement.tagName)) {
      content += currentElement.outerHTML;
      currentElement = currentElement.nextElementSibling;
    }

    const combinedText = (headingText + " " + content).toLowerCase();

    // ✅ Match if heading OR content indicates a relevant option
    if (
      headingText.toLowerCase().includes('option') ||
      headingText.toLowerCase().includes('flight') ||
      headingText.toLowerCase().includes('hotel') ||
      headingText.includes('✈️') ||
      headingText.includes('🏨') ||
      combinedText.includes('vacation rental') // <— Added this check
    ) {
      options.push({
        id: `option-${index}`,
        title: headingText,
        content: content,
        fullHTML: heading.outerHTML + content
      });
    }
  });

  return options;
}


const App = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentAssistantMessage, setCurrentAssistantMessage] = useState("");
  const chatEndRef = useRef(null);

  const userId = useRef(localStorage.getItem("user_id") || uuidv4());
  const threadId = useRef(localStorage.getItem("thread_id") || "default");

  const [typingText, setTypingText] = useState("");
  const fullTypingText = "Tara is typing...";

  useEffect(() => {
    if (loading) {
      setTypingText("");
      let i = 0;
      const interval = setInterval(() => {
        setTypingText(fullTypingText.slice(0, i + 1));
        i++;
        if (i > fullTypingText.length) {
          i = 0; // restart typing
        }
      }, 100); // typing speed
      return () => clearInterval(interval);
    } else {
      setTypingText("");
    }
  }, [loading]);

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

    setMessages(prev => [...prev, { role: "user", content: input }]);
    const userInput = input;
    setInput("");
    setLoading(true);
    setCurrentAssistantMessage("");

    try {
      const response = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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
        let parts = buffer.split("\n\n");
        buffer = parts.pop();

        for (let part of parts) {
          if (part.startsWith("data: ")) {
            const data = part.replace(/^data: /, "");
            try {
              const parsed = JSON.parse(data);
              
              if (parsed.type === "text") {
                // Regular text chunk
                assistantMessage += parsed.content;
                setCurrentAssistantMessage(formatMessage(assistantMessage));
                
                // Natural typing delay for streaming effect
                const delay = Math.min(200, parsed.content.length * 15);
                await new Promise(res => setTimeout(res, delay));
              } else if (parsed.type === "final") {
                // Final message - we already have this content in assistantMessage
                // No need to do anything special here
              }
            } catch (e) {
              // Fallback for non-JSON messages (shouldn't happen with our new backend)
              assistantMessage += data;
              setCurrentAssistantMessage(formatMessage(assistantMessage));
            }
          }
        }
      }

      // Push final formatted message
      setMessages(prevMessages => [
        ...prevMessages,
        { role: "assistant", content: formatMessage(assistantMessage) }
      ]);

      setCurrentAssistantMessage("");

    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentAssistantMessage]);

  const getAvatar = (role) => (role === "user" ? "🧑" : "🌍");

  // Component to render assistant messages with option cards
 const AssistantMessage = ({ content }) => {
  const parser = new DOMParser();
  const doc = parser.parseFromString(content, "text/html");

  // ✅ Replace all anchor text with "View more details"
  doc.querySelectorAll("a").forEach(a => {
    a.textContent = "View more details";
    a.setAttribute("target", "_blank"); // open in new tab
    a.setAttribute("rel", "noopener noreferrer");
  });

  // ✅ Leave <img> tags alone so they display normally
  // If you want to resize or style, do it here
  doc.querySelectorAll("img").forEach(img => {
    img.style.maxWidth = "100%";
    img.style.borderRadius = "8px";
    img.style.margin = "8px 0";
  });

  const processedHTML = doc.body.innerHTML;

  const options = parseOptionsFromHTML(processedHTML);

  if (options.length > 0) {
    const firstOptionHeading = doc.querySelector("h3, h2");
    let introContent = "";
    if (firstOptionHeading) {
      let currentElement = doc.body.firstElementChild;
      while (currentElement && currentElement !== firstOptionHeading) {
        introContent += currentElement.outerHTML;
        currentElement = currentElement.nextElementSibling;
      }
    }

    return (
      <div className="message-content">
        {introContent && (
          <div dangerouslySetInnerHTML={{ __html: introContent }} />
        )}
        <div className="options-container">
          {options.map((option) => (
            <div key={option.id} className="option-card">
              <h3 dangerouslySetInnerHTML={{ __html: option.title }} />
              <div dangerouslySetInnerHTML={{ __html: option.content }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      dangerouslySetInnerHTML={{ __html: processedHTML }}
      className="message-content"
    />
  );
};


  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>Tara</h2>
          <p>Your Ultimate Travel Partner</p>
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
              {msg.role === "assistant" ? (
                <AssistantMessage content={msg.content} />
              ) : (
                <div 
                  dangerouslySetInnerHTML={{ __html: msg.content }}
                  className="message-content"
                />
              )}
            </div>
          ))}
          
          {currentAssistantMessage && (
            <div className="message assistant">
              <span className="avatar">🌍</span>
              <AssistantMessage content={currentAssistantMessage} />
            </div>
          )}

          {loading && (
            <div className="typing-indicator">
              <span className="avatar">🌍</span>
              <span className="typing-text">{typingText}</span>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        <div className="input-container">
          <div className="input-bar">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && !loading && !e.shiftKey && sendMessage()}
              placeholder="Where would you like to go today? Ask about flights, hotels, or destinations..."
              disabled={loading}
              rows={3}
            />
            <button onClick={sendMessage} disabled={loading || !input.trim()}>
              {loading ? "✈️ Sending..." : "✈️ Send"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;