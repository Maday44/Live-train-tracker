document.addEventListener("DOMContentLoaded", () => {
    const eventsEl = document.getElementById("events");
    const templateEl = document.getElementById("event-row-template");

    async function loadRecent() {
        if (!eventsEl || !templateEl) return;

        try {
            const resp = await fetch("/events/recent");
            const data = await resp.json();

            eventsEl.innerHTML = "";

            if (!data || data.length === 0) {
                const emptyRow = document.createElement("tr");
                emptyRow.innerHTML = `<td colspan="4" class="empty text-center py-4">Waiting for trains near you :) ...</td>`;
                eventsEl.appendChild(emptyRow);
                return;
            }

            const groupedByDate = data.reduce((acc, ev) => {
                const dateKey = ev.date || "Today";
                if (!acc[dateKey]) acc[dateKey] = [];
                acc[dateKey].push(ev);
                return acc;
            }, {});

            Object.keys(groupedByDate).forEach(dateStr => {
                const dateHeaderRow = document.createElement("tr");
                dateHeaderRow.className = "table-light fw-bold";
                dateHeaderRow.innerHTML = `<td colspan="4" class="py-2">${dateStr}</td>`;
                eventsEl.appendChild(dateHeaderRow);


                groupedByDate[dateStr].forEach(ev => {
                    // Clone the HTML template
                    const clone = templateEl.content.cloneNode(true);
                    const row = clone.querySelector(".event-row");

                    // Timestamp formatting
                    let rawTimestamp = ev.timestamp;
                    if (rawTimestamp && !rawTimestamp.endsWith("Z") && !rawTimestamp.includes("+")) {
                        rawTimestamp += "Z";
                    }
                    const dateObj = new Date(rawTimestamp);
                    const formattedTime = !isNaN(dateObj.getTime())
                        ? dateObj.toLocaleTimeString("en-GB", {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                            timeZone: "Europe/London"
                        })
                        : (ev.time);

                    const fromStr = ev.from_berth;
                    const toStr = ev.to_berth; 

                    // Bind pure values directly to cloned template elements
                    clone.querySelector(".time").textContent = formattedTime;
                    clone.querySelector(".headcode").textContent = ev.headcode || "";

                    if (ev.origin && ev.destination) {
                        clone.querySelector(".route-title").textContent = `${ev.origin} → ${ev.destination}`;
                    } else {
                        clone.querySelector(".route-title").style.display = "none";
                        clone.querySelector(".route-unknown").style.display = "block";
                    }

                    clone.querySelector(".berth-subtext").textContent = `${fromStr} → ${toStr}`;

                    if (ev.rtt_service_uid) {
                        const link = clone.querySelector(".rtt-link");
                        link.href = `https://www.realtimetrains.co.uk/service/gb-nr:${ev.rtt_service_uid}/${ev.date}/detailed`;
                    } else {
                        clone.querySelector(".rtt-link").style.display = "none";
                        clone.querySelector(".rtt-none").style.display = "inline";
                    }

                    if (typeof showTrainDetails === "function") {
                        row.onclick = () => showTrainDetails(ev.headcode);
                    }

                    eventsEl.appendChild(clone);
                });
            });
        } catch (e) {
            console.error("Failed to render train events:", e);
        }
    }

    loadRecent();
    setInterval(loadRecent, 3000);
});