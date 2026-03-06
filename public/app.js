/* ---------- Config ---------- */
const PARTICIPANTS = ["Edje", "Maxime", "El Sierd", "Miqi", "Koen", "Bart"];
const COLORS = {
    "Edje": "#C4613A",
    "Maxime": "#3A8F85",
    "El Sierd": "#C69C4E",
    "Miqi": "#6B5BAD",
    "Koen": "#D08B4A",
    "Bart": "#4A90A4"
};
const INITIALS = {
    "Edje": "E",
    "Maxime": "M",
    "El Sierd": "S",
    "Miqi": "Q",
    "Koen": "K",
    "Bart": "B"
};
const DAYS = [
    { key: "2026-04-01", label: "Woensdag 1 april", short: "1 apr" },
    { key: "2026-04-02", label: "Donderdag 2 april", short: "2 apr" },
    { key: "2026-04-03", label: "Vrijdag 3 april", short: "3 apr" },
    { key: "2026-04-04", label: "Zaterdag 4 april", short: "4 apr" }
];

const DAY_TABS = { "day-1": "2026-04-01", "day-2": "2026-04-02", "day-3": "2026-04-03", "day-4": "2026-04-04" };

/* ---------- i18n: Spanish translations for Edje ---------- */
const ES = {
    // Login
    login_title: "\u00bfQui\u00e9n eres?",
    login_dates: "1 - 4 de abril",
    // Tabs
    tab_suggestions: "Sugerencias",
    tab_day1: "D\u00eda 1",
    tab_day2: "D\u00eda 2",
    tab_day3: "D\u00eda 3",
    tab_day4: "D\u00eda 4",
    // Suggestions page
    all_suggestions: "Todas las sugerencias",
    new_suggestion: "+ Nueva sugerencia",
    no_suggestions: "\u00a1A\u00fan no hay sugerencias. \u00a1A\u00f1ade una!",
    // Suggestion modal
    new_suggestion_title: "Nueva sugerencia",
    label_activity: "Actividad",
    placeholder_activity: "Ej. Visitar el Museo del Prado",
    label_location: "Ubicaci\u00f3n",
    placeholder_location: "Ej. Calle de Ruiz de Alarc\u00f3n, 23",
    label_duration: "Duraci\u00f3n",
    placeholder_duration: "Ej. 2 horas",
    label_daypart: "Momento del d\u00eda",
    option_choose: "Elige...",
    option_morning: "Ma\u00f1ana",
    option_afternoon: "Tarde",
    option_evening: "Noche",
    option_allday: "Todo el d\u00eda",
    label_cost: "Coste (por persona)",
    placeholder_cost: "Ej. \u20ac15 o Gratis",
    btn_cancel: "Cancelar",
    btn_add: "A\u00f1adir",
    btn_close: "Cerrar",
    // Day add modal
    add_to_day_title: "A\u00f1adir sugerencia al d\u00eda",
    // Logout
    logout_title: "Cambiar de usuario",
    // Day view (dynamic)
    day_labels: {
        "2026-04-01": "Mi\u00e9rcoles 1 de abril",
        "2026-04-02": "Jueves 2 de abril",
        "2026-04-03": "Viernes 3 de abril",
        "2026-04-04": "S\u00e1bado 4 de abril"
    },
    propose_btn: "+ Proponer actividad",
    agenda_title: "Agenda",
    no_agenda: "A\u00fan no hay actividades confirmadas para este d\u00eda.",
    proposals_title: "Propuestas",
    proposed_by: "Propuesto por",
    btn_accept: "Aceptar",
    btn_reject: "Rechazar",
    rejected_label: "Rechazado",
    btn_revoke: "Anular voto",
    btn_calendar: "A\u00f1adir al calendario",
    delete_btn: "Eliminar",
    confirm_delete: "\u00bfEst\u00e1s seguro de que quieres eliminar esta sugerencia?",
    all_proposed: "Todas las sugerencias ya han sido propuestas o confirmadas para este d\u00eda.",
    connected: "Conectado",
    disconnected: "Conexi\u00f3n perdida...",
    // Detail / notes
    detail_title: "Detalles de la actividad",
    author_label: "Sugerido por",
    notes_title: "Notas",
    no_notes: "\u00a1A\u00fan no hay notas. \u00a1A\u00f1ade una!",
    note_placeholder: "Escribe una nota...",
    btn_add_note: "A\u00f1adir",
    btn_delete_note: "Eliminar",
    btn_remove_agenda: "Eliminar de la agenda",
    confirm_remove_agenda: "\u00bfEst\u00e1s seguro de que quieres eliminar esta actividad de la agenda?",
    label_link: "Enlace",
    label_optional: "(opcional)",
    placeholder_link: "Ej. https://www.museodelprado.es",
    label_description: "Descripci\u00f3n",
    placeholder_description: "Cu\u00e9ntanos m\u00e1s sobre esta actividad...",
    link_label: "M\u00e1s info",
    // Daypart translations (for dynamic content)
    dayparts: {
        "Ochtend": "Ma\u00f1ana",
        "Middag": "Tarde",
        "Avond": "Noche",
        "Hele dag": "Todo el d\u00eda"
    }
};

function isSpanish() {
    return currentUser === "Edje";
}

/** Translate a UI key. Returns Spanish if Edje, otherwise returns fallback (Dutch). */
function t(key, fallback) {
    if (isSpanish() && ES[key] !== undefined) return ES[key];
    return fallback || key;
}

/** Translate a daypart value */
function tDaypart(val) {
    if (isSpanish() && ES.dayparts[val]) return ES.dayparts[val];
    return val;
}

/** Translate a day label */
function tDayLabel(dayKey, nlLabel) {
    if (isSpanish() && ES.day_labels[dayKey]) return ES.day_labels[dayKey];
    return nlLabel;
}

/* ---------- Translation API for dynamic content ---------- */
const translationCache = new Map();
const pendingTranslations = new Map();

/**
 * Translate free-text content (title, location, duration, cost) via MyMemory API.
 * Returns cached value if available, otherwise starts async fetch and re-renders.
 */
function translateText(text) {
    if (!text || !isSpanish()) return text;

    // Check cache
    if (translationCache.has(text)) return translationCache.get(text);

    // Don't re-fetch if already pending
    if (!pendingTranslations.has(text)) {
        pendingTranslations.set(text, true);
        fetch(`https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}&langpair=nl|es`)
            .then(r => r.json())
            .then(data => {
                if (data.responseData && data.responseData.translatedText) {
                    let translated = data.responseData.translatedText;
                    // MyMemory returns uppercase when unsure; keep original casing style
                    if (text[0] === text[0].toLowerCase() && translated[0] !== translated[0].toLowerCase()) {
                        translated = translated[0].toLowerCase() + translated.slice(1);
                    }
                    translationCache.set(text, translated);
                } else {
                    translationCache.set(text, text); // fallback to original
                }
                pendingTranslations.delete(text);
                render(); // re-render with translated content
            })
            .catch(() => {
                translationCache.set(text, text);
                pendingTranslations.delete(text);
            });
    }

    return text; // return original while loading
}

/** Translate a suggestion's display fields. Returns new object with translated strings. */
function tSuggestion(s) {
    if (!isSpanish()) return s;
    return {
        ...s,
        title: translateText(s.title),
        location: translateText(s.location),
        duration: translateText(s.duration),
        daypart: tDaypart(s.daypart),
        cost: translateText(s.cost),
        description: s.description ? translateText(s.description) : ""
    };
}

/** Apply i18n to static HTML elements with data-i18n attributes. */
function applyStaticTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (isSpanish() && ES[key] !== undefined) {
            el.textContent = ES[key];
        }
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (isSpanish() && ES[key] !== undefined) {
            el.placeholder = ES[key];
        }
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        if (isSpanish() && ES[key] !== undefined) {
            el.title = ES[key];
        }
    });
}

/* ---------- State ---------- */
let currentUser = null;
let appState = null;
let ws = null;
let reconnectTimer = null;
let openDetailDayKey = null;
let openDetailSuggestionId = null;

/* ---------- WebSocket ---------- */
function connect() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        setConnectionStatus(true);
        ws.send(JSON.stringify({ action: "get_state" }));
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "state") {
            appState = msg.data;
            render();
        }
    };

    ws.onclose = () => {
        setConnectionStatus(false);
        reconnectTimer = setTimeout(connect, 2000);
    };

    ws.onerror = () => {
        ws.close();
    };
}

function send(action) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(action));
    }
}

function setConnectionStatus(connected) {
    let el = document.querySelector('.connection-status');
    if (!el) {
        el = document.createElement('div');
        el.className = 'connection-status';
        document.body.appendChild(el);
    }
    el.className = `connection-status ${connected ? 'connected' : 'disconnected'}`;
    el.textContent = connected
        ? t('connected', 'Verbonden')
        : t('disconnected', 'Verbinding verbroken...');
    if (connected) {
        setTimeout(() => { el.style.opacity = '0'; }, 2000);
    } else {
        el.style.opacity = '1';
    }
}

/* ---------- Icons (inline SVG) ---------- */
const icons = {
    location: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>',
    clock: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    sun: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>',
    euro: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="10" x2="16" y2="10"/><line x1="4" y1="14" x2="14" y2="14"/><path d="M17 4a7.5 7.5 0 010 16"/></svg>',
    check: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>',
    x: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    undo: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 105.64-11.36L1 10"/></svg>',
    calendar: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    trash: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>',
    note: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
    link: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>',
};

/* ---------- Login ---------- */
document.querySelectorAll('.user-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        currentUser = btn.dataset.user;
        localStorage.setItem('madrid-user', currentUser);
        showApp();
    });
});

document.getElementById('logout-btn').addEventListener('click', () => {
    currentUser = null;
    localStorage.removeItem('madrid-user');
    document.getElementById('app-screen').classList.remove('active');
    document.getElementById('login-screen').classList.add('active');
    // Reset static text to Dutch defaults
    location.reload();
});

function showApp() {
    document.getElementById('login-screen').classList.remove('active');
    document.getElementById('app-screen').classList.add('active');

    const badge = document.getElementById('current-user-badge');
    badge.textContent = currentUser;
    badge.style.borderColor = COLORS[currentUser];
    badge.style.color = COLORS[currentUser];

    // Apply static translations for Edje
    applyStaticTranslations();

    connect();
}

// Auto-login
const savedUser = localStorage.getItem('madrid-user');
if (savedUser && PARTICIPANTS.includes(savedUser)) {
    currentUser = savedUser;
    showApp();
}

/* ---------- Tabs ---------- */
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
    });
});

/* ---------- Render ---------- */
function render() {
    if (!appState) return;
    renderSuggestions();
    DAYS.forEach((day, i) => renderDay(day, i));
    // Refresh detail modal if open
    if (openDetailDayKey && openDetailSuggestionId) {
        renderDetailBody(openDetailDayKey, openDetailSuggestionId);
    }
}

function renderSuggestions() {
    const list = document.getElementById('suggestions-list');
    const empty = document.getElementById('no-suggestions');
    const suggestions = appState.suggestions;

    if (suggestions.length === 0) {
        list.innerHTML = '';
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';
    list.innerHTML = suggestions.map(s => {
        const ts = tSuggestion(s);
        const color = COLORS[s.author] || '#888';
        const initial = INITIALS[s.author] || '?';
        return `
        <div class="suggestion-card" style="--card-color: ${color}">
            <div class="card-header">
                <h3>${esc(ts.title)}</h3>
                <div class="author-dot" title="${esc(s.author)}">${initial}</div>
            </div>
            <div class="suggestion-meta">
                <div class="meta-row">${icons.location} ${esc(ts.location)}</div>
                <div class="meta-row">${icons.clock} ${esc(ts.duration)}</div>
                <div class="meta-row">${icons.sun} ${esc(ts.daypart)}</div>
                <div class="meta-row">${icons.euro} ${esc(ts.cost)}</div>
                ${s.link ? `<div class="meta-row meta-link">${icons.link} <a href="${esc(s.link)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${t('link_label', 'Meer info')}</a></div>` : ''}
            </div>
            ${ts.description ? `<p class="suggestion-description">${esc(ts.description)}</p>` : ''}
            ${s.author === currentUser ? `
            <div class="card-actions">
                <button class="btn btn-sm btn-danger" onclick="deleteSuggestion(${s.id})">${t('delete_btn', 'Verwijderen')}</button>
            </div>` : ''}
        </div>`;
    }).join('');
}

function renderDay(day, index) {
    const container = document.getElementById(`tab-day-${index + 1}`);
    const dayData = appState.days[day.key];
    if (!dayData) return;

    const agenda = dayData.agenda || [];
    const proposals = dayData.proposals || [];

    let html = `
        <div class="section-header">
            <h2>${tDayLabel(day.key, day.label)}</h2>
            <button class="btn btn-primary" onclick="openDayAddModal('${day.key}')">${t('propose_btn', '+ Activiteit voorstellen')}</button>
        </div>
    `;

    // Agenda section
    html += `<div class="day-section">
        <h3>${t('agenda_title', 'Agenda')} <span class="count">${agenda.length}</span></h3>`;

    if (agenda.length === 0) {
        html += `<div class="empty-state"><p>${t('no_agenda', 'Nog geen bevestigde activiteiten voor deze dag.')}</p></div>`;
    } else {
        html += agenda.map(a => {
            const ta = tSuggestion(a);
            const noteCount = (appState.days[day.key].notes && appState.days[day.key].notes[String(a.id)])
                ? appState.days[day.key].notes[String(a.id)].length : 0;
            return `
            <div class="agenda-item agenda-item-clickable" onclick="openDetail('${day.key}', ${a.id})">
                <div class="check">${icons.check}</div>
                <div class="agenda-info">
                    <h4>${esc(ta.title)}</h4>
                    <div class="agenda-details">
                        <span>${icons.location} ${esc(ta.location)}</span>
                        <span>${icons.clock} ${esc(ta.duration)}</span>
                        <span>${icons.sun} ${esc(ta.daypart)}</span>
                        <span>${icons.euro} ${esc(ta.cost)}</span>
                    </div>
                </div>
                ${noteCount > 0 ? `<span class="note-count">${icons.note} ${noteCount}</span>` : ''}
                <button class="btn-calendar" onclick="event.stopPropagation(); addToCalendar('${day.key}', ${a.id})" title="${t('btn_calendar', 'Toevoegen aan agenda')}">
                    ${icons.calendar}
                </button>
            </div>
        `}).join('');
    }
    html += `</div>`;

    // Proposals section
    const activeProposals = proposals.filter(p => p.status !== 'rejected');
    const rejectedProposals = proposals.filter(p => p.status === 'rejected');

    if (activeProposals.length > 0 || rejectedProposals.length > 0) {
        html += `<div class="day-section">
            <h3>${t('proposals_title', 'Voorstellen')} <span class="count">${activeProposals.length}</span></h3>`;

        html += activeProposals.map(p => renderProposal(p, day.key)).join('');
        html += rejectedProposals.map(p => renderProposal(p, day.key)).join('');

        html += `</div>`;
    }

    container.innerHTML = html;
}

function renderProposal(p, dayKey) {
    const s = p.suggestion;
    const ts = tSuggestion(s);
    const color = COLORS[s.author] || '#888';
    const isRejected = p.status === 'rejected';

    let votesHtml = PARTICIPANTS.map(name => {
        const vote = p.votes[name];
        let cls = 'pending';
        let label = '?';
        if (vote === true) { cls = 'accepted'; label = icons.check; }
        else if (vote === false) { cls = 'rejected'; label = icons.x; }
        return `<span class="vote-chip ${cls}">${label} ${esc(name)}</span>`;
    }).join('');

    const hasVoted = p.votes.hasOwnProperty(currentUser);
    const canVote = !hasVoted;

    // Build action buttons
    let actionsHtml = '';
    if (canVote) {
        actionsHtml = `
        <div class="vote-actions">
            <button class="btn btn-sm btn-accept" onclick="vote('${dayKey}', ${p.id}, true)">${icons.check} ${t('btn_accept', 'Accepteer')}</button>
            <button class="btn btn-sm btn-reject" onclick="vote('${dayKey}', ${p.id}, false)">${icons.x} ${t('btn_reject', 'Afwijzen')}</button>
        </div>`;
    } else if (hasVoted) {
        actionsHtml = `
        <div class="vote-actions">
            <button class="btn btn-sm btn-revoke" onclick="revokeVote('${dayKey}', ${p.id})">${icons.undo} ${t('btn_revoke', 'Herroep stem')}</button>
        </div>`;
    }

    return `
    <div class="proposal-item ${isRejected ? 'rejected' : ''}" style="--card-color: ${color}">
        <div class="proposal-header">
            <h4>${esc(ts.title)}</h4>
            <span class="proposal-proposer">${t('proposed_by', 'Voorgesteld door')} ${esc(p.proposer)}</span>
        </div>
        <div class="proposal-details">
            <span>${icons.location} ${esc(ts.location)}</span>
            <span>${icons.clock} ${esc(ts.duration)}</span>
            <span>${icons.sun} ${esc(ts.daypart)}</span>
            <span>${icons.euro} ${esc(ts.cost)}</span>
        </div>
        <div class="votes-bar">${votesHtml}</div>
        ${actionsHtml}
        ${isRejected ? `<p style="font-size:0.8rem;color:var(--danger);margin-top:0.5rem;">${t('rejected_label', 'Afgewezen')}</p>` : ''}
    </div>`;
}

/* ---------- Actions ---------- */
function deleteSuggestion(id) {
    if (confirm(t('confirm_delete', 'Weet je zeker dat je deze suggestie wilt verwijderen?'))) {
        send({ action: "delete_suggestion", id: id });
    }
}

function vote(day, proposalId, accept) {
    send({
        action: "vote",
        day: day,
        proposal_id: proposalId,
        voter: currentUser,
        accept: accept
    });
}

function revokeVote(day, proposalId) {
    send({
        action: "revoke_vote",
        day: day,
        proposal_id: proposalId,
        voter: currentUser
    });
}

/* ---------- Detail Modal ---------- */
function openDetail(dayKey, suggestionId) {
    openDetailDayKey = dayKey;
    openDetailSuggestionId = suggestionId;
    renderDetailBody(dayKey, suggestionId);
    document.getElementById('detail-modal').classList.add('active');
}

function closeDetail() {
    openDetailDayKey = null;
    openDetailSuggestionId = null;
    document.getElementById('detail-modal').classList.remove('active');
}

function renderDetailBody(dayKey, suggestionId) {
    const dayData = appState.days[dayKey];
    if (!dayData) return;
    const item = dayData.agenda.find(a => a.id === suggestionId);
    if (!item) return;

    const ta = tSuggestion(item);
    const color = COLORS[item.author] || '#888';
    const initial = INITIALS[item.author] || '?';
    const notes = (dayData.notes && dayData.notes[String(suggestionId)]) || [];
    const isAuthor = currentUser === item.author;

    // Find day label
    const dayObj = DAYS.find(d => d.key === dayKey);
    const dayLabel = dayObj ? tDayLabel(dayKey, dayObj.label) : dayKey;

    let html = `
        <div class="detail-header">
            <div class="detail-title-row">
                <h2>${esc(ta.title)}</h2>
                <div class="author-dot" style="background: ${color}" title="${esc(item.author)}">${initial}</div>
            </div>
            <p class="detail-day-label">${dayLabel}</p>
            <div class="detail-meta">
                <span>${icons.location} ${esc(ta.location)}</span>
                <span>${icons.clock} ${esc(ta.duration)}</span>
                <span>${icons.sun} ${esc(ta.daypart)}</span>
                <span>${icons.euro} ${esc(ta.cost)}</span>
            </div>
            <p class="detail-author">${t('author_label', 'Voorgesteld door')} <strong>${esc(item.author)}</strong></p>
            ${item.link ? `<p class="detail-link">${icons.link} <a href="${esc(item.link)}" target="_blank" rel="noopener">${t('link_label', 'Meer info')}</a></p>` : ''}
            ${ta.description ? `<p class="detail-description">${esc(ta.description)}</p>` : ''}
            <button class="btn btn-sm btn-calendar-detail" onclick="event.stopPropagation(); addToCalendar('${dayKey}', ${item.id})">
                ${icons.calendar} ${t('btn_calendar', 'Toevoegen aan agenda')}
            </button>
        </div>

        <div class="notes-section">
            <h3>${icons.note} ${t('notes_title', 'Aantekeningen')} <span class="count">${notes.length}</span></h3>
    `;

    if (notes.length === 0) {
        html += `<p class="notes-empty">${t('no_notes', 'Nog geen aantekeningen. Voeg er een toe!')}</p>`;
    } else {
        html += notes.map(n => {
            const noteColor = COLORS[n.author] || '#888';
            const noteInitial = INITIALS[n.author] || '?';
            const timeStr = formatNoteTime(n.created);
            return `
            <div class="note-item">
                <div class="note-header">
                    <div class="note-author-badge" style="--note-color: ${noteColor}">
                        <span class="note-initial">${noteInitial}</span>
                        <span class="note-name">${esc(n.author)}</span>
                    </div>
                    <span class="note-time">${timeStr}</span>
                </div>
                <p class="note-text">${esc(n.text)}</p>
                ${isAuthor ? `<button class="btn-note-delete" onclick="deleteNote('${dayKey}', ${suggestionId}, ${n.id})" title="${t('btn_delete_note', 'Verwijderen')}">${icons.trash}</button>` : ''}
            </div>`;
        }).join('');
    }

    html += `
            <div class="note-input-row">
                <input type="text" id="note-input" class="note-input" placeholder="${t('note_placeholder', 'Schrijf een aantekening...')}" onkeydown="if(event.key==='Enter'){addNote('${dayKey}', ${suggestionId});}" />
                <button class="btn btn-primary btn-sm" onclick="addNote('${dayKey}', ${suggestionId})">${t('btn_add_note', 'Toevoegen')}</button>
            </div>
        </div>
        ${isAuthor ? `<div class="detail-remove-row">
            <button class="btn-remove-agenda" onclick="removeFromAgenda('${dayKey}', ${item.id})">${t('btn_remove_agenda', 'Verwijder uit agenda')}</button>
        </div>` : ''}
    `;

    document.getElementById('detail-body').innerHTML = html;
}

function formatNoteTime(isoStr) {
    try {
        const d = new Date(isoStr);
        return d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' }) + ' ' +
               d.toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        return '';
    }
}

function addNote(dayKey, suggestionId) {
    const input = document.getElementById('note-input');
    const text = input.value.trim();
    if (!text) return;
    send({
        action: "add_note",
        day: dayKey,
        suggestion_id: suggestionId,
        author: currentUser,
        text: text
    });
    input.value = '';
}

function deleteNote(dayKey, suggestionId, noteId) {
    send({
        action: "delete_note",
        day: dayKey,
        suggestion_id: suggestionId,
        note_id: noteId,
        requester: currentUser
    });
}

function removeFromAgenda(dayKey, suggestionId) {
    if (confirm(t('confirm_remove_agenda', 'Weet je zeker dat je deze activiteit uit de agenda wilt verwijderen?'))) {
        send({
            action: "remove_from_agenda",
            day: dayKey,
            suggestion_id: suggestionId,
            requester: currentUser
        });
        closeDetail();
    }
}

/* ---------- Calendar Export ---------- */
const DAYPART_TIMES = {
    "Ochtend": { start: "090000", end: "120000" },
    "Middag":  { start: "130000", end: "170000" },
    "Avond":   { start: "190000", end: "230000" },
};

function addToCalendar(dayKey, suggestionId) {
    const dayData = appState.days[dayKey];
    if (!dayData) return;
    const item = dayData.agenda.find(a => a.id === suggestionId);
    if (!item) return;

    const dateClean = dayKey.replace(/-/g, ''); // 20260401
    const daypart = item.daypart;
    const isAllDay = (daypart === "Hele dag" || !DAYPART_TIMES[daypart]);

    let dtStart, dtEnd;
    if (isAllDay) {
        // All-day event: DATE only, no time
        dtStart = `DTSTART;VALUE=DATE:${dateClean}`;
        // All-day end is exclusive next day
        const nextDay = new Date(dayKey + 'T12:00:00');
        nextDay.setDate(nextDay.getDate() + 1);
        const nd = nextDay.toISOString().slice(0, 10).replace(/-/g, '');
        dtEnd = `DTEND;VALUE=DATE:${nd}`;
    } else {
        const times = DAYPART_TIMES[daypart];
        dtStart = `DTSTART;TZID=Europe/Madrid:${dateClean}T${times.start}`;
        dtEnd = `DTEND;TZID=Europe/Madrid:${dateClean}T${times.end}`;
    }

    const uid = `madrid2026-${suggestionId}-${dateClean}@trip`;
    const now = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+/, '');

    const ics = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Madrid2026//TripPlanner//NL',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VTIMEZONE',
        'TZID:Europe/Madrid',
        'BEGIN:STANDARD',
        'DTSTART:19701025T030000',
        'RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10',
        'TZOFFSETFROM:+0200',
        'TZOFFSETTO:+0100',
        'END:STANDARD',
        'BEGIN:DAYLIGHT',
        'DTSTART:19700329T020000',
        'RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=3',
        'TZOFFSETFROM:+0100',
        'TZOFFSETTO:+0200',
        'END:DAYLIGHT',
        'END:VTIMEZONE',
        'BEGIN:VEVENT',
        `UID:${uid}`,
        `DTSTAMP:${now}`,
        dtStart,
        dtEnd,
        `SUMMARY:${icsEscape(item.title)}`,
        `LOCATION:${icsEscape(item.location)}`,
        `DESCRIPTION:${icsEscape(item.cost + ' per persoon')}`,
        'STATUS:CONFIRMED',
        'END:VEVENT',
        'END:VCALENDAR'
    ].join('\r\n');

    const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${item.title.replace(/[^a-zA-Z0-9 ]/g, '').replace(/\s+/g, '-')}.ics`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function icsEscape(str) {
    return (str || '').replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');
}

/* ---------- Day Add Modal ---------- */
let currentDayForAdd = null;

function openDayAddModal(dayKey) {
    currentDayForAdd = dayKey;
    const modal = document.getElementById('day-add-modal');
    const list = document.getElementById('day-add-list');

    // Filter out suggestions already proposed or in agenda for this day
    const dayData = appState.days[dayKey];
    const proposedIds = new Set((dayData.proposals || []).map(p => p.suggestion_id));
    const agendaIds = new Set((dayData.agenda || []).map(a => a.id));

    const available = appState.suggestions.filter(s =>
        !proposedIds.has(s.id) && !agendaIds.has(s.id)
    );

    if (available.length === 0) {
        list.innerHTML = `<div class="empty-state"><p>${t('all_proposed', 'Alle suggesties zijn al voorgesteld of bevestigd voor deze dag.')}</p></div>`;
    } else {
        list.innerHTML = available.map(s => {
            const ts = tSuggestion(s);
            const color = COLORS[s.author] || '#888';
            return `
            <div class="day-add-item" style="--card-color: ${color}" onclick="proposeForDay(${s.id})">
                <div class="item-info">
                    <h4>${esc(ts.title)}</h4>
                    <p>${esc(ts.daypart)} &middot; ${esc(ts.duration)} &middot; ${esc(ts.cost)}</p>
                </div>
                <span class="add-icon">+</span>
            </div>`;
        }).join('');
    }

    modal.classList.add('active');
}

function proposeForDay(suggestionId) {
    send({
        action: "propose_for_day",
        day: currentDayForAdd,
        suggestion_id: suggestionId,
        proposer: currentUser
    });
    document.getElementById('day-add-modal').classList.remove('active');
}

/* ---------- Suggestion Modal ---------- */
document.getElementById('add-suggestion-btn').addEventListener('click', () => {
    document.getElementById('suggestion-modal').classList.add('active');
    document.getElementById('s-title').focus();
});

document.getElementById('cancel-suggestion').addEventListener('click', () => {
    document.getElementById('suggestion-modal').classList.remove('active');
    document.getElementById('suggestion-form').reset();
});

document.getElementById('cancel-day-add').addEventListener('click', () => {
    document.getElementById('day-add-modal').classList.remove('active');
});

document.getElementById('close-detail').addEventListener('click', () => {
    closeDetail();
});

// Close modals on backdrop click
document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', () => {
        const modal = backdrop.parentElement;
        modal.classList.remove('active');
        // Clear detail state if closing detail modal
        if (modal.id === 'detail-modal') {
            openDetailDayKey = null;
            openDetailSuggestionId = null;
        }
    });
});

document.getElementById('suggestion-form').addEventListener('submit', (e) => {
    e.preventDefault();
    send({
        action: "add_suggestion",
        title: document.getElementById('s-title').value.trim(),
        location: document.getElementById('s-location').value.trim(),
        duration: document.getElementById('s-duration').value.trim(),
        daypart: document.getElementById('s-daypart').value,
        cost: document.getElementById('s-cost').value.trim(),
        link: document.getElementById('s-link').value.trim(),
        description: document.getElementById('s-description').value.trim(),
        author: currentUser
    });
    document.getElementById('suggestion-modal').classList.remove('active');
    document.getElementById('suggestion-form').reset();
});

/* ---------- Utility ---------- */
function esc(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}
