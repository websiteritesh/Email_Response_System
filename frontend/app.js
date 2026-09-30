const API = "";
let allEmails = [];
let currentFilter = "All";

// Escape text before putting it into the page, so email content can never inject HTML/scripts.
function esc(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

async function loadEmails() {
    try {
        const res = await fetch(`${API}/emails`);
        const data = await res.json();
        allEmails = data.emails || []; // the database already returns newest first
    } catch (e) { /* server not reachable yet — start empty */ }
    renderEmails();
}

async function processEmail() {
    const emailText = document.getElementById("emailInput").value.trim();
    const sender = document.getElementById("senderInput").value.trim() || "customer@example.com";
    const btn = document.getElementById("processBtn");
    const msg = document.getElementById("processingMsg");

    if (!emailText) { alert("Please paste a customer email first."); return; }

    btn.disabled = true; btn.textContent = "Processing…";
    msg.classList.add("on");

    try {
        const res = await fetch(`${API}/process`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email_text: emailText, sender: sender })
        });
        if (!res.ok) throw new Error("Server error");
        const data = await res.json();
        allEmails.unshift(data);
        document.getElementById("emailInput").value = "";
        renderEmails();
    } catch (e) {
        alert("Couldn't process the email. Make sure uvicorn is running, then try again.");
    }

    btn.disabled = false; btn.textContent = "Process email";
    msg.classList.remove("on");
}

async function updateStatus(emailId, status) {
    try {
        await fetch(`${API}/update`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email_id: emailId, status: status })
        });
        const email = allEmails.find(e => e.id === emailId);
        if (email) email.status = status;
        renderEmails();
    } catch (e) { alert("Couldn't update the status."); }
}

async function clearAll() {
    if (!allEmails.length) return;
    if (!confirm("Remove all emails from the dashboard?")) return;
    try { await fetch(`${API}/clear`, { method: "DELETE" }); } catch (e) {}
    allEmails = [];
    renderEmails();
}

document.getElementById("tabs").addEventListener("click", (ev) => {
    const tab = ev.target.closest(".tab");
    if (!tab) return;
    currentFilter = tab.dataset.filter;
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === tab));
    renderEmails();
});

function pick(value, allowed, fallback) {
    const v = String(value || "").toLowerCase();
    return allowed.includes(v) ? v : fallback;
}

function renderEmails() {
    document.getElementById("totalCount").textContent = allEmails.length;
    document.getElementById("pendingCount").textContent = allEmails.filter(e => e.status === "Pending").length;
    document.getElementById("approvedCount").textContent = allEmails.filter(e => e.status === "Approved").length;

    const shown = currentFilter === "All" ? allEmails : allEmails.filter(e => e.status === currentFilter);
    const list = document.getElementById("emailList");

    if (!shown.length) {
        list.innerHTML = `<div class="empty"><span class="serif">${allEmails.length ? "Nothing here" : "Inbox is empty"}</span>${
            allEmails.length ? "No emails match this filter." : "Paste a customer email on the left to get started."}</div>`;
        return;
    }

    list.innerHTML = shown.map(email => {
        const urg = pick(email.urgency, ["high", "medium", "low"], "medium");
        const sent = pick(email.sentiment, ["angry", "frustrated", "neutral", "happy"], "neutral");
        const st = pick(email.status, ["pending", "approved", "rejected"], "pending");
        return `
        <article class="card u-${urg}">
            <div class="card-top">
                <span class="sender">${esc(email.sender)}</span>
                <span class="time">${esc(email.timestamp)}</span>
            </div>
            <div class="chips">
                <span class="chip u-${urg}">${esc(email.urgency)} urgency</span>
                <span class="chip">${esc(email.category)}</span>
                <span class="chip s-${sent}">${esc(email.sentiment)}</span>
                <span class="chip st-${st}">${esc(email.status)}</span>
            </div>
            <div class="summary">${esc(email.summary)}</div>
            <div class="label">Customer wrote</div>
            <div class="original">${esc(email.original_email)}</div>
            <div class="label">Suggested reply</div>
            <div class="reply">${esc(email.draft_reply)}</div>
            ${email.status === "Pending" ? `
            <div class="actions">
                <button class="btn btn-approve" onclick="updateStatus('${esc(email.id)}', 'Approved')">Approve reply</button>
                <button class="btn btn-reject" onclick="updateStatus('${esc(email.id)}', 'Rejected')">Reject</button>
            </div>` : `<div class="done-note">Reply ${esc(String(email.status).toLowerCase())}.</div>`}
        </article>`;
    }).join("");
}

loadEmails();