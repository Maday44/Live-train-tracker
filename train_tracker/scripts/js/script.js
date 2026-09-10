const eventsEl = document.getElementById("events");

async function loadRecent() {
    try {
        const resp = await fetch("/events/recent");
        const data = await resp.json();


        eventsEl.innerHTML = "";
        data.forEach(ev => {
            const row = document.createElement("div");
            row.className = "event-row";
            row.innerHTML = `
            <div class="time">${ev.time}</div>
            <div class="headcode">${ev.headcode}</div>
            <div class="movement">${ev.from_berth} &rarr; ${ev.to_berth}</div>
            <div class="area">[${ev.area}]</div>
          `;
            eventsEl.appendChild(row);
        });
    } catch (e) {
        console.error("Failed to fetch train events:", e);
    }
}

loadRecent();
setInterval(loadRecent, 5000);
