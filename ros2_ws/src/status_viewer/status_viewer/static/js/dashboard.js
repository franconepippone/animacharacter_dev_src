const protocol = location.protocol === "https:" ? "wss://" : "ws://";
const ws = new WebSocket(protocol + location.host + "/ws");

let pieChart = new Chart(document.getElementById("pieChart"), {
    type: 'pie',
    data: {
        labels: ['CPU', 'Memory'],
        datasets: [{
            data: [0, 0]
        }]
    }
});

let history = [];

let lineChart = new Chart(document.getElementById("lineChart"), {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Throughput',
            data: []
        }]
    }
});

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);

    document.getElementById("cpuBar").style.width = data.cpu + "%";
    document.getElementById("cpuBar").innerText = data.cpu + "%";

    document.getElementById("memoryBar").style.width = data.memory + "%";
    document.getElementById("memoryBar").innerText = data.memory + "%";

    document.getElementById("tasks").innerText = data.tasks;
    document.getElementById("errors").innerText = data.errors;
    document.getElementById("throughput").innerText = data.throughput;

    pieChart.data.datasets[0].data = [data.cpu, data.memory];
    pieChart.update();

    history.push(data.throughput);
    if (history.length > 20) history.shift();

    lineChart.data.labels = Array.from({length: history.length}, (_, i) => i);
    lineChart.data.datasets[0].data = history;
    lineChart.update();
};
