// Journey Planner - App Logic

// Global state
let map = null;
let geocoder = null;
let markers = [];
let rawMarkdown = "";
let isPlanning = false;
let stopCount = 0;

// Initialize on Load
document.addEventListener("DOMContentLoaded", async () => {
    initThemeToggle();
    
    // Fetch Maps Config
    try {
        const res = await fetch("/api/config");
        const data = await res.json();
        if (data.maps_api_key) {
            window.__MAPS_KEY__ = data.maps_api_key;
            const script = document.createElement("script");
            script.src = `https://maps.googleapis.com/maps/api/js?key=${data.maps_api_key}&callback=initMap`;
            script.async = true;
            script.defer = true;
            document.head.appendChild(script);
        } else {
            console.warn("No Google Maps API Key provided in config.");
        }
    } catch (err) {
        console.error("Failed to load map config", err);
    }

    // Attach form listener
    document.getElementById("trip-search-form").addEventListener("submit", handleSearchSubmit);
});

// Theme Toggle Logic
function initThemeToggle() {
    const toggleBtn = document.getElementById("theme-toggle");
    const htmlEl = document.documentElement;
    
    // Check local storage or system preference
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
        
        // Update map style if loaded
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
            { featureType: "administrative.locality", elementType: "labels.text.fill", stylers: [{ color: "#d96c4d" }] },
            { featureType: "poi", elementType: "labels.text.fill", stylers: [{ color: "#6d93b3" }] },
            { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#3d7980" }] },
            { featureType: "road", elementType: "geometry", stylers: [{ color: "#3a3b38" }] },
            { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#212a37" }] },
            { featureType: "water", elementType: "geometry", stylers: [{ color: "#1a1c1e" }] }
        ];
    } else {
        return [
            { elementType: "geometry", stylers: [{ color: "#f9f6f0" }] },
            { elementType: "labels.text.stroke", stylers: [{ color: "#ffffff" }] },
            { elementType: "labels.text.fill", stylers: [{ color: "#718096" }] },
            { featureType: "administrative.locality", elementType: "labels.text.fill", stylers: [{ color: "#e27d60" }] },
            { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#e8dcc4" }] },
            { featureType: "water", elementType: "geometry", stylers: [{ color: "#cbd5e0" }] }
        ];
    }
}

// Form Submission & SSE Streaming
async function handleSearchSubmit(e) {
    e.preventDefault();
    if (isPlanning) return;
    
    const query = document.getElementById("trip-query").value.trim();
    if (!query) return;

    // Transition UI
    isPlanning = true;
    document.getElementById("hero-section").classList.add("collapsed");
    document.getElementById("dashboard").classList.remove("hidden");
    
    const btn = document.getElementById("search-btn");
    btn.querySelector(".btn-text").textContent = "Planning...";
    btn.querySelector(".loader").classList.remove("hidden");
    btn.disabled = true;

    // Reset State
    rawMarkdown = "";
    document.getElementById("itinerary-feed").innerHTML = "";
    document.getElementById("timeline-nav").innerHTML = "";
    document.getElementById("agent-message").textContent = "Architecting your journey...";
    document.getElementById("agent-indicator").classList.add("active");
    stopCount = 0;
    
    if (markers.length > 0) {
        markers.forEach(m => m.setMap(null));
        markers = [];
    }

    // Add initial skeleton loaders
    showSkeletons(3);

    // Start SSE
    try {
        await fetch("/api/clear", { method: "POST" });
    } catch (e) { /* ignore */ }

    const eventSource = new EventSource(`/api/plan?query=${encodeURIComponent(query)}`);

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "status") {
            document.getElementById("agent-message").textContent = data.message;
        } else if (data.type === "error") {
            document.getElementById("agent-message").textContent = "Error: " + data.message;
            document.getElementById("agent-indicator").classList.remove("active");
            document.getElementById("agent-indicator").style.background = "#e53e3e";
            finalizePlanning();
            eventSource.close();
        } else if (data.type === "event" && data.text) {
            removeSkeletons();
            handleStreamText(data.text);
        }
    };

    eventSource.onerror = (err) => {
        eventSource.close();
        document.getElementById("agent-message").textContent = "Itinerary Complete";
        document.getElementById("agent-indicator").classList.remove("active");
        finalizePlanning();
    };
}

function finalizePlanning() {
    isPlanning = false;
    const btn = document.getElementById("search-btn");
    btn.querySelector(".btn-text").textContent = "Inspire Me";
    btn.querySelector(".loader").classList.add("hidden");
    btn.disabled = false;
    removeSkeletons();
}

// Inline Markdown Streaming Parser
function handleStreamText(newText) {
    rawMarkdown += newText;
    
    // Split by double newlines to get distinct blocks
    let blocks = rawMarkdown.split('\n\n');
    const feed = document.getElementById("itinerary-feed");
    
    blocks.forEach((blockText, index) => {
        if (!blockText.trim()) return;
        
        let blockId = `block-${index}`;
        let el = document.getElementById(blockId);
        let parsedHtml = parseBlock(blockText.trim());
        
        if (!el) {
            // New block
            el = document.createElement('div');
            el.id = blockId;
            el.innerHTML = parsedHtml;
            feed.appendChild(el);
            
            // Attempt to geocode and map this block if it represents a location
            extractAndGeocodeLocation(blockText.trim());
        } else {
            // Update existing block only if the text changed
            // This prevents reloading images while a block is streaming
            if (el.getAttribute('data-raw') !== blockText) {
                // If the block is huge and still streaming, we just update it.
                // It might cause minor flicker on the LAST block, which is unavoidable
                // without complex DOM diffing, but acceptable for the streaming effect.
                el.innerHTML = parsedHtml;
            }
        }
        el.setAttribute('data-raw', blockText);
    });
    
    // Auto-scroll logic if near bottom
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
        window.scrollTo(0, document.body.scrollHeight);
    }
}

// Custom Markdown to HTML Block Parser
function parseBlock(text) {
    // 1. Day Headers
    let match = text.match(/^##\s*(Day\s*\d+.*)/i) || text.match(/^(Day\s*\d+.*)/i);
    // Be careful not to match simple sentences starting with Day
    if (match && text.length < 100 && (text.startsWith("##") || text.includes(":"))) {
        const title = match[1].replace(/\*\*/g, '');
        return `<div class="card day-card"><h2>${title}</h2></div>`;
    }
    
    // 2. Hotel / Accommodation
    match = text.match(/\*\*(Hotel|Accommodation):\*\*\s*(.*)/i) || text.match(/^(Hotel|Accommodation):\s*(.*)/i);
    if (match) {
        const label = match[1];
        const namePart = match[2].split('\n')[0].replace(/\*\*/g, '').trim();
        // Remove markdown artifacts for the image query
        const imgQuery = namePart.replace(/[^a-zA-Z0-9 ]/g, '');
        const imgUrl = `https://source.unsplash.com/400x300/?${encodeURIComponent(imgQuery + ' hotel')}`;
        
        // Extract rest of text for description
        let desc = text.replace(match[0], '').replace(/\*\*/g, '').trim();
        if (desc.startsWith('-')) desc = desc.substring(1).trim();
        
        return `
        <div class="card content-card">
            <div class="card-image" style="background-image: url('${imgUrl}')"></div>
            <div class="card-body">
                <div class="card-label">${label}</div>
                <h3 class="card-title">${namePart}</h3>
                <div class="card-meta"><span class="stars">★★★★☆</span> <span>(Estimated)</span></div>
                <div class="card-desc">${desc.substring(0, 150)}${desc.length > 150 ? '...' : ''}</div>
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
        <div class="card content-card">
            <div class="card-image" style="background-image: url('${imgUrl}')"></div>
            <div class="card-body">
                <div class="card-label">${label}</div>
                <h3 class="card-title">${namePart}</h3>
                <div class="card-desc">${desc.substring(0, 150)}${desc.length > 150 ? '...' : ''}</div>
            </div>
        </div>`;
    }
    
    // 4. Drive Segment
    match = text.match(/\*\*(Drive|Distance|Route):\*\*\s*(.*)/i) || text.match(/^(Drive|Distance|Route):\s*(.*)/i);
    if (match) {
        const desc = match[2].replace(/\*\*/g, '').split('\n')[0];
        return `
        <div class="drive-card">
            <div class="drive-icon">🚙</div>
            <div class="drive-details">
                <div class="drive-title">Drive Segment</div>
                <div class="drive-meta">${desc}</div>
            </div>
        </div>`;
    }
    
    // 5. Standard Text / Bullet Points
    let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formattedText = formattedText.replace(/\n/g, '<br>');
    
    // Simple bullet list styling if it looks like a list
    if (formattedText.includes('- ')) {
        formattedText = formattedText.replace(/- (.*?)<br>/g, '<li>$1</li>');
        formattedText = formattedText.replace(/- (.*?)$/g, '<li>$1</li>');
        if (formattedText.includes('<li>')) {
            formattedText = `<ul>${formattedText}</ul>`;
        }
    }
    
    return `<div class="text-block"><p>${formattedText}</p></div>`;
}

// Map Extraction Logic
function extractAndGeocodeLocation(blockText) {
    if (!geocoder || !map) return;
    
    let locationMatch = blockText.match(/\*\*(Hotel|Accommodation|Activity|Tour|Stop):\*\*\s*(.*?)(?:\n|$)/i) || 
                        blockText.match(/^(Hotel|Accommodation|Activity|Tour|Stop):\s*(.*?)(?:\n|$)/i);
                        
    if (locationMatch) {
        let name = locationMatch[2].replace(/\*\*/g, '').trim();
        // Remove trailing descriptors often generated by LLM
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
                
                // Adjust bounds
                if (markers.length > 1) {
                    let bounds = new google.maps.LatLngBounds();
                    markers.forEach(m => bounds.extend(m.getPosition()));
                    map.fitBounds(bounds);
                } else {
                    map.setCenter(loc);
                    map.setZoom(10);
                }
                
                addSidebarNav(name);
            }
        });
    }
}

function addSidebarNav(name) {
    stopCount++;
    const nav = document.getElementById("timeline-nav");
    const item = document.createElement("div");
    item.className = "nav-item";
    item.innerHTML = `<div class="nav-dot"></div> Stop ${stopCount}: ${name}`;
    nav.appendChild(item);
}

function showSkeletons(count) {
    const feed = document.getElementById("itinerary-feed");
    for (let i = 0; i < count; i++) {
        const skel = document.createElement("div");
        skel.className = "skeleton skel-placeholder";
        skel.innerHTML = `
            <div class="skel-line title"></div>
            <div class="skel-line full"></div>
            <div class="skel-line short"></div>
        `;
        feed.appendChild(skel);
    }
}

function removeSkeletons() {
    document.querySelectorAll(".skel-placeholder").forEach(el => el.remove());
}
