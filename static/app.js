let currentExportId = null;
let eventSource = null;

function toggleOptions() {
    const panel = document.getElementById("options-panel");
    const caret = document.getElementById("caret-icon");
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) {
        caret.style.transform = "rotate(180deg)";
    } else {
        caret.style.transform = "rotate(0deg)";
    }
}

function setPreset(url) {
    document.getElementById("target-url").value = url;
}

function updatePageVal(val) {
    document.getElementById("maxpages-val").innerText = val + " pages";
}

function clearConsole() {
    document.getElementById("console-logs").innerHTML = "";
}

function appendLog(message, level = "info") {
    const consoleLogs = document.getElementById("console-logs");
    const line = document.createElement("div");
    line.className = `log-line ${level}`;
    const timestamp = new Date().toLocaleTimeString();
    line.innerText = `[${timestamp}] ${message}`;
    consoleLogs.appendChild(line);
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

function updateRoutesList(routes) {
    const routesList = document.getElementById("routes-list");
    const routeCount = document.getElementById("route-count");
    
    if (!routes || routes.length === 0) {
        routesList.innerHTML = '<div class="route-placeholder">Discovered routes will appear here...</div>';
        routeCount.innerText = "0";
        return;
    }
    
    routeCount.innerText = routes.length;
    routesList.innerHTML = routes.map(r => {
        let file = r === "/" ? "index.html" : `${r.replace(/^\//, '')}/index.html`;
        return `
            <div class="route-item">
                <span class="route-path">${r}</span>
                <span class="route-file">&rarr; ${file}</span>
            </div>
        `;
    }).join("");
}

async function handleExportSubmit(event) {
    event.preventDefault();
    const urlInput = document.getElementById("target-url");
    const url = urlInput.value.strip ? urlInput.value.strip() : urlInput.value.trim();
    
    if (!url) return;
    
    const rewrite_links = document.getElementById("opt-rewrite").checked;
    const strip_telemetry = document.getElementById("opt-telemetry").checked;
    const hide_badge = document.getElementById("opt-badge").checked;
    const max_pages = document.getElementById("opt-maxpages").value;
    
    // UI state updates
    const exportBtn = document.getElementById("export-btn");
    exportBtn.disabled = true;
    exportBtn.querySelector(".btn-text").style.display = "none";
    exportBtn.querySelector(".btn-loader").style.display = "inline";
    
    document.getElementById("dashboard").style.display = "block";
    document.getElementById("results").style.display = "none";
    
    document.getElementById("status-title").innerText = "Discovering Framer Site Routes...";
    document.getElementById("status-dot").classList.add("pulsing");
    document.getElementById("progress-bar").style.width = "10%";
    clearConsole();
    updateRoutesList([]);

    appendLog(`Initiating export job for ${url}...`);

    try {
        const resp = await fetch("/api/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                url,
                rewrite_links,
                strip_telemetry,
                hide_badge,
                max_pages,
            }),
        });
        
        const data = await resp.json();
        if (data.error) {
            appendLog(`Error: ${data.error}`, "error");
            resetBtnState();
            return;
        }
        
        currentExportId = data.export_id;
        connectSSE(currentExportId);
        
    } catch (e) {
        appendLog(`Network Exception: ${e.message}. The server at http://127.0.0.1:5000 is not reachable. Make sure the black launcher console window is still open!`, "error");
        resetBtnState();
    }
}

function resetBtnState() {
    const exportBtn = document.getElementById("export-btn");
    exportBtn.disabled = false;
    exportBtn.querySelector(".btn-text").style.display = "inline";
    exportBtn.querySelector(".btn-loader").style.display = "none";
}

function connectSSE(exportId) {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource(`/api/stream/${exportId}`);

    eventSource.onmessage = function(e) {
        try {
            const data = JSON.parse(e.data);
            if (data.message) {
                appendLog(data.message, data.level || "info");
                
                if (data.message.includes("Discovered route")) {
                    document.getElementById("progress-bar").style.width = "30%";
                } else if (data.message.includes("Processing route")) {
                    document.getElementById("progress-bar").style.width = "70%";
                }
            }
        } catch (err) {}
    };

    eventSource.addEventListener("status", function(e) {
        const data = JSON.parse(e.data);
        if (data.status === "completed") {
            appendLog("Export Task Completed Successfully!", "info");
            document.getElementById("status-title").innerText = "Export Complete!";
            document.getElementById("status-dot").classList.remove("pulsing");
            document.getElementById("progress-bar").style.width = "100%";
            
            updateRoutesList(data.routes || []);
            showResults(exportId, data.files || []);
        } else if (data.status === "failed") {
            appendLog("Export Task Failed.", "error");
            document.getElementById("status-title").innerText = "Export Failed";
            document.getElementById("status-dot").classList.remove("pulsing");
        }
        
        resetBtnState();
        eventSource.close();
    });

    eventSource.onerror = function() {
        // Fallback polling check if SSE drops
        checkStatusFallback(exportId);
    };
}

async function checkStatusFallback(exportId) {
    try {
        const resp = await fetch(`/api/status/${exportId}`);
        const data = await resp.json();
        if (data.status === "completed") {
            showResults(exportId, data.exported_files || []);
            resetBtnState();
            if (eventSource) eventSource.close();
        }
    } catch (e) {}
}

async function showResults(exportId, files) {
    document.getElementById("results").style.display = "block";
    document.getElementById("res-page-count").innerText = files.length;
    document.getElementById("download-zip-btn").href = `/api/download/${exportId}`;
    
    // Load File Tree
    try {
        const resp = await fetch(`/api/tree/${exportId}`);
        const data = await resp.json();
        renderFileTree(exportId, data.tree || []);
        
        // Load default file (index.html)
        if (data.tree && data.tree.length > 0) {
            loadFileContent(exportId, data.tree[0].path);
        }
    } catch (e) {
        console.error("Error loading tree:", e);
    }
}

function renderFileTree(exportId, tree) {
    const fileTree = document.getElementById("file-tree");
    if (!tree || tree.length === 0) {
        fileTree.innerHTML = '<div class="route-placeholder">No files generated</div>';
        return;
    }
    
    fileTree.innerHTML = tree.map((item, idx) => {
        const icon = item.name.endsWith(".html") ? "📄" : "📁";
        return `
            <div class="tree-item ${idx === 0 ? 'active' : ''}" onclick="selectTreeFile(this, '${exportId}', '${item.path}')">
                <span>${icon}</span>
                <span>${item.path}</span>
            </div>
        `;
    }).join("");
}

function selectTreeFile(element, exportId, path) {
    document.querySelectorAll(".tree-item").forEach(el => el.classList.remove("active"));
    element.classList.add("active");
    loadFileContent(exportId, path);
}

async function loadFileContent(exportId, path) {
    document.getElementById("active-file-path").innerText = path;
    const codeContent = document.getElementById("code-content");
    codeContent.innerText = "Loading file source...";
    
    try {
        const resp = await fetch(`/api/file/${exportId}?path=${encodeURIComponent(path)}`);
        const data = await resp.json();
        if (data.content) {
            codeContent.innerText = data.content;
            document.getElementById("active-file-size").innerText = `${(data.content.length / 1024).toFixed(1)} KB`;
        } else {
            codeContent.innerText = "<!-- Unable to load file content -->";
        }
    } catch (e) {
        codeContent.innerText = `<!-- Exception loading file: ${e.message} -->`;
    }
}
