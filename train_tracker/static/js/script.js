document.addEventListener("DOMContentLoaded", () => {
    const eventsEl = document.getElementById("events");
    const templateEl = document.getElementById("event-row-template");
    const headerTemplateEl = document.getElementById("date-header-template");

    // Helper function for pages
    function getPageQueryParam() {
        const urlParams = new URLSearchParams(window.location.search);
        const page = parseInt(urlParams.get("page"), 10);
        return isNaN(page) || page < 1 ? 1 : page;
    }

    async function loadRecent() {
        if (!eventsEl || !templateEl) return;

        const currentPage = getPageQueryParam();

        try {
            // Fetch json output
            const resp = await fetch(`/events/recent?page=${currentPage}`);
            if (!resp.ok) return;

            const data = await resp.json();
            const items = Array.isArray(data) ? data : (data.items || []);
            const countsMap = data.counts || {};

            eventsEl.innerHTML = "";

            // Group by date key
            const groupedByDate = items.reduce((acc, train) => {
                let dateKey = train.date;
                if (!dateKey && train.timestamp) {
                    dateKey = String(train.timestamp).split("T")[0].split(" ")[0];
                }
                dateKey = dateKey || "Today";

                if (!acc[dateKey]) acc[dateKey] = [];
                acc[dateKey].push(train);
                return acc;
            }, {});

            // Process each date group
            Object.keys(groupedByDate).forEach(dateStr => {
                const dayEvents = groupedByDate[dateStr];

                // count for trains
                const Count = countsMap[dateStr] !== undefined ? countsMap[dateStr] : dayEvents.length;


                if (headerTemplateEl) {
                    const headerClone = headerTemplateEl.content.cloneNode(true);
                    const dateSpan = headerClone.querySelector(".date-label");
                    const countSpan = headerClone.querySelector(".count-label");

                    if (dateSpan) dateSpan.textContent = dateStr;
                    if (countSpan) countSpan.textContent = `${Count} Trains`;
                    eventsEl.appendChild(headerClone);
                } else {
                    const dateHeaderRow = document.createElement("tr");
                    dateHeaderRow.className = "table-light fw-bold";
                    dateHeaderRow.innerHTML = `
                        <td colspan="4" class="py-2 px-3 fs-6 border-top">
                            <div class="d-flex justify-content-between align-items-center">
                                <span class="text-secondary small">${dateStr}</span>
                                <span>
                                    <i class="bi bi-train-front "> </i>${Count} Trains
                                </span>
                            </div>
                        </td>`;
                    eventsEl.appendChild(dateHeaderRow);
                }

                dayEvents.forEach(train => {
                    const clone = templateEl.content.cloneNode(true);
                    const row = clone.querySelector(".event-row");

                    let rawTimestamp = train.timestamp;
                    if (rawTimestamp && typeof rawTimestamp === "string" && !rawTimestamp.endsWith("Z") && !rawTimestamp.includes("+")) {
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
                        : (train.time || "");

                    const fromStr = train.from_berth || "";
                    const toStr = train.to_berth || "";

                    // Populate the rows
                    const timeEl = clone.querySelector(".time");
                    if (timeEl) timeEl.textContent = formattedTime;

                    const headcodeEl = clone.querySelector(".headcode");
                    if (headcodeEl) headcodeEl.textContent = train.headcode || "";

                    const routeTitleEl = clone.querySelector(".route-title");
                    const routeUnknownEl = clone.querySelector(".route-unknown");

                    if (train.origin && train.destination) {
                        if (routeTitleEl) {
                            routeTitleEl.textContent = `${train.origin} → ${train.destination}`;
                            routeTitleEl.style.display = "block";
                        }
                        if (routeUnknownEl) routeUnknownEl.style.display = "none";
                    } else if (train.origin) {
                        if (routeTitleEl) {
                            routeTitleEl.textContent = `${train.origin} → Unknown`;
                            routeTitleEl.style.display = "block";
                        }
                        if (routeUnknownEl) routeUnknownEl.style.display = "none";
                    } else if (train.destination) {
                        if (routeTitleEl) {
                            routeTitleEl.textContent = `Unknown → ${train.destination}`;
                            routeTitleEl.style.display = "block";
                        }
                        if (routeUnknownEl) routeUnknownEl.style.display = "none";
                    } else {
                        if (routeTitleEl) routeTitleEl.style.display = "none";
                        if (routeUnknownEl) routeUnknownEl.style.display = "block";
                    }

                    const berthSubtextEl = clone.querySelector(".berth-subtext");
                    if (berthSubtextEl) {
                        berthSubtextEl.textContent = `${fromStr} → ${toStr}`;
                    }

                    const rttLinkEl = clone.querySelector(".rtt-link");
                    const rttNoneEl = clone.querySelector(".rtt-none");

                    // RTT Link assignment logic
                    if (train.rtt_service_uid) {
                        // UID match -> Show clickable RTT button
                        if (rttLinkEl) {
                            rttLinkEl.href = `https://www.realtimetrains.co.uk/service/gb-nr:${train.rtt_service_uid}/${dateStr}/detailed`;
                            rttLinkEl.style.display = "inline-block";
                        }
                        if (rttNoneEl) rttNoneEl.style.display = "none";
                    } else {
                        // No UID found (Unmatched service) -> Hide RTT button and show N/A
                        if (rttLinkEl) rttLinkEl.style.display = "none";
                        if (rttNoneEl) rttNoneEl.style.display = "inline";
                    }

                    if (row && typeof showTrainDetails === "function" && train.headcode) {
                        row.onclick = () => showTrainDetails(train.headcode);
                    }

                    eventsEl.appendChild(clone);
                });
            });
        } catch (e) {
            console.error("Failed to render train events:", e);
        }
    }

    // refresh the page after 4 sec and updates 
    loadRecent();
    setInterval(loadRecent, 4000);
});