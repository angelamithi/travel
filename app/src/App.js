import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const App = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light');
  const chatRef = useRef(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const threadId = 'default';
  const userId = localStorage.getItem('user_id') || generateUserId();

  function generateUserId() {
    const newId = 'user_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('user_id', newId);
    return newId;
  }

  // Load messages from localStorage or fetch from backend
  useEffect(() => {
    const saved = localStorage.getItem('tara_chat_history');
    if (saved) {
      setMessages(JSON.parse(saved));
    } else {
      fetch(`http://127.0.0.1:8000/history?user_id=${userId}&thread_id=${threadId}`)
        .then(res => res.json())
        .then(data => {
          if (data.history) {
            setMessages(data.history);
            localStorage.setItem('tara_chat_history', JSON.stringify(data.history));
          }
        })
        .catch(err => console.error('Failed to load chat history:', err));
    }
  }, []);

  // Persist messages to localStorage
  useEffect(() => {
    localStorage.setItem('tara_chat_history', JSON.stringify(messages));
    scrollToBottom();
  }, [messages]);

  // Update theme
  useEffect(() => {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const scrollToBottom = () => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, thread_id: threadId, user_id: userId }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (let line of lines) {
          if (line.startsWith('data:')) {
            const text = line.replace(/^data:\s*/, '');

            // Add space only when appropriate
            if (
              assistantMessage.length > 0 &&
              !/\s$/.test(assistantMessage) &&
              !/^[.,!?;:]/.test(text)
            ) {
              assistantMessage += ' ';
            }

            assistantMessage += text;

            // Update the streaming message
            setMessages(prev => {
              const existing = prev.filter(msg => msg.role !== 'streaming');
              return [...existing, { role: 'streaming', content: assistantMessage }];
            });
          }
        }
      }

      // Finalize the assistant message
      setMessages(prev => {
        const existing = prev.filter(msg => msg.role !== 'streaming');
        return [...existing, { role: 'assistant', content: assistantMessage }];
      });

    } catch (error) {
      console.error('Streaming error:', error);
    } finally {
      setIsTyping(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    localStorage.removeItem('tara_chat_history');
  };

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  return (
    <div className="app-container">
      <button
        className="sidebar-toggle"
        onClick={() => setSidebarOpen(prev => !prev)}
      >
        ☰
      </button>

      <div className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        <div className="emoji-header">🌍</div>
        <h2 style={{ marginTop: '20px', fontSize: '30px' }}>Travel Assistant</h2>

        <div className="instructions">
          <ul>
            <li>🛫 Find flights</li>
            <li>🏨 Book hotels</li>
            <li>🗺️ Discover places</li>
            <li>📅 Plan itineraries</li>
          </ul>
        </div>

        <div className="spacer" />

        <div className="theme-toggle">
          <label>
            <input type="checkbox" checked={theme === 'dark'} onChange={toggleTheme} />
            {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
          </label>
        </div>
      </div>

      <div className="chat-container">
        <div className="chat-header">
          <h1>Tara - Your Travel Mate</h1>
          <p>✈️ Let’s plan the perfect trip together 🌴</p>
        </div>

        <div className="chat-window" ref={chatRef}>
          {messages.map((msg, index) => (
            <div
  key={index}
  className={`chat-message-wrapper ${msg.role}`}
>
  {msg.role === 'assistant' || msg.role === 'streaming' ? (
    <>
      <div className="avatar emoji">🌍</div>

      <div className={`chat-message ${msg.role}`}>
        <div className="chat-bubble">{msg.content}</div>
      </div>
    </>
  ) : (
    <>
      <div
  className={`chat-message ${msg.role}`}
  style={{
    display: 'flex',
    flexDirection: 'row-reverse',
    alignItems: 'center',
    justifyContent: 'flex-end',
    marginRight: '50px', // pushes it away from right edge
    marginLeft: 'auto',  // pushes it to the right side
  }}
>
  
  <div className="chat-bubble">{msg.content}</div>
  <div className="avatar emoji" style={{ marginRight: '15px' }}>🧑</div>
</div>


    </>
  )}
</div>


          ))}
          {isTyping && (
            <div className="chat-message assistant typing">
              Tara is typing<span className="dots">...</span>
            </div>
          )}
        </div>

        <div className="input-area">
          <input
            type="text"
            value={input}
            placeholder="Ask Tara anything about your trip..."
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
          />
          <button onClick={sendMessage}>Send</button>
          <button className="clear-button" onClick={clearChat}>🧹</button>
        </div>
      </div>
    </div>
  );
};

export default App;
