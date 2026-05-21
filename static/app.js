// Global state
let map = null;
let geocoder = null;
let markers = [];
let currentSessionId = null;
let isPlanning = false;

// Initialize on Load
document.addEventListener("DOMContentLoaded", async () => {
    initThemeToggle();
    
    // Fetch Maps Config
    try {
        const res = await fetch("/api/config");
        const data = await res.json();
        if (data.maps_api_key) {
            const script = document.createElement("script");
            script.src = `https://maps.googleapis.com/maps/api/js?key=${data.maps_api_key}&callback=initMap`;
            script.async = true;
            script.defer = true;
            document.head.appendChild(script);
        }
    } catch (err) {
        console.error("Failed to load map config", err);
    }

    // Attach form listener
    document.getElementById("chat-form").addEventListener("submit", handleChatSubmit);
    
    // Handle Enter key for textarea
    const chatInput = document.getElementById('chat-input');
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            document.getElementById("chat-form").dispatchEvent(new Event('submit'));
        }
    });
});

// Theme Toggle Logic
function initThemeToggle() {
    const toggleBtn = document.getElementById("theme-toggle");
    const htmlEl = document.documentElement;
    
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) {
        htmlEl.setAttribute("data-theme", savedTheme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        htmlEl.setAttribute("data-theme", "dark");
    }

    toggleBtn.addEventListener("click", () => {
        const currentTheme = htmlEl.getAttribute("data-theme");
        const newTheme = currentTheme === "dark" ? "light" : "dark";
        htmlEl.setAttribute("data-theme", newTheme);
        localStorage.setItem("theme", newTheme);
        
        if (map) {
            map.setOptions({ styles: getMapStyles(newTheme) });
        }
    });
}

// Google Maps Initialization
window.initMap = function() {
    const theme = document.documentElement.getAttribute("data-theme") || "light";
    map = new google.maps.Map(document.getElementById("google-map-container"), {
        center: { lat: 39.8283, lng: -98.5795 },
        zoom: 4,
        styles: getMapStyles(theme),
        disableDefaultUI: true,
        zoomControl: true
    });
    geocoder = new google.maps.Geocoder();
};

function getMapStyles(theme) {
    if (theme === "dark") {
        return [
            { elementType: "geometry", stylers: [{ color: "#24272b" }] },
            { elementType: "labels.text.stroke", stylers: [{ color: "#24272b" }] },
            { elementType: "labels.text.fill", stylers: [{ color: "#a0aec0" }] },
            { featureType: "road", elementType: "geometry", stylers: [{ color: "#3a3b38" }] },
            { featureType: "water", elementType: "geometry", stylers: [{ color: "#1a1c1e" }] }
        ];
    } else {
        return [
            { elementType: "geometry", stylers: [{ color: "#f9f6f0" }] },
            { elementType: "labels.text.stroke", stylers: [{ color: "#ffffff" }] },
            { elementType: "labels.text.fill", stylers: [{ color: "#718096" }] },
            { featureType: "water", elementType: "geometry", stylers: [{ color: "#cbd5e0" }] }
        ];
    }
}

// Chat UI Logic
const chatFeed = document.getElementById('chat-feed');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const agentIndicator = document.getElementById('agent-indicator');
const agentMessage = document.getElementById('agent-message');

function appendUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'message user-message';
    div.innerHTML = `
        <div class="message-bubble">
            <p>${text.replace(/\n/g, '<br>')}</p>
        </div>
    `;
    chatFeed.appendChild(div);
    scrollToBottom();
}

function createAgentMessageBubble() {
    const div = document.createElement('div');
    div.className = 'message agent-message';
    div.innerHTML = `
        <div class="message-bubble">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
            <div class="message-content" style="display: none;"></div>
        </div>
    `;
    chatFeed.appendChild(div);
    scrollToBottom();
    return {
        container: div,
        contentEl: div.querySelector('.message-content'),
        typingEl: div.querySelector('.typing-indicator')
    };
}

function scrollToBottom() {
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

// Handle Form Submit and Fetch SSE
async function handleChatSubmit(e) {
    e.preventDefault();
    if (isPlanning) return;

    const message = chatInput.value.trim();
    if (!message) return;

    // UI Updates
    isPlanning = true;
    appendUserMessage(message);
    chatInput.value = '';
    sendBtn.disabled = true;
    agentIndicator.classList.add('active');
    agentMessage.textContent = 'Agent is thinking...';

    const agentBubble = createAgentMessageBubble();
    let rawMarkdown = "";

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                session_id: currentSessionId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

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
                        const data = JSON.parse(dataStr);
                        
                        if (data.type === 'session') {
                            currentSessionId = data.session_id;
                        } 
                        else if (data.type === 'status') {
                            agentMessage.textContent = data.message;
                        } 
                        else if (data.type === 'event' && data.text) {
                            if (agentBubble.typingEl.style.display !== 'none') {
                                agentBubble.typingEl.style.display = 'none';
                                agentBubble.contentEl.style.display = 'block';
                            }
                            rawMarkdown += data.text;
                            renderAgentContent(rawMarkdown, agentBubble.contentEl);
                            scrollToBottom();
                        }
                        else if (data.type === 'error') {
                            agentMessage.textContent = "Error: " + data.message;
                            agentIndicator.classList.remove("active");
                            agentIndicator.style.background = "#e53e3e";
                        }
                    } catch (err) {
                        console.error("JSON parse error:", err, dataStr);
                    }
                }
            }
        }
    } catch (e) {
        console.error("Fetch error:", e);
        if (agentBubble.typingEl.style.display !== 'none') {
            agentBubble.typingEl.style.display = 'none';
            agentBubble.contentEl.style.display = 'block';
        }
        agentBubble.contentEl.innerHTML += `<div style="color: red; margin-top: 10px;">Connection error.</div>`;
    } finally {
        isPlanning = false;
        sendBtn.disabled = false;
        agentIndicator.classList.remove('active');
        agentMessage.textContent = 'Standing by';
        chatInput.focus();
    }
}

// Inline Markdown Parser
function renderAgentContent(rawMarkdown, container) {
    let blocks = rawMarkdown.split('\n\n');
    
    blocks.forEach((blockText, index) => {
        if (!blockText.trim()) return;
        
        let blockId = `block-${index}`;
        let el = container.querySelector(`#${blockId}`);
        let parsedHtml = parseBlock(blockText.trim());
        
        if (!el) {
            el = document.createElement('div');
            el.id = blockId;
            el.innerHTML = parsedHtml;
            container.appendChild(el);
            
            extractAndGeocodeLocation(blockText.trim());
        } else {
            if (el.getAttribute('data-raw') !== blockText) {
                el.innerHTML = parsedHtml;
            }
        }
        el.setAttribute('data-raw', blockText);
    });
}

// Custom Markdown to HTML Block Parser (From Previous App)
function parseBlock(text) {
    // 1. Day Headers
    let match = text.match(/^##\s*(Day\s*\d+.*)/i) || text.match(/^(Day\s*\d+.*)/i);
    if (match && text.length < 100 && (text.startsWith("##") || text.includes(":"))) {
        const title = match[1].replace(/\*\*/g, '');
        return `<div class="itinerary-day"><div class="day-header">${title}</div></div>`;
    }
    
    // 2. Hotel / Accommodation
    match = text.match(/\*\*(Hotel|Accommodation):\*\*\s*(.*)/i) || text.match(/^(Hotel|Accommodation):\s*(.*)/i);
    if (match) {
        const label = match[1];
        const namePart = match[2].split('\n')[0].replace(/\*\*/g, '').trim();
        const imgQuery = namePart.replace(/[^a-zA-Z0-9 ]/g, '');
        const imgUrl = `https://source.unsplash.com/400x300/?${encodeURIComponent(imgQuery + ' hotel')}`;
        
        let desc = text.replace(match[0], '').replace(/\*\*/g, '').trim();
        if (desc.startsWith('-')) desc = desc.substring(1).trim();
        
        return `
        <div class="itinerary-day" style="display:flex; gap:1rem; align-items:center;">
            <div style="width:100px; height:100px; background-image:url('${imgUrl}'); background-size:cover; border-radius:8px; flex-shrink:0;"></div>
            <div>
                <div style="font-size:0.75rem; text-transform:uppercase; color:var(--accent-color); font-weight:600;">${label}</div>
                <div style="font-weight:bold; font-size:1.1rem;">${namePart}</div>
                <div style="font-size:0.9rem; color:var(--text-secondary); margin-top:0.25rem;">${desc.substring(0, 100)}${desc.length > 100 ? '...' : ''}</div>
            </div>
        </div>`;
    }
    
    // 3. Activity / Tour
    match = text.match(/\*\*(Activity|Tour|Stop):\*\*\s*(.*)/i) || text.match(/^(Activity|Tour|Stop):\s*(.*)/i);
    if (match) {
        const label = match[1];
        const namePart = match[2].split('\n')[0].replace(/\*\*/g, '').trim();
        const imgQuery = namePart.replace(/[^a-zA-Z0-9 ]/g, '');
        const imgUrl = `https://source.unsplash.com/400x300/?${encodeURIComponent(imgQuery)}`;
        
        let desc = text.replace(match[0], '').replace(/\*\*/g, '').trim();
        if (desc.startsWith('-')) desc = desc.substring(1).trim();

        return `
        <div class="itinerary-day" style="display:flex; gap:1rem; align-items:center;">
            <div style="width:100px; height:100px; background-image:url('${imgUrl}'); background-size:cover; border-radius:8px; flex-shrink:0;"></div>
            <div>
                <div style="font-size:0.75rem; text-transform:uppercase; color:var(--accent-color); font-weight:600;">${label}</div>
                <div style="font-weight:bold; font-size:1.1rem;">${namePart}</div>
                <div style="font-size:0.9rem; color:var(--text-secondary); margin-top:0.25rem;">${desc.substring(0, 100)}${desc.length > 100 ? '...' : ''}</div>
            </div>
        </div>`;
    }
    
    // 4. Drive Segment
    match = text.match(/\*\*(Drive|Distance|Route):\*\*\s*(.*)/i) || text.match(/^(Drive|Distance|Route):\s*(.*)/i);
    if (match) {
        const desc = match[2].replace(/\*\*/g, '').split('\n')[0];
        return `
        <div style="display:flex; align-items:center; gap:0.5rem; margin:1rem 0; padding-left:1rem; border-left:2px dashed var(--border-color); color:var(--text-secondary);">
            <div style="font-size:1.2rem;">🚙</div>
            <div style="font-size:0.9rem;">${desc}</div>
        </div>`;
    }
    
    // 5. Standard Text / Bullet Points
    let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formattedText = formattedText.replace(/\n/g, '<br>');
    
    if (formattedText.includes('- ')) {
        formattedText = formattedText.replace(/- (.*?)<br>/g, '<li>$1</li>');
        formattedText = formattedText.replace(/- (.*?)$/g, '<li>$1</li>');
        if (formattedText.includes('<li>')) {
            formattedText = `<ul style="padding-left:1.5rem; margin:0.5rem 0;">${formattedText}</ul>`;
        }
    }
    
    return `<div style="margin-bottom:0.75rem;"><p>${formattedText}</p></div>`;
}

// Map Extraction Logic
function extractAndGeocodeLocation(blockText) {
    if (!geocoder || !map) return;
    
    let locationMatch = blockText.match(/\*\*(Hotel|Accommodation|Activity|Tour|Stop):\*\*\s*(.*?)(?:\n|$)/i) || 
                        blockText.match(/^(Hotel|Accommodation|Activity|Tour|Stop):\s*(.*?)(?:\n|$)/i);
                        
    if (locationMatch) {
        let name = locationMatch[2].replace(/\*\*/g, '').trim();
        name = name.split('-')[0].split(',')[0].trim();
        
        geocoder.geocode({ address: name }, (results, status) => {
            if (status === "OK" && results[0]) {
                const loc = results[0].geometry.location;
                let marker = new google.maps.Marker({
                    map: map,
                    position: loc,
                    title: name,
                    animation: google.maps.Animation.DROP
                });
                markers.push(marker);
                
                if (markers.length > 1) {
                    let bounds = new google.maps.LatLngBounds();
                    markers.forEach(m => bounds.extend(m.getPosition()));
                    map.fitBounds(bounds);
                } else {
                    map.setCenter(loc);
                    map.setZoom(10);
                }
            }
        });
    }
}
