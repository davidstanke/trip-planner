// VagabondAI Client Logic

let map;
let routeLayer = null;
let markersGroup = null;
let currentItineraryMarkdown = "";

document.addEventListener("DOMContentLoaded", () => {
    initMap();
    
    document.getElementById("trip-form").addEventListener("submit", handleFormSubmit);
    document.getElementById("download-btn").addEventListener("click", downloadItinerary);
});

function initMap() {
    map = L.map('map', {
        zoomControl: false // Move zoom control to bottom right
    }).setView([39.8, -98.5], 4);
    
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    // Premium CartoDB Dark Matter
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    markersGroup = L.layerGroup().addTo(map);
}

// Custom Markdown Renderer for Timeline
const timelineRenderer = new marked.Renderer();
timelineRenderer.heading = function({ text, depth }) {
    if (depth === 2 && text.toLowerCase().includes("day")) {
        return `<div class="timeline-day"><h2 class="day-header">${text}</h2><div class="timeline-content">`;
    } else if (depth === 2) {
        return `</div><div class="timeline-day"><h2 class="day-header">${text}</h2><div class="timeline-content">`;
    } else if (depth === 3) {
        return `<h3>${text}</h3>`;
    }
    return `<h${depth}>${text}</h${depth}>`;
};

marked.use({ renderer: timelineRenderer });

async function handleFormSubmit(e) {
    e.preventDefault();

    // UI Elements
    const layout = document.getElementById("dashboard-layout");
    const planBtn = document.getElementById("plan-btn");
    const btnText = planBtn.querySelector(".btn-text");
    const logStream = document.getElementById("log-stream");
    const consoleStatus = document.getElementById("console-status");
    
    const agentConsole = document.getElementById("agent-console-view");
    const itineraryView = document.getElementById("itinerary-view");
    const statsCard = document.getElementById("stats-card");

    // Form Values
    const startLoc = document.getElementById("start-loc").value.trim();
    const endLoc = document.getElementById("end-loc").value.trim();
    const stopovers = document.getElementById("stopovers").value.trim();
    const duration = document.getElementById("duration").value;
    const budget = document.getElementById("budget").value;
    const style = document.getElementById("style").value;
    const interests = document.getElementById("interests").value.trim();

    // Expand Layout
    layout.classList.add("itinerary-active");
    
    // Reset UI State
    agentConsole.style.display = "flex";
    itineraryView.style.display = "none";
    statsCard.classList.remove("visible");
    logStream.innerHTML = "";
    
    consoleStatus.textContent = "Swarm Active";
    consoleStatus.className = "status-badge active";
    
    planBtn.disabled = true;
    planBtn.classList.add("loading");
    btnText.textContent = "Architecting Trip...";

    if (routeLayer) {
        map.removeLayer(routeLayer);
        routeLayer = null;
    }
    markersGroup.clearLayers();

    // 1. Clear previous server state
    try {
        await fetch("/api/clear", { method: "POST" });
    } catch (err) {
        console.error("Failed to clear state", err);
    }

    // 2. Build Query
    let query = `Plan a road trip from ${startLoc} to ${endLoc}`;
    if (stopovers) query += ` stopping at ${stopovers}`;
    query += ` for a duration of ${duration} days. Budget tier: ${budget}. Travel style: ${style}. Primary interests: ${interests}.`;

    addLogEntry("system", "Initializing VagabondAI Sub-Agent Swarm...");
    addLogEntry("system", `Directing Swarm: "${query}"`);

    // 3. Connect SSE Stream
    const eventSource = new EventSource(`/api/plan?query=${encodeURIComponent(query)}`);
    let lastAuthor = "";
    let accumulatedText = "";

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "status") {
            addLogEntry("system", data.message);
        } else if (data.type === "error") {
            addLogEntry("system", `CRITICAL ERROR: ${data.message}`);
            finalizeExecution(false, data.message);
            eventSource.close();
        } else if (data.type === "event") {
            const author = data.author;
            
            if (author && author !== lastAuthor) {
                updateActiveAgentRoster(author);
                lastAuthor = author;
            }

            if (data.tool_calls && data.tool_calls.length > 0) {
                data.tool_calls.forEach(tool => {
                    addLogEntry(author, `Tool Execution: [${tool.name}] → ${JSON.stringify(tool.args)}`);
                });
            }

            if (data.text) {
                addLogEntry(author, data.text);
                // Accumulate text from agent responses to use as fallback itinerary
                accumulatedText += data.text + "\n";
            }
        }
    };

    eventSource.onerror = (err) => {
        console.log("SSE Stream closed or errored", err);
        eventSource.close();
        fetchFinalResults(accumulatedText);
    };
}

function updateActiveAgentRoster(agentName) {
    document.querySelectorAll(".agent-chip").forEach(item => {
        item.classList.remove("active");
    });
    
    const activeItem = document.getElementById(`roster-${agentName}`);
    if (activeItem) activeItem.classList.add("active");
}

function addLogEntry(author, text) {
    const stream = document.getElementById("log-stream");
    const entry = document.createElement("div");
    entry.className = `log-entry ${author}`;
    
    const formattedAuthor = author.replace("_agent", "");
    entry.innerHTML = `<span class="log-author">${formattedAuthor}</span> ${text}`;
    
    stream.appendChild(entry);
    stream.scrollTop = stream.scrollHeight;
}

async function fetchFinalResults(fallbackText) {
    let success = false;
    let errorMsg = "Unable to retrieve itinerary payload.";

    // Fetch Itinerary
    try {
        const resItinerary = await fetch("/api/itinerary");
        if (resItinerary.ok) {
            const data = await resItinerary.json();
            currentItineraryMarkdown = data.markdown;
        } else {
            // Fallback for server_cloudrun.py
            currentItineraryMarkdown = fallbackText;
        }
    } catch (err) {
        console.error("Itinerary Error", err);
        currentItineraryMarkdown = fallbackText;
    }
    
    if (currentItineraryMarkdown) {
        // Parse Markdown and wrap the final div
        let parsedHtml = marked.parse(currentItineraryMarkdown);
        // Close the final timeline-content div if it was opened
        if (parsedHtml.includes("timeline-content")) {
            parsedHtml += "</div></div>";
        }
        
        document.getElementById("itinerary-view").innerHTML = parsedHtml;
        success = true;
    }

    // Fetch Route
    try {
        const resRoute = await fetch("/api/route");
        if (resRoute.ok) {
            const routeData = await resRoute.json();
            plotRouteOnMap(routeData);
            
            // Update Stats
            document.getElementById("stat-dist").textContent = `${routeData.distance_km || 0} km`;
            document.getElementById("stat-time").textContent = `${routeData.duration_hours || 0} hrs`;
            document.getElementById("stats-card").classList.add("visible");
        }
    } catch (err) {
        console.error("Route Error (expected if using server_cloudrun.py)", err);
    }

    finalizeExecution(success, success ? null : errorMsg);
}

function plotRouteOnMap(routeData) {
    if (!routeData.route_geometry) return;

    // Premium Glow Path
    routeLayer = L.geoJSON(routeData.route_geometry, {
        style: {
            color: '#8b5cf6', // Purple base
            weight: 5,
            opacity: 0.9,
            className: 'route-path-glow'
        }
    }).addTo(map);

    map.fitBounds(routeLayer.getBounds(), { padding: [50, 50], animate: true, duration: 1.5 });

    const coords = routeData.route_geometry.coordinates;
    if (coords && coords.length > 0) {
        const start = coords[0];
        const end = coords[coords.length - 1];

        // Custom Marker Icons could be added here. For now standard markers.
        L.marker([start[1], start[0]]).addTo(markersGroup).bindPopup("<b>Departure</b>");
        L.marker([end[1], end[0]]).addTo(markersGroup).bindPopup("<b>Destination</b>");
    }
}

function finalizeExecution(success, errorMsg) {
    const planBtn = document.getElementById("plan-btn");
    const btnText = planBtn.querySelector(".btn-text");
    const consoleStatus = document.getElementById("console-status");
    
    planBtn.disabled = false;
    planBtn.classList.remove("loading");
    btnText.textContent = "Generate Master Itinerary";

    document.querySelectorAll(".agent-chip").forEach(item => item.classList.remove("active"));
    document.getElementById("roster-root_agent").classList.add("active");

    if (success) {
        consoleStatus.textContent = "Mission Accomplished";
        consoleStatus.className = "status-badge success";
        
        // Swap views
        setTimeout(() => {
            document.getElementById("agent-console-view").style.display = "none";
            const itView = document.getElementById("itinerary-view");
            itView.style.display = "block";
            itView.style.animation = "slideIn 0.5s ease-out forwards";
        }, 1500); // give user a moment to see completion

    } else {
        consoleStatus.textContent = "Execution Failed";
        consoleStatus.className = "status-badge";
        consoleStatus.style.background = "rgba(239, 68, 68, 0.15)";
        consoleStatus.style.color = "#f87171";
        consoleStatus.style.border = "1px solid rgba(239, 68, 68, 0.3)";
        addLogEntry("system", `Swarm Halted: ${errorMsg}`);
    }
}

function downloadItinerary() {
    if (!currentItineraryMarkdown) return;
    
    const blob = new Blob([currentItineraryMarkdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "VagabondAI_Itinerary.md";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
