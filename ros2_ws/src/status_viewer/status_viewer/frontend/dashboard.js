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
};

function formatLoopStatus(status) {
    const WIDTH = 66;
    const lines = [];
    function box_line(content = "", sep = "║") {
        return `${sep} ${content.padEnd(WIDTH - 2)} ${sep}`;
    }
    function separator(char = "═") { return `╠${char.repeat(WIDTH)}╣`; }
    function top() { return `╔${"═".repeat(WIDTH)}╗`; }
    function bottom() { return `╚${"═".repeat(WIDTH)}╝`; }

    lines.push(top());
    lines.push(box_line("THREADED LOOPER STATUS"));
    lines.push(separator());

    lines.push(box_line(`Total: ${status.total} | Running: ${status.running} | Paused: ${status.paused} | Stopped: ${status.stopped}`));
    lines.push(separator());

    for (const l of status.loops) {
        lines.push(box_line(`Loop ID: ${l.id}`));
        lines.push(box_line(`  State              : ${l.state}`));
        lines.push(box_line(`  Frequency          : ${l.freq.toFixed(3)} Hz`));
        lines.push(box_line(`  Thread Alive       : ${l.is_running}`));
        lines.push(box_line(`  Lock Type          : ${l.lock_type}`));
        lines.push(box_line(`  Exception Callback : ${l.exception_cb ? "YES" : "NO"}`));
        lines.push(separator());
    }

    if (lines.length) lines[lines.length - 1] = bottom();
    return lines.join("\n");
}

async function fetchStatus() {
    try {
        const resp = await fetch("/get_status_rest"); // We'll add this endpoint in FastAPI
        const data = await resp.json();

        // Update hardware metrics
        document.getElementById("cpu-text").textContent = data.cpu;
        document.getElementById("ram-text").textContent = data.memory;
        document.getElementById("uptime").textContent = data.uptime;
        document.getElementById("net-up").textContent = `${data.upload_rate} KB/s`;
        document.getElementById("net-down").textContent = `${data.download_rate} KB/s`;

        // Update loop ASCII table
        if (data.loops_json) {
            document.getElementById("loop-status").textContent = formatLoopStatus(data.loops_json);
        }
    } catch (e) {
        console.error("Failed to fetch status:", e);
    }
}

// Refresh every second
setInterval(fetchStatus, 1000);
