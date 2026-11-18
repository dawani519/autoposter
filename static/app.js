// AutoPoster dashboard. All text is inserted with textContent, never innerHTML,
// so AI-written or user-entered content can't inject markup.

const STATUS_LABELS = {
    pending_approval: "Awaiting approval",
    scheduled: "Scheduled",
    posting: "Publishing",
    posted: "Posted",
    failed: "Failed",
    rejected: "Rejected",
};

const state = { niches: [], accounts: [], platforms: {}, postFilter: "" };

// ---------- helpers ----------

async function api(path, options = {}) {
    const resp = await fetch(`/api${path}`, {
        method: options.method || "GET",
        headers: options.body ? { "Content-Type": "application/json" } : {},
        body: options.body ? JSON.stringify(options.body) : undefined,
        credentials: "same-origin",
    });
    if (resp.status === 204) return null;
    let data = null;
    try { data = await resp.json(); } catch (e) { /* not JSON */ }
    if (!resp.ok) throw new Error((data && data.error) || `Request failed (${resp.status})`);
    return data;
}

function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
        if (value === undefined || value === null || value === false) continue;
        if (key === "class") node.className = value;
        else if (key === "dataset") Object.assign(node.dataset, value);
        else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
        else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) {
        if (child === null || child === undefined || child === false) continue;
        node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
}

function fmtTime(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function toLocalInput(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

let toastTimer;
function toast(message, kind = "success") {
    const box = document.getElementById("toast");
    box.textContent = message;
    box.className = `result-message ${kind}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { box.className = "result-message"; }, 6000);
}

async function run(action, successMessage) {
    try {
        const result = await action();
        if (successMessage) toast(typeof successMessage === "function" ? successMessage(result) : successMessage);
        return result;
    } catch (err) {
        toast(err.message, "error");
        return undefined;
    }
}

function showForm(id, show = true) {
    const card = document.getElementById(id);
    card.hidden = !show;
    if (show) card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function emptyRow(table, colspan, text) {
    table.replaceChildren(el("tr", {}, el("td", { colspan, class: "empty" }, text)));
}

function fillSelect(select, items, label, { optional = false, placeholder = "" } = {}) {
    const current = select.value;
    select.replaceChildren(
        ...(optional ? [el("option", { value: "" }, placeholder || "None")] : []),
        ...items.map((item) => el("option", { value: item.id }, label(item))),
    );
    if ([...select.options].some((o) => o.value === current)) select.value = current;
}

const accountLabel = (a) => `${a.platform_label}: ${a.name || "account " + a.id}`;

// ---------- navigation ----------

const TITLES = { dashboard: "Dashboard", posts: "Posts", niches: "Niches", schedule: "Schedules",
                 accounts: "Accounts", scheduler: "Scheduler" };

function switchSection(name) {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.section === name));
    document.querySelectorAll(".content-section").forEach((s) => s.classList.toggle("active", s.id === name));
    document.getElementById("section-title").textContent = TITLES[name];
    loadSection(name);
}

function currentSection() {
    return document.querySelector(".content-section.active").id;
}

async function loadSection(name) {
    await loadShared();
    const loaders = { dashboard: loadDashboard, posts: loadPosts, niches: loadNiches, schedule: loadSchedules,
                      accounts: loadAccounts, scheduler: loadScheduler };
    await run(loaders[name]);
}

async function loadShared() {
    const [niches, accounts, platforms] = await Promise.all([api("/niches"), api("/accounts"), api("/platforms")]);
    state.niches = niches;
    state.accounts = accounts;
    state.platforms = Object.fromEntries(platforms.map((p) => [p.id, p]));
}

// ---------- dashboard ----------

async function loadDashboard() {
    const s = await api("/stats");
    const set = (id, v) => { document.getElementById(id).textContent = v; };
    set("stat-pending", s.posts.pending_approval);
    set("stat-scheduled", s.posts.scheduled);
    set("stat-posted", s.posts.posted);
    set("stat-failed", s.posts.failed);
    set("stat-niches", s.niches);
    set("stat-accounts", s.accounts);
    updatePendingBadge(s.posts.pending_approval);

    const warnings = [];
    if (!s.ai_configured) warnings.push("AI_API_KEY isn't set, so scheduled posts can't be written yet.");
    if (!s.scheduler.running) warnings.push("The scheduler isn't running in this process. Posts only publish if worker.py is running, or when you use the Scheduler page.");
    if (s.posts.failed) warnings.push(`${s.posts.failed} post(s) failed. See Posts > Failed.`);
    document.getElementById("setup-warnings").replaceChildren(
        ...warnings.map((w) => el("div", { class: "result-message error" }, w)),
    );
}

function updatePendingBadge(count) {
    const badge = document.getElementById("nav-pending");
    badge.hidden = !count;
    badge.textContent = count;
}

// ---------- posts ----------

async function loadPosts() {
    const query = state.postFilter ? `?status=${encodeURIComponent(state.postFilter)}` : "";
    const posts = await api(`/posts${query}`);
    const table = document.getElementById("posts-table");
    fillSelect(document.getElementById("post-account"), state.accounts, accountLabel);
    fillSelect(document.getElementById("post-niche"), state.niches, (n) => n.name, { optional: true });
    if (!posts.length) return emptyRow(table, 5, "No posts here yet.");

    table.replaceChildren(...posts.map((p) => el("tr", {},
        el("td", { class: "nowrap" }, p.status === "posted" ? fmtTime(p.posted_at) : fmtTime(p.scheduled_time)),
        el("td", {}, p.account_name || "—", p.niche_name ? el("div", { class: "muted" }, p.niche_name) : null),
        el("td", { class: "post-content" },
            el("div", { class: "content-text" }, p.content),
            p.last_error ? el("div", { class: "error-text" }, p.last_error) : null),
        el("td", {}, el("span", { class: `badge badge-${p.status}` }, STATUS_LABELS[p.status] || p.status),
            p.url ? el("div", {}, el("a", { href: p.url, target: "_blank", rel: "noopener" }, "View ↗")) : null),
        el("td", { class: "actions" }, postActions(p)),
    )));
}

function postActions(p) {
    const btn = (label, cls, handler) => el("button", { class: `btn btn-small ${cls}`, onclick: handler }, label);
    const act = (path, msg) => () => run(() => api(`/posts/${p.id}/${path}`, { method: "POST" }), msg).then(refresh);
    const actions = [];
    if (p.status === "pending_approval") actions.push(btn("Approve", "btn-success", act("approve", "Post approved")));
    if (["pending_approval", "scheduled", "failed"].includes(p.status)) actions.push(btn("Edit", "btn-secondary", () => editPost(p)));
    if (p.status === "failed") actions.push(btn("Retry", "btn-primary", act("retry", "Post will be retried")));
    if (["pending_approval", "scheduled"].includes(p.status)) actions.push(btn("Reject", "btn-secondary", act("reject", "Post rejected")));
    if (p.status !== "posting") {
        actions.push(btn("Delete", "btn-danger", () => {
            if (confirm("Delete this post? This doesn't remove it from the platform if it was already posted.")) {
                run(() => api(`/posts/${p.id}`, { method: "DELETE" }), "Post deleted").then(refresh);
            }
        }));
    }
    return actions;
}

function openPostForm(post) {
    document.getElementById("post-form").reset();
    document.getElementById("post-id").value = post ? post.id : "";
    document.getElementById("post-form-title").textContent = post ? "Edit post" : "Write a post";
    document.getElementById("post-submit").textContent = post ? "Save changes" : "Schedule post";
    document.getElementById("post-account").disabled = Boolean(post);
    document.getElementById("post-niche").disabled = Boolean(post);
    if (post) {
        document.getElementById("post-account").value = post.account_id || "";
        document.getElementById("post-niche").value = post.niche_id || "";
        document.getElementById("post-content").value = post.content;
        document.getElementById("post-time").value = toLocalInput(post.scheduled_time);
    }
    updateCharCount();
    showForm("post-form-card");
}

function editPost(p) { openPostForm(p); }

function updateCharCount() {
    const account = state.accounts.find((a) => String(a.id) === document.getElementById("post-account").value);
    const limit = account && state.platforms[account.platform] ? state.platforms[account.platform].max_length : null;
    const length = document.getElementById("post-content").value.length;
    const counter = document.getElementById("post-char-count");
    counter.textContent = limit ? `${length} / ${limit}` : `${length} characters`;
    counter.classList.toggle("over", Boolean(limit && length > limit));
}

async function submitPost(event) {
    event.preventDefault();
    const id = document.getElementById("post-id").value;
    const time = document.getElementById("post-time").value;
    const payload = {
        content: document.getElementById("post-content").value,
        scheduled_time: time ? new Date(time).toISOString() : null,
    };
    if (!id) {
        payload.account_id = document.getElementById("post-account").value;
        payload.niche_id = document.getElementById("post-niche").value || null;
    }
    const saved = await run(
        () => api(id ? `/posts/${id}` : "/posts", { method: id ? "PUT" : "POST", body: payload }),
        id ? "Post saved" : "Post scheduled",
    );
    if (saved) { showForm("post-form-card", false); refresh(); }
}

// ---------- niches ----------

async function loadNiches() {
    const table = document.getElementById("niches-table");
    if (!state.niches.length) return emptyRow(table, 4, "No niches yet. A niche is a topic AutoPoster writes about.");
    table.replaceChildren(...state.niches.map((n) => el("tr", {},
        el("td", {}, el("strong", {}, n.name)),
        el("td", {}, n.description || "", n.primary_statement ? el("div", { class: "muted" }, `Key message: ${n.primary_statement}`) : null),
        el("td", {}, hashtagEditor(n)),
        el("td", { class: "actions" },
            el("button", { class: "btn btn-small btn-secondary", onclick: () => openNicheForm(n) }, "Edit"),
            el("button", { class: "btn btn-small btn-danger", onclick: () => {
                if (confirm(`Delete "${n.name}"? Its schedules and posts are deleted too.`)) {
                    run(() => api(`/niches/${n.id}`, { method: "DELETE" }), "Niche deleted").then(refresh);
                }
            } }, "Delete")),
    )));
}

function hashtagEditor(niche) {
    const input = el("input", { type: "text", placeholder: "add tag", class: "tag-input", maxlength: 100 });
    const add = () => {
        const tag = input.value.trim();
        if (!tag) return;
        run(() => api(`/niches/${niche.id}/hashtags`, { method: "POST", body: { tag } })).then(refresh);
    };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } });
    return el("div", { class: "tags" },
        niche.hashtags.map((h) => el("span", { class: "tag" }, `#${h.tag}`,
            el("button", { class: "tag-remove", title: "Remove", onclick: () =>
                run(() => api(`/hashtags/${h.id}`, { method: "DELETE" })).then(refresh) }, "×"))),
        input);
}

function openNicheForm(niche) {
    document.getElementById("niche-form").reset();
    document.getElementById("niche-id").value = niche ? niche.id : "";
    document.getElementById("niche-form-title").textContent = niche ? "Edit niche" : "Create niche";
    if (niche) {
        document.getElementById("niche-name").value = niche.name;
        document.getElementById("niche-description").value = niche.description || "";
        document.getElementById("niche-statement").value = niche.primary_statement || "";
    }
    showForm("niche-form-card");
}

async function submitNiche(event) {
    event.preventDefault();
    const id = document.getElementById("niche-id").value;
    const payload = {
        name: document.getElementById("niche-name").value,
        description: document.getElementById("niche-description").value,
        primary_statement: document.getElementById("niche-statement").value,
    };
    const saved = await run(() => api(id ? `/niches/${id}` : "/niches", { method: id ? "PUT" : "POST", body: payload }),
                            "Niche saved");
    if (saved) { showForm("niche-form-card", false); refresh(); }
}

// ---------- schedules ----------

async function loadSchedules() {
    const schedules = await api("/schedules");
    fillSelect(document.getElementById("schedule-niche"), state.niches, (n) => n.name);
    fillSelect(document.getElementById("schedule-account"), state.accounts, accountLabel);
    const table = document.getElementById("schedule-table");
    if (!schedules.length) return emptyRow(table, 5, "No schedules yet.");
    table.replaceChildren(...schedules.map((s) => el("tr", {},
        el("td", {}, s.niche_name),
        el("td", {}, s.account_name || el("span", { class: "error-text" }, "No account: choose one")),
        el("td", {}, s.posts_per_day),
        el("td", {}, s.needs_approval ? "Approve first" : "Automatic"),
        el("td", { class: "actions" },
            el("button", { class: "btn btn-small btn-secondary", onclick: () => openScheduleForm(s) }, "Edit"),
            el("button", { class: "btn btn-small btn-danger", onclick: () => {
                if (confirm("Delete this schedule? Posts already written are kept.")) {
                    run(() => api(`/schedules/${s.id}`, { method: "DELETE" }), "Schedule deleted").then(refresh);
                }
            } }, "Delete")),
    )));
}

function openScheduleForm(schedule) {
    if (!state.niches.length || !state.accounts.length) {
        toast("Add an account and a niche first.", "error");
        return;
    }
    document.getElementById("schedule-form").reset();
    document.getElementById("schedule-id").value = schedule ? schedule.id : "";
    document.getElementById("schedule-form-title").textContent = schedule ? "Edit schedule" : "Create schedule";
    if (schedule) {
        document.getElementById("schedule-niche").value = schedule.niche_id;
        document.getElementById("schedule-account").value = schedule.account_id || "";
        document.getElementById("schedule-posts-per-day").value = schedule.posts_per_day;
        document.getElementById("schedule-needs-approval").value = schedule.needs_approval ? "1" : "0";
    }
    showForm("schedule-form-card");
}

async function submitSchedule(event) {
    event.preventDefault();
    const id = document.getElementById("schedule-id").value;
    const payload = {
        niche_id: document.getElementById("schedule-niche").value,
        account_id: document.getElementById("schedule-account").value,
        posts_per_day: document.getElementById("schedule-posts-per-day").value,
        needs_approval: document.getElementById("schedule-needs-approval").value === "1",
    };
    const saved = await run(() => api(id ? `/schedules/${id}` : "/schedules", { method: id ? "PUT" : "POST", body: payload }),
                            "Schedule saved");
    if (saved) { showForm("schedule-form-card", false); refresh(); }
}

// ---------- accounts ----------

async function loadAccounts() {
    const table = document.getElementById("accounts-table");
    if (!state.accounts.length) return emptyRow(table, 4, "No accounts yet.");
    table.replaceChildren(...state.accounts.map((a) => el("tr", {},
        el("td", {}, el("strong", {}, a.name || `Account ${a.id}`), a.author_urn ? el("div", { class: "muted" }, a.author_urn) : null),
        el("td", {}, a.platform_label),
        el("td", {}, fmtTime(a.created_at)),
        el("td", { class: "actions" },
            el("button", { class: "btn btn-small btn-secondary", onclick: () => verifyAccount(a.id) }, "Verify"),
            el("button", { class: "btn btn-small btn-danger", onclick: () => {
                if (confirm("Delete this account? Its posts are deleted and its schedules stop until you pick another account.")) {
                    run(() => api(`/accounts/${a.id}`, { method: "DELETE" }), "Account deleted").then(refresh);
                }
            } }, "Delete")),
    )));
}

function verifyAccount(id) {
    return run(() => api(`/accounts/${id}/verify`, { method: "POST" }),
               (r) => `Connected as ${r.display_name}`).then(refresh);
}

function syncAccountFields() {
    const platform = document.getElementById("account-platform").value;
    document.querySelectorAll("#account-form [data-platform]").forEach((block) => {
        block.hidden = block.dataset.platform !== platform;
    });
}

async function submitAccount(event) {
    event.preventDefault();
    const platform = document.getElementById("account-platform").value;
    const value = (id) => document.getElementById(id).value.trim();
    const payload = { platform, name: value("account-name") };
    if (platform === "x") {
        Object.assign(payload, { api_key: value("account-api-key"), api_secret: value("account-api-secret"),
                                 access_token: value("account-access-token"), access_secret: value("account-access-secret") });
    } else {
        Object.assign(payload, { access_token: value("account-li-token"), author_urn: value("account-author-urn") });
    }
    const account = await run(() => api("/accounts", { method: "POST", body: payload }));
    if (!account) return;
    document.getElementById("account-form").reset();
    syncAccountFields();
    showForm("account-form-card", false);
    await verifyAccount(account.id);
}

// ---------- scheduler ----------

async function loadScheduler() {
    const s = await api("/stats");
    const sched = s.scheduler;
    const line = (label, value) => el("div", { class: "status-row" }, el("span", { class: "muted" }, label), el("span", {}, value));
    const describe = (job) => !job ? "Not run yet" : job.error ? `Error: ${job.error}` :
        `${fmtTime(job.at)} · ${Object.entries(job.result).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.length : v}`).join(", ")}`;
    document.getElementById("scheduler-status").replaceChildren(
        line("Background scheduler", sched.running ? "Running in this process" : "Not running here (use worker.py)"),
        line("AI writer", s.ai_configured ? "Configured" : "AI_API_KEY not set"),
        line("Last planning run", describe(sched.plan)),
        line("Last publishing run", describe(sched.publish)),
    );
}

// ---------- wiring ----------

function refresh() { return loadSection(currentSection()); }

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.addEventListener("click", () => switchSection(b.dataset.section)));
    document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => switchSection(b.dataset.goto)));
    document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => showForm(b.dataset.close, false)));
    document.getElementById("refresh-btn").addEventListener("click", refresh);

    document.getElementById("new-post-btn").addEventListener("click", () => {
        if (!state.accounts.length) return toast("Add an account first.", "error");
        openPostForm(null);
    });
    document.getElementById("post-form").addEventListener("submit", submitPost);
    document.getElementById("post-content").addEventListener("input", updateCharCount);
    document.getElementById("post-account").addEventListener("change", updateCharCount);
    document.getElementById("post-filters").addEventListener("click", (e) => {
        const tab = e.target.closest(".tab");
        if (!tab) return;
        state.postFilter = tab.dataset.status;
        document.querySelectorAll("#post-filters .tab").forEach((t) => t.classList.toggle("active", t === tab));
        refresh();
    });

    document.getElementById("new-niche-btn").addEventListener("click", () => openNicheForm(null));
    document.getElementById("niche-form").addEventListener("submit", submitNiche);
    document.getElementById("new-schedule-btn").addEventListener("click", () => openScheduleForm(null));
    document.getElementById("schedule-form").addEventListener("submit", submitSchedule);
    document.getElementById("new-account-btn").addEventListener("click", () => showForm("account-form-card"));
    document.getElementById("account-form").addEventListener("submit", submitAccount);
    document.getElementById("account-platform").addEventListener("change", syncAccountFields);

    document.getElementById("run-plan-btn").addEventListener("click", () =>
        run(() => api("/run/plan", { method: "POST" }), (r) =>
            r.errors.length ? `Wrote ${r.created} post(s); ${r.errors[0].error}` : `Wrote ${r.created} post(s)`).then(refresh));
    document.getElementById("run-publish-btn").addEventListener("click", () =>
        run(() => api("/run/publish", { method: "POST" }), (r) =>
            `Posted ${r.posted}, failed ${r.failed}, retrying ${r.retrying}`).then(refresh));

    switchSection("dashboard");
});
