document.addEventListener("DOMContentLoaded", () => {
    const eventsEl = document.getElementById("events");

    async function loadRecent() {
        if (!eventsEl) return;

        try {
            const resp = await fetch("/events/recent");
            const data = await resp.json();

            eventsEl.innerHTML = "";

            if (!data || data.length === 0) {
                eventsEl.innerHTML = `<div class="empty">Waiting for live train events...</div>`;
                return;
            }

            data.forEach(ev => {
                // Handle fallback if station names are missing or empty
                const fromLoc = ev.from_station || (ev.from_berth ? `Berth ${ev.from_berth}` : "N/A");
                const toLoc = ev.to_station || (ev.to_berth ? `Berth ${ev.to_berth}` : "N/A");

                const row = document.createElement("div");
                row.className = "event-row";
                row.innerHTML = `
                    <div class="time">${ev.time}</div>
                    <div class="headcode">${ev.headcode}</div>
                    <div class="movement">${fromLoc} &rarr; ${toLoc}</div>
                    <div class="area">[${ev.area}]</div>
                `;
                eventsEl.appendChild(row);
            });
        } catch (e) {
            console.error("Failed to render train events:", e);
        }
    }

    loadRecent();
    setInterval(loadRecent, 3000);
});