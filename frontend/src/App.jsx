import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Agent metadata mapping for rich visuals, avatars, and custom colors
const AGENT_METADATA = {
  user: { icon: '👤', name: 'You', class: 'author-user' },
  orchestrator: { icon: '👑', name: 'Master Coordinator', class: 'author-orchestrator' },
  Orchestrator_Agent: { icon: '👑', name: 'Master Coordinator', class: 'author-orchestrator' },
  Orchestrator: { icon: '👑', name: 'Master Coordinator', class: 'author-orchestrator' },
  
  route_planner: { icon: '🗺️', name: 'Route Architect', class: 'author-route-planner' },
  Route_Planner: { icon: '🗺️', name: 'Route Architect', class: 'author-route-planner' },
  Route: { icon: '🗺️', name: 'Route Architect', class: 'author-route-planner' },
  
  hotel_agent: { icon: '🏨', name: 'Hotel Agent', class: 'author-hotel' },
  Hotel_Agent: { icon: '🏨', name: 'Hotel Agent', class: 'author-hotel' },
  Hotel: { icon: '🏨', name: 'Hotel Agent', class: 'author-hotel' },
  
  activities_agent: { icon: '🎯', name: 'Activities Guide', class: 'author-activities' },
  Activities_Agent: { icon: '🎯', name: 'Activities Guide', class: 'author-activities' },
  Activities: { icon: '🎯', name: 'Activities Guide', class: 'author-activities' },
  
  unknown: { icon: '🤖', name: 'AI Assistant', class: 'author-orchestrator' }
};

const getAgentInfo = (author) => {
  if (!author) return AGENT_METADATA.unknown;
  return AGENT_METADATA[author] || AGENT_METADATA[author.replace(/\s+/g, '_')] || AGENT_METADATA.unknown;
};

// Robust, customized Markdown to HTML parser
function parseMarkdown(text) {
  if (!text) return '';
  let html = text;

  // Escape HTML tags to prevent XSS while allowing our own generated tags
  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code Blocks
  html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

  // Inline Code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Headers (H1, H2, H3)
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Bold & Italics
  html = html.replace(/\*\*([\s\S]*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([\s\S]*?)\*/g, '<em>$1</em>');

  // Horizontal Rules
  html = html.replace(/^\s*[-*_]{3,}\s*$/gim, '<hr>');

  // Numbered lists (consecutive lines)
  html = html.replace(/^\s*\d+\.\s+(.*)/gim, '<ol><li>$1</li></ol>');
  html = html.replace(/<\/ol>\s*<ol>/gim, '');

  // Bullet lists (consecutive lines starting with - or *)
  html = html.replace(/^\s*[\-\*]\s+(.*)/gim, '<ul><li>$1</li></ul>');
  html = html.replace(/<\/ul>\s*<ul>/gim, '');

  // Tables
  // Match rows with pipe borders
  html = html.replace(/^\s*\|(.+)\|\s*$/gim, (match, p1) => {
    const cells = p1.split('|').map(c => `<td>${c.trim()}</td>`).join('');
    return `<tr>${cells}</tr>`;
  });
  
  // Clean up formatting rows like |---|---| and wrap consecutive trs in table tags
  html = html.replace(/(<tr>.*?<\/tr>\n?)+/g, match => {
    // Remove divider row
    let cleaned = match.replace(/<tr>(\s*<td>\s*[:\- ]+\s*<\/td>\s*)+<\/tr>\n?/g, ''); 
    // Convert first row <td> to <th> for header styling
    cleaned = cleaned.replace(/^<tr>(.*?)<\/tr>/i, (firstRow, cellsContent) => {
      const headers = cellsContent.replace(/<td>/g, '<th>').replace(/<\/td>/g, '</th>');
      return `<tr>${headers}</tr>`;
    });
    return `<table>${cleaned}</table>`;
  });

  // Line breaks
  html = html.replace(/\n/g, '<br>');

  return html;
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [status, setStatus] = useState('Standing by');
  const [statusType, setStatusType] = useState('idle'); // 'idle' | 'active' | 'error'
  const [isPlanning, setIsPlanning] = useState(false);
  const [openAccordionId, setOpenAccordionId] = useState(null);

  const chatFeedRef = useRef(null);
  const textareaRef = useRef(null);

  // Theme State Management (2-state system: follows system, or pinned to user choice)
  const getSystemTheme = () => window.matchMedia("(prefers-color-scheme: dark)").matches ? 'dark' : 'light';

  const [isThemePinned, setIsThemePinned] = useState(() => !!localStorage.getItem("color-scheme"));
  const [theme, setTheme] = useState(() => {
    const pinned = localStorage.getItem("color-scheme");
    if (pinned === 'light' || pinned === 'dark') return pinned;
    return getSystemTheme();
  });

  // Sync theme with document attribute & meta tags
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    const meta = document.querySelector('meta[name="color-scheme"]');
    if (meta) {
      meta.content = theme;
    }
  }, [theme]);

  // Listen to system level preference changes when the user has not pinned a preference
  useEffect(() => {
    if (isThemePinned) return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (e) => {
      setTheme(e.matches ? 'dark' : 'light');
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [isThemePinned]);

  const toggleTheme = () => {
    const systemTheme = getSystemTheme();
    
    if (isThemePinned) {
      // Revert back to auto-syncing with system
      localStorage.removeItem("color-scheme");
      setIsThemePinned(false);
      setTheme(systemTheme);
    } else {
      // Pin to the opposite of current system theme
      const oppositeTheme = systemTheme === 'dark' ? 'light' : 'dark';
      localStorage.setItem("color-scheme", oppositeTheme);
      setIsThemePinned(true);
      setTheme(oppositeTheme);
    }
  };

  // Read backend API URL from env variables
  const apiUrl = import.meta.env.VITE_AGENT_API_URL || 'http://localhost:8080';

  // Automatically scroll to bottom of chat feed when messages update
  useEffect(() => {
    if (chatFeedRef.current) {
      chatFeedRef.current.scrollTop = chatFeedRef.current.scrollHeight;
    }
  }, [messages, isPlanning]);

  // Handle textarea height auto-resizing
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [input]);

  // Create a new session in the ADK session service
  const createSession = async () => {
    try {
      setStatus('Creating agent session...');
      setStatusType('active');
      
      const response = await fetch(`${apiUrl}/apps/app/users/web-user/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          state: {}
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to create session: status ${response.status}`);
      }

      const data = await response.json();
      setSessionId(data.id);
      setStatus('Standing by');
      setStatusType('idle');
      return data.id;
    } catch (err) {
      console.error('Error creating session:', err);
      setStatus(`Failed to connect to agent backend on ${apiUrl}. Ensure the playground is running.`);
      setStatusType('error');
      return null;
    }
  };

  // Triggered when user submits a message
  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (isPlanning || !input.trim()) return;

    const queryText = input.trim();
    setInput('');
    setIsPlanning(true);
    setStatusType('active');

    // Add user message to UI
    const userMsgId = Date.now().toString();
    setMessages(prev => [
      ...prev,
      {
        id: userMsgId,
        sender: 'user',
        author: 'user',
        text: queryText,
        timestamp: Date.now() / 1000
      }
    ]);

    // Create a fresh agent message bubble
    const agentMsgId = (Date.now() + 1).toString();
    const newAgentMsg = {
      id: agentMsgId,
      sender: 'agent',
      author: 'orchestrator',
      text: '',
      trajectory: [],
      isStreaming: true
    };

    setMessages(prev => [...prev, newAgentMsg]);
    // setOpenAccordionId(agentMsgId); // Open accordion for active execution

    try {
      // 1. Ensure we have an active session
      let activeSessionId = sessionId;
      if (!activeSessionId) {
        activeSessionId = await createSession();
        if (!activeSessionId) {
          throw new Error('Could not establish agent session.');
        }
      }

      setStatus('Connecting to agent...');

      // 2. Post the request to /run_sse
      const response = await fetch(`${apiUrl}/run_sse`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          app_name: 'app',
          user_id: 'web-user',
          session_id: activeSessionId,
          new_message: {
            parts: [{ text: queryText }]
          },
          streaming: true
        })
      });

      if (!response.ok) {
        throw new Error(`API error! Status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let accumulatedText = '';
      let activeAuthor = 'orchestrator';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let boundary = buffer.indexOf('\n\n');

        while (boundary !== -1) {
          const chunk = buffer.slice(0, boundary).trim();
          buffer = buffer.slice(boundary + 2);
          boundary = buffer.indexOf('\n\n');

          if (chunk.startsWith('data: ')) {
            const dataStr = chunk.slice(6);
            try {
              const event = JSON.parse(dataStr);

              // 3. Parse ADK SSE raw event fields
              const author = event.author || 'orchestrator';
              const agentInfo = getAgentInfo(author);
              setStatus(`${agentInfo.name} is working...`);

              // Update the active speaker avatar
              activeAuthor = author;

              // Extract function calls from event content parts (trajectory steps)
              let toolCallsList = [];
              if (event.content && event.content.parts) {
                for (const part of event.content.parts) {
                  if (part.functionCall) {
                    toolCallsList.push({
                      timestamp: event.timestamp || (Date.now() / 1000),
                      author: author,
                      action: part.functionCall.name,
                      args: part.functionCall.args ? JSON.stringify(part.functionCall.args) : '{}'
                    });
                  }
                }
              }

              // Extract text stream deltas
              let textDelta = '';
              if (event.content && event.content.parts) {
                for (const part of event.content.parts) {
                  if (part.text) {
                    textDelta += part.text;
                  }
                }
              }

              // Apply updates to the active agent bubble
              setMessages(prev =>
                prev.map(m => {
                  if (m.id === agentMsgId) {
                    const nextTrajectory = [...m.trajectory];
                    toolCallsList.forEach(tc => {
                      // Avoid duplicates
                      if (!nextTrajectory.some(existing => 
                        existing.action === tc.action && 
                        Math.abs(existing.timestamp - tc.timestamp) < 2
                      )) {
                        nextTrajectory.push(tc);
                      }
                    });

                    return {
                      ...m,
                      author: activeAuthor,
                      text: m.text + textDelta,
                      trajectory: nextTrajectory
                    };
                  }
                  return m;
                })
              );

            } catch (err) {
              console.error('Error parsing SSE event JSON:', err, dataStr);
            }
          }
        }
      }

      // Mark streaming completed successfully
      setMessages(prev =>
        prev.map(m => (m.id === agentMsgId ? { ...m, isStreaming: false } : m))
      );
      setStatus('Standing by');
      setStatusType('idle');

    } catch (err) {
      console.error('SSE execution error:', err);
      setStatus(`Execution error: ${err.message}`);
      setStatusType('error');
      
      // Update message bubble to stop streaming state and display error
      setMessages(prev =>
        prev.map(m =>
          m.id === agentMsgId
            ? {
                ...m,
                isStreaming: false,
                text: m.text + `\n\n*(Error: Connection to the agent was lost. ${err.message})*`
              }
            : m
        )
      );
    } finally {
      setIsPlanning(false);
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const selectFeaturePrompt = (text) => {
    setInput(text);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  const toggleAccordion = (id) => {
    setOpenAccordionId(prev => (prev === id ? null : id));
  };

  return (
    <div className="app-container">
      {/* Premium Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-logo">🌌</div>
          <div>
            <h1>Journey Chat</h1>
          </div>
          <span>Trip Planner Agent</span>
        </div>
        
        <div className="header-controls">
          <button 
            className={`theme-toggle-btn ${isThemePinned ? 'pinned' : ''}`}
            onClick={toggleTheme}
            title={isThemePinned ? `Theme pinned to ${theme}. Click to follow system.` : `Following system (${theme}). Click to toggle theme.`}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? (
              <svg className="theme-icon moon-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
              </svg>
            ) : (
              <svg className="theme-icon sun-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5"></circle>
                <line x1="12" y1="1" x2="12" y2="3"></line>
                <line x1="12" y1="21" x2="12" y2="23"></line>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                <line x1="1" y1="12" x2="3" y2="12"></line>
                <line x1="21" y1="12" x2="23" y2="12"></line>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
              </svg>
            )}
            <span className="theme-toggle-dot"></span>
          </button>

          <div className="status-section">
            <div className={`status-dot ${statusType === 'active' ? 'active' : statusType === 'error' ? 'error' : 'idle'}`}></div>
            <span className="status-text">{status}</span>
          </div>
        </div>
      </header>

      {/* Main Chat Feed */}
      {messages.length === 0 ? (
        <div className="welcome-screen">
          <div className="welcome-logo">🚀</div>
          <h2>Plan Your Epic Journey</h2>
          <p>
            Describe your ideal road trip. The Journey Agent coordinates routing, searches hotels, and discovers activities using live Google APIs.
          </p>
          
          <div className="welcome-features">
            <div 
              className="feature-card"
              onClick={() => selectFeaturePrompt("Plan a 3-day road trip from Seattle to Portland focusing on nature and hiking")}
            >
              <h3>Seattle to Portland</h3>
              <p>3-day road trip with beautiful nature, forest hikes, and outdoor activities.</p>
            </div>
            <div 
              className="feature-card"
              onClick={() => selectFeaturePrompt("Plan a weekend getaway from Los Angeles to Santa Barbara, finding premium beachside hotels")}
            >
              <h3>LA to Santa Barbara</h3>
              <p>Weekend coastal escape with beach hotels, dining, and scenic ocean views.</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="chat-feed-container" ref={chatFeedRef}>
          {messages.map((msg) => {
            const agentInfo = getAgentInfo(msg.author);
            const isUser = msg.sender === 'user';
            const formattedTime = msg.timestamp ? new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

            return (
              <div key={msg.id} className={`message-wrapper ${isUser ? 'user' : 'agent'}`}>
                {/* Message Header Info */}
                <div className="message-header-info">
                  <span className="message-avatar">{agentInfo.icon}</span>
                  <span className="message-author-name">{agentInfo.name}</span>
                  {formattedTime && <span className="message-time">{formattedTime}</span>}
                </div>

                {/* Message Content Bubble */}
                <div className="message-bubble">
                  {isUser ? (
                    <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
                  ) : (
                    <>
                      {/* Markdown text response */}
                      {msg.text ? (
                        <div 
                          className="markdown-body"
                          dangerouslySetInnerHTML={{ __html: parseMarkdown(msg.text) }}
                        />
                      ) : (
                        msg.isStreaming && (
                          <div className="typing-indicator">
                            <div className="typing-dot"></div>
                            <div className="typing-dot"></div>
                            <div className="typing-dot"></div>
                          </div>
                        )
                      )}

                      {/* Collapsible Trajectory Steps / Agent Thoughts */}
                      {msg.trajectory && msg.trajectory.length > 0 && (
                        <div className="trajectory-accordion">
                          <div 
                            className="trajectory-header"
                            onClick={() => toggleAccordion(msg.id)}
                          >
                            <div className="trajectory-status-line">
                              <span>⚙️</span>
                              <span>Agent Execution Path ({msg.trajectory.length} steps)</span>
                            </div>
                            <span className={`chevron-icon ${openAccordionId === msg.id ? 'open' : ''}`}>▼</span>
                          </div>

                          {openAccordionId === msg.id && (
                            <div className="trajectory-content">
                              {msg.trajectory.map((step, idx) => {
                                const stepAgent = getAgentInfo(step.author);
                                const logTime = new Date(step.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                                return (
                                  <div key={idx} className="trajectory-log-line">
                                    <span className="log-time">[{logTime}]</span>
                                    <span className={`log-author ${stepAgent.class}`}>&lt;{stepAgent.name}&gt;</span>
                                    <span className="log-action">calling {step.action}</span>
                                    <span className="log-args">with args {step.args}</span>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Input section fixed at bottom */}
      <div className="chat-input-wrapper">
        <form onSubmit={handleSubmit} className="chat-form">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder="e.g. Plan a 3-day road trip from Seattle to Portland..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={isPlanning}
          />
          <button 
            type="submit" 
            className="send-button"
            disabled={isPlanning || !input.trim()}
            aria-label="Send message"
          >
            <svg className="send-button-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}
