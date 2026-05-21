// Global state
let map = null;
let markers = [];
let routePolyline = null;
let animMarker = null;
let currentAnim = null;
let currentSessionId = null;
let isPlanning = false;
let stops = []; // Array of {name: string, coords: [lat, lng]}

let geocodeQueue = [];
let isGeocoding = false;

// Initialize on Load
document.addEventListener("DOMContentLoaded", () => {
    initThemeToggle();
    initMap();

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
            const tileUrl = getTileUrl(newTheme);
            map.eachLayer(layer => {
                if (layer instanceof L.TileLayer) {
                    layer.setUrl(tileUrl);
                }
            });
        }
    });
}

function getTileUrl(theme) {
    // Indiana Jones Vintage look (CartoDB Positron)
    return theme === 'dark' 
        ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
        : 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png'; // Voyager has a warm, vintage feel
}

// Leaflet Maps Initialization
function initMap() {
    const theme = document.documentElement.getAttribute("data-theme") || "light";
    
    map = L.map('map-container', {
        zoomControl: false
    }).setView([39.8283, -98.5795], 4);
    
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    L.tileLayer(getTileUrl(theme), {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    document.getElementById('replay-btn').addEventListener('click', playIndianaJonesAnimation);
}

// Chat UI Logic
const chatFeed = document.getElementById('chat-feed');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const agentIndicator = document.getElementById('agent-indicator');
const agentMessage = document.getElementById('agent-message');

function scrollToBottom() {
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

const agentIcons = {
    'route_planner': '🚙',
    'hotel_agent': '🛏️',
    'activities_agent': '⭐',
    'tour_agent': '🧭',
    'root_agent': '🧠'
};

const agentNames = {
    'route_planner': 'Route Planner',
    'hotel_agent': 'Hotel Agent',
    'activities_agent': 'Activities Agent',
    'tour_agent': 'Tour Agent',
    'root_agent': 'Orchestrator'
};

function formatTime(unixTime) {
    const date = new Date(unixTime * 1000);
    return date.toLocaleTimeString([], { hour12: false });
}

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
            <div class="trajectory-panel" style="display: none;">
                <div class="trajectory-header">
                    <div class="trajectory-title">
                        <span class="trajectory-icon">🧠</span>
                        <span class="trajectory-progress">Agent is planning...</span>
                    </div>
                    <button type="button" class="trajectory-toggle">Show activity</button>
                </div>
                <div class="trajectory-log-container"></div>
            </div>
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
    
    const toggle = div.querySelector('.trajectory-toggle');
    const header = div.querySelector('.trajectory-header');
    const logContainer = div.querySelector('.trajectory-log-container');
    
    header.addEventListener('click', () => {
        logContainer.classList.toggle('open');
        header.classList.toggle('expanded');
        toggle.textContent = logContainer.classList.contains('open') ? 'Hide activity' : 'Show activity';
    });

    return {
        container: div,
        contentEl: div.querySelector('.message-content'),
        typingEl: div.querySelector('.typing-indicator'),
        trajectoryPanel: div.querySelector('.trajectory-panel'),
        trajectoryIcon: div.querySelector('.trajectory-icon'),
        trajectoryProgress: div.querySelector('.trajectory-progress'),
        trajectoryLog: div.querySelector('.trajectory-log-container'),
        stepCount: 0
    };
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
                        else if (data.type === 'trajectory') {
                            agentBubble.trajectoryPanel.style.display = 'block';
                            agentBubble.stepCount++;
                            
                            const author = data.author;
                            const action = data.action;
                            const args = JSON.stringify(data.args);
                            const timeStr = formatTime(data.timestamp);
                            const icon = agentIcons[author] || '🤖';
                            const authorName = agentNames[author] || author;
                            
                            // Update Master Agent Indicator
                            agentIndicator.innerHTML = icon;
                            agentMessage.textContent = `${authorName} is working...`;
                            
                            // Update Trajectory Progress
                            agentBubble.trajectoryIcon.textContent = icon;
                            agentBubble.trajectoryProgress.textContent = `Step ${agentBubble.stepCount}: ${authorName} is calling ${action}...`;
                            
                            // Append Log Line
                            const logLine = document.createElement('div');
                            logLine.className = 'trajectory-log-line';
                            logLine.innerHTML = `
                                <span class="log-time">[${timeStr}]</span>
                                <span class="log-author author-${author}">&lt;${author}&gt;</span>
                                <span class="log-action">calling ${action}</span>
                                <span class="log-args">(${args})</span>
                            `;
                            agentBubble.trajectoryLog.appendChild(logLine);
                            
                            if(agentBubble.trajectoryLog.classList.contains('open')) {
                                agentBubble.trajectoryLog.scrollTop = agentBubble.trajectoryLog.scrollHeight;
                            }
                        }
                        else if (data.type === 'event' && data.text) {
                            if (agentBubble.typingEl.style.display !== 'none') {
                                agentBubble.typingEl.style.display = 'none';
                                agentBubble.contentEl.style.display = 'block';
                            }
                            
                            if (data.author) {
                                const icon = agentIcons[data.author] || '🤖';
                                const authorName = agentNames[data.author] || data.author;
                                agentIndicator.innerHTML = icon;
                                agentMessage.textContent = `${authorName} is speaking...`;
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

// Robust Markdown Parser
function parseMarkdown(text) {
    let html = text;

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Bold & Italic
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // HR
    html = html.replace(/^\-\-\-/gim, '<hr>');

    // Lists
    html = html.replace(/^\s*[\-\*]\s+(.*)/gim, '<ul><li>$1</li></ul>');
    html = html.replace(/^\s*\d+\.\s+(.*)/gim, '<ol><li>$1</li></ol>');

    // Clean up adjacent lists
    html = html.replace(/<\/ul>\n<ul>/g, '\n');
    html = html.replace(/<\/ol>\n<ol>/g, '\n');

    // Tables
    html = html.replace(/^\|(.+)\|$/gim, (match, p1) => {
        let cells = p1.split('|').map(c => `<td>${c.trim()}</td>`).join('');
        return `<tr>${cells}</tr>`;
    });
    html = html.replace(/(<tr>.*?<\/tr>\n?)+/g, match => {
        let m = match.replace(/<td>\-\-\-.*?<\/td>/g, ''); 
        return `<div style="overflow-x:auto;"><table border="1"><tbody>${m}</tbody></table></div>`;
    });

    // Newlines to P/BR for untagged lines
    html = html.split('\n').map(line => {
        if (!line.trim() || line.match(/<(h|ul|ol|li|hr|table|tr|div)/)) return line;
        return `<p>${line}</p>`;
    }).join('\n');

    return html;
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
    
    // 5. Standard Text / Fallback to Markdown Parser
    return `<div style="margin-bottom:0.75rem;">${parseMarkdown(text)}</div>`;
}


// Nominatim Geocoding
async function geocodeLocation(name) {
    if (window._geocodeCache && window._geocodeCache[name]) {
        return window._geocodeCache[name];
    }
    
    try {
        const response = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(name)}&format=json&limit=1`, {
            headers: {
                'User-Agent': 'JourneyApp/1.0'
            }
        });
        const data = await response.json();
        if (data && data.length > 0) {
            const coords = [parseFloat(data[0].lat), parseFloat(data[0].lon)];
            window._geocodeCache = window._geocodeCache || {};
            window._geocodeCache[name] = coords;
            return coords;
        }
    } catch (e) {
        console.error("Geocoding failed for", name, e);
    }
    return null;
}

// Queue system to respect Nominatim limits
function extractAndGeocodeLocation(blockText) {
    if (!map) return;
    
    let locationMatch = blockText.match(/\*\*(Hotel|Accommodation|Activity|Tour|Stop):\*\*\s*(.*?)(?:\n|$)/i) || 
                        blockText.match(/^(Hotel|Accommodation|Activity|Tour|Stop):\s*(.*?)(?:\n|$)/i);
                        
    if (locationMatch) {
        let name = locationMatch[2].replace(/\*\*/g, '').trim();
        name = name.split('-')[0].split(',')[0].trim();
        
        if (!stops.some(s => s.name === name)) {
            geocodeQueue.push(name);
            processGeocodeQueue();
        }
    }
}

async function processGeocodeQueue() {
    if (isGeocoding || geocodeQueue.length === 0) return;
    isGeocoding = true;
    
    const name = geocodeQueue.shift();
    const coords = await geocodeLocation(name);
    
    if (coords) {
        addStopToMap(name, coords);
    }
    
    // Rate limit: 1.1s for Nominatim
    setTimeout(() => {
        isGeocoding = false;
        processGeocodeQueue();
    }, 1100);
}

function addStopToMap(name, coords) {
    const stopNum = stops.length + 1;
    stops.push({ name, coords });
    
    const legendList = document.getElementById('legend-list');
    const li = document.createElement('li');
    li.innerHTML = `<div class="legend-marker">${stopNum}</div> <span>${name}</span>`;
    legendList.appendChild(li);
    
    const iconHtml = `<div class="legend-marker" style="margin:0; box-shadow:0 2px 5px rgba(0,0,0,0.3);">${stopNum}</div>`;
    const customIcon = L.divIcon({
        html: iconHtml,
        className: 'custom-div-icon',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
    
    const marker = L.marker(coords, { icon: customIcon }).addTo(map);
    marker.bindPopup(`<b>Stop ${stopNum}</b><br>${name}`);
    markers.push(marker);
    
    const group = new L.featureGroup(markers);
    map.fitBounds(group.getBounds(), { padding: [50, 50] });
    
    if (stops.length >= 2) {
        document.getElementById('replay-btn').style.display = 'block';
        playIndianaJonesAnimation();
    }
}

// Indiana Jones Custom Animation
function playIndianaJonesAnimation() {
    if (routePolyline) map.removeLayer(routePolyline);
    if (animMarker) map.removeLayer(animMarker);
    if (currentAnim) cancelAnimationFrame(currentAnim);
    
    const latlngs = stops.map(s => s.coords);
    if (latlngs.length < 2) return;
    
    routePolyline = L.polyline([latlngs[0]], {
        color: '#f44336', 
        weight: 4, 
        dashArray: '10, 10', 
        opacity: 0.8
    }).addTo(map);
    
    const planeIcon = L.divIcon({
        html: '<div class="travel-icon" style="transform: scaleX(-1);">✈️</div>',
        className: 'plane-icon-wrapper',
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    });
    animMarker = L.marker(latlngs[0], { icon: planeIcon, zIndexOffset: 1000 }).addTo(map);
    
    let startTime = null;
    const durationPerSegment = 1500; // 1.5 seconds per leg
    
    function animate(timestamp) {
        if (!startTime) startTime = timestamp;
        const progress = timestamp - startTime;
        
        const totalDuration = (latlngs.length - 1) * durationPerSegment;
        
        if (progress >= totalDuration) {
            routePolyline.setLatLngs(latlngs);
            animMarker.setLatLng(latlngs[latlngs.length - 1]);
            return; // Animation finished
        }
        
        const currentSegment = Math.floor(progress / durationPerSegment);
        const segmentProgress = (progress % durationPerSegment) / durationPerSegment;
        
        const p1 = latlngs[currentSegment];
        const p2 = latlngs[currentSegment + 1];
        
        // Linear interpolation
        const currentLat = p1[0] + (p2[0] - p1[0]) * segmentProgress;
        const currentLng = p1[1] + (p2[1] - p1[1]) * segmentProgress;
        
        const currentPath = latlngs.slice(0, currentSegment + 1);
        currentPath.push([currentLat, currentLng]);
        
        routePolyline.setLatLngs(currentPath);
        animMarker.setLatLng([currentLat, currentLng]);
        
        // Auto-pan map if plane gets close to edge
        const planePt = map.latLngToContainerPoint([currentLat, currentLng]);
        const size = map.getSize();
        if (planePt.x < 50 || planePt.x > size.x - 50 || planePt.y < 50 || planePt.y > size.y - 50) {
             map.panTo([currentLat, currentLng], { animate: true, duration: 0.5 });
        }
        
        currentAnim = requestAnimationFrame(animate);
    }
    
    currentAnim = requestAnimationFrame(animate);
}
