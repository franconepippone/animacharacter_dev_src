function formatBytes(bytes) {
    if (bytes >= 1024*1024)
        return Math.round(bytes / (1024*1024)) + " MB";
    else
        return Math.round(bytes / 1024) + " KB";
}

function formatRate(rate) {
    if (rate >= 1024)
        return Math.round(rate / 1024) + " MB/s";
    else
        return Math.round(rate) + " KB/s";
}

function getStateClass(state) {
    switch(state) {
        case 'RUNNING': return 'bg-success';
        case 'PAUSED': return 'bg-warning';
        case 'STOPPED': return 'bg-secondary';
        default: return 'bg-light text-dark';
    }
}

function getBoolBadge(value) {
    return value ? 'bg-success' : 'bg-danger';
}



const ws = new WebSocket("ws://" + location.host + "/ws");

ws.onopen = () => {
    const badge = document.getElementById("connection-badge");
    badge.className = "badge bg-success";
    badge.textContent = "Connected";
};

ws.onclose = () => {
    const badge = document.getElementById("connection-badge");
    badge.className = "badge bg-danger";
    badge.textContent = "Disconnected";
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    // CPU & RAM
    document.getElementById("cpu-text").textContent = data.cpu;
    document.getElementById("ram-text").textContent = data.memory;
    document.getElementById("cpu-bar").style.width = data.cpu + "%";
    document.getElementById("ram-bar").style.width = data.memory + "%";

    // System
    document.getElementById("uptime").textContent = data.uptime;
    document.getElementById("last-update").textContent = new Date().toLocaleTimeString();

    // Network
    document.getElementById("net-sent").textContent = formatBytes(data.bytes_sent);
    document.getElementById("net-recv").textContent = formatBytes(data.bytes_recv);
    document.getElementById("net-up").textContent = formatRate(data.upload_rate);
    document.getElementById("net-down").textContent = formatRate(data.download_rate);

    // Loops
    if (data.loops) {
        const summary = `Total: ${data.total} | Running: ${data.running} | Paused: ${data.paused} | Stopped: ${data.stopped}`;
        document.getElementById("loops-summary").textContent = summary;
        const tbody = document.getElementById("loops-tbody");
        tbody.innerHTML = "";
        for (const loop of data.loops) {
            const row = tbody.insertRow();
            
            row.insertCell().textContent = loop.id;
            
            const stateCell = row.insertCell();
            const stateBadge = document.createElement('span');
            stateBadge.className = 'badge ' + getStateClass(loop.state);
            stateBadge.textContent = loop.state;
            stateCell.appendChild(stateBadge);
            
            row.insertCell().textContent = `${loop.freq.toFixed(3)} Hz`;
            
            const aliveCell = row.insertCell();
            const aliveBadge = document.createElement('span');
            aliveBadge.className = 'badge ' + getBoolBadge(loop.is_running);
            aliveBadge.textContent = loop.is_running ? 'Yes' : 'No';
            aliveCell.appendChild(aliveBadge);
            
            row.insertCell().textContent = loop.lock_type;
            
            const excCell = row.insertCell();
            const excBadge = document.createElement('span');
            excBadge.className = 'badge ' + getBoolBadge(loop.exception_cb);
            excBadge.textContent = loop.exception_cb ? 'Yes' : 'No';
            excCell.appendChild(excBadge);
        }
    }
};

// Fallback periodic REST fetch every 2s
async function fetchStatus() {
    try {
        const resp = await fetch("/get_status_rest");
        const data = await resp.json();
        ws.onmessage({ data: JSON.stringify(data) });
    } catch (e) {
        console.error("Failed to fetch status:", e);
    }
}
setInterval(fetchStatus, 2000);
