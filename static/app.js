// Initialize variables
let map;
let routeGeoJsonLayer = null;
let markersGroup = null;
let currentItineraryMarkdown = "";

// Initialize Leaflet Map on load
document.addEventListener("DOMContentLoaded", () => {
    // Standard coordinates centering USA
    map = L.map('map').setView([37.8, -96.9], 4);
    
    // Beautiful CartoDB Dark Matter Tile Layer (free, no key required)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    markersGroup = L.layerGroup().addTo(map);

    // Attach Event Listeners
    document.getElementById("trip-form").addEventListener("submit", handleFormSubmit);
    document.getElementById("download-btn").addEventListener("click", downloadItinerary);
});

// Submit Form Handler
async function handleFormSubmit(e) {
    e.preventDefault();
    
    // UI Elements
    const planBtn = document.getElementById("plan-btn");
    const btnLoader = planBtn.querySelector(".btn-loader");
    const btnText = planBtn.querySelector(".btn-text");
    const consoleLogs = document.getElementById("console-logs");
    const consoleStatus = document.getElementById("console-status");
    const itineraryCard = document.getElementById("itinerary-card");

    // Get Form Values
    const startLoc = document.getElementById("start-loc").value.trim();
    const endLoc = document.getElementById("end-loc").value.trim();
    const stopovers = document.getElementById("stopovers").value.trim();
    const duration = document.getElementById("duration").value;
    const budget = document.getElementById("budget").value;
    const style = document.getElementById("style").value;
    const interests = document.getElementById("interests").value.trim();

    // Reset UI State
    itineraryCard.classList.add("hidden");
    consoleLogs.innerHTML = "";
    consoleStatus.textContent = "Running";
    consoleStatus.className = "console-status-badge console-badge running";
    planBtn.disabled = true;
    btnLoader.classList.remove("hidden");
    btnText.textContent = "Planning Trip...";

    if (routeGeoJsonLayer) {
        map.removeLayer(routeGeoJsonLayer);
        routeGeoJsonLayer = null;
    }
    markersGroup.clearLayers();

    // 1. Clear previous server state
    try {
        await fetch("/api/clear", { method: "POST" });
    } catch (err) {
        console.error("Failed to clear previous trip state", err);
    }

    // 2. Build the query prompt for ADK Agent
    let query = `Plan a road trip from ${startLoc} to ${endLoc}`;
    if (stopovers) {
        query += ` stopping at ${stopovers}`;
    }
    query += ` for a duration of ${duration} days. Budget tier: ${budget}. Travel style: ${style}. Primary interests: ${interests}.`;

    addLogEntry("system", `Constructed Query: "${query}"`);
    addLogEntry("system", "Starting multi-agent execution pipeline...");

    // 3. Start SSE Event Stream
    const eventSource = new EventSource(`/api/plan?query=${encodeURIComponent(query)}`);
    
    let lastAuthor = "";

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "status") {
            addLogEntry("system", data.message);
        } else if (data.type === "error") {
            addLogEntry("system", `ERROR: ${data.message}`);
            finalizeExecution(false, data.message);
            eventSource.close();
        } else if (data.type === "event") {
            const author = data.author;
            
            // Highlight current active agent in the roster
            if (author && author !== lastAuthor) {
                updateActiveAgentRoster(author);
                lastAuthor = author;
            }

            // Print Tool Calls if any
            if (data.tool_calls && data.tool_calls.length > 0) {
                data.tool_calls.forEach(tool => {
                    addLogEntry(author, `Calling tool <span class="log-tool">${tool.name}</span> with args: ${JSON.stringify(tool.args)}`);
                });
            }

            // Print text message
            if (data.text) {
                addLogEntry(author, data.text);
            }
        }
    };

    eventSource.onerror = (err) => {
        console.error("SSE stream error", err);
        addLogEntry("system", "Event source connection closed or finished.");
        eventSource.close();
        
        // Try fetching final output (route + itinerary)
        fetchFinalResults();
    };
}

// Update Active Agent Highlight
function updateActiveAgentRoster(agentName) {
    // Remove active class from all
    document.querySelectorAll(".roster-item").forEach(item => {
        item.classList.remove("active-agent");
    });
    
    // Add active class to matching
    const activeItem = document.getElementById(`roster-${agentName}`);
    if (activeItem) {
        activeItem.classList.add("active-agent");
    }
}

// Add Log to Console
function addLogEntry(author, text) {
    const consoleLogs = document.getElementById("console-logs");
    const entry = document.createElement("div");
    entry.className = "log-entry";
    
    const formattedAuthor = author.replace("_agent", "");
    entry.innerHTML = `<span class="log-author ${author}">${formattedAuthor}</span> ${text}`;
    
    consoleLogs.appendChild(entry);
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

// Fetch route and itinerary once planning concludes
async function fetchFinalResults() {
    let success = false;
    let errorMsg = "Unable to retrieve itinerary data.";

    // Retrieve Itinerary
    try {
        const resItinerary = await fetch("/api/itinerary");
        if (resItinerary.ok) {
            const data = await resItinerary.json();
            currentItineraryMarkdown = data.markdown;
            
            // Render Markdown
            document.getElementById("itinerary-content").innerHTML = marked.parse(data.markdown);
            document.getElementById("itinerary-card").classList.remove("hidden");
            success = true;
        }
    } catch (err) {
        console.error("Error reading itinerary", err);
    }

    // Retrieve Route data for map
    try {
        const resRoute = await fetch("/api/route");
        if (resRoute.ok) {
            const routeData = await resRoute.json();
            plotRouteOnMap(routeData);
            updateTripStats(routeData);
        }
    } catch (err) {
        console.error("Error reading route details", err);
    }

    finalizeExecution(success, success ? null : errorMsg);
}

// Plot route on Leaflet Map
function plotRouteOnMap(routeData) {
    if (!routeData.route_geometry) return;

    // Plot Driving Path using geojson
    routeGeoJsonLayer = L.geoJSON(routeData.route_geometry, {
        style: {
            color: '#6366f1', // Indigo glow line
            weight: 6,
            opacity: 0.8
        }
    }).addTo(map);

    // Zoom map to fit route bounds
    map.fitBounds(routeGeoJsonLayer.getBounds(), { padding: [40, 40] });

    // Place Markers for Waypoints
    const coords = routeData.route_geometry.coordinates;
    if (coords && coords.length > 0) {
        const startCoord = coords[0];
        const endCoord = coords[coords.length - 1];

        // Start point marker
        L.marker([startCoord[1], startCoord[0]])
            .addTo(markersGroup)
            .bindPopup("<b>Start Location</b>")
            .openPopup();

        // End point marker
        L.marker([endCoord[1], endCoord[0]])
            .addTo(markersGroup)
            .bindPopup("<b>Destination Location</b>");
    }
}

// Update Trip Stats Row
function updateTripStats(routeData) {
    const statsContainer = document.getElementById("trip-stats");
    statsContainer.innerHTML = `
        <div class="stat-box">
            <span class="stat-val">${routeData.distance_km} km</span>
            <span class="stat-lbl">Driving Distance</span>
        </div>
        <div class="stat-box">
            <span class="stat-val">${routeData.duration_hours} hrs</span>
            <span class="stat-lbl">Est. Driving Time</span>
        </div>
        <div class="stat-box">
            <span class="stat-val">${document.getElementById("duration").value} Days</span>
            <span class="stat-lbl">Trip Duration</span>
        </div>
    `;
}

// Finalize Form & Button UI
function finalizeExecution(success, errorMsg) {
    const planBtn = document.getElementById("plan-btn");
    const btnLoader = planBtn.querySelector(".btn-loader");
    const btnText = planBtn.querySelector(".btn-text");
    const consoleStatus = document.getElementById("console-status");

    planBtn.disabled = false;
    btnLoader.classList.add("hidden");
    btnText.textContent = "Generate Itinerary";

    // Reset Roster highlights
    document.querySelectorAll(".roster-item").forEach(item => {
        item.classList.remove("active-agent");
    });
    
    // Highlight root coordinator again
    document.getElementById("roster-root_agent").classList.add("active-agent");

    if (success) {
        consoleStatus.textContent = "Success";
        consoleStatus.className = "console-status-badge console-badge";
        consoleStatus.style.background = "rgba(16, 185, 129, 0.2)";
        consoleStatus.style.color = "#34d399";
        consoleStatus.style.border = "1px solid rgba(16, 185, 129, 0.4)";
        addLogEntry("system", "Pipeline completed successfully. View itinerary below.");
    } else {
        consoleStatus.textContent = "Error";
        consoleStatus.className = "console-status-badge console-badge";
        consoleStatus.style.background = "rgba(239, 68, 68, 0.2)";
        consoleStatus.style.color = "#f87171";
        consoleStatus.style.border = "1px solid rgba(239, 68, 68, 0.4)";
        addLogEntry("system", `Pipeline halted: ${errorMsg}`);
    }
}

// Download markdown file
function downloadItinerary() {
    if (!currentItineraryMarkdown) return;
    
    const blob = new Blob([currentItineraryMarkdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "itinerary.md";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
