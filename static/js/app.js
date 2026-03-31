/**
 * LLM Prompt Evaluator — Frontend Application Logic v3.0
 * =======================================================
 * Features: Evaluate, Compare, Dataset, Matrix, Assertions, RAG Mode
 * All data is fetched from /api/* endpoints — zero hardcoded mock data.
 */

// ── Global Fetch Override for ngrok ──
const originalFetch = window.fetch;
window.fetch = async function () {
    const resource = arguments[0];
    let config = arguments[1];
    if (!config) config = {};
    if (!config.headers) config.headers = {};
    if (config.headers instanceof Headers) {
        config.headers.append('ngrok-skip-browser-warning', 'true');
    } else {
        config.headers['ngrok-skip-browser-warning'] = 'true';
    }
    return originalFetch(resource, config);
};

// ── Global State ──
let selectedModel = 'phi3:mini';
let useJudge = false;
let useRag = false;
let currentResults = [];
let optimizeResult = null;
let datasetPrompts = [];
let promptCount = 0;
let assertions = [];
let loadingTimerHandle = null;
let etaRequestId = 0;
let fastMode = false;

const STRATEGIES = ['zero-shot', 'few-shot', 'chain-of-thought', 'role-based'];
const STRAT_TAGS = ['tag-zs', 'tag-fs', 'tag-cot', 'tag-rb'];
const MODEL_SEC_PER_PROMPT = {
    'phi3:mini': 2.0,
    'phi3': 2.2,
    'llama3': 4.8,
    'mistral': 3.8,
    'mistral:7b': 4.0,
    'gemma:2b': 2.5,
    'gemma:7b': 4.6
};

/** Quote CSV field (RFC 4180). */
function csvEscapeField(val) {
    const s = val === null || val === undefined ? '' : String(val);
    return '"' + s.replace(/"/g, '""') + '"';
}

/** UTF-8 BOM + CRLF so Microsoft Excel opens UTF-8 correctly on Windows. */
function buildExcelCsv(rowStrings) {
    return '\uFEFF' + rowStrings.join('\r\n');
}


// ═══════════════════════════════════
// THEME (Dark / Light)
// ═══════════════════════════════════

function initTheme() {
    const saved = localStorage.getItem('llm-eval-theme') || 'dark';
    applyTheme(saved);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem('llm-eval-theme', next);
}

function applyTheme(theme) {
    if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = theme === 'light' ? '☀️' : '🌙';
}

initTheme();

// ── Initialization ──
document.addEventListener('DOMContentLoaded', async () => {
    setupFastModeToggle();
    setupJudgeToggle();
    setupRagToggle();
    setupDragDrop();
    addPrompt();
    await fetchModels();
    updateEstimatedTime();
    fetchHistory();
    fetchIterations(false);
});

function setupFastModeToggle() {
    const toggle = document.getElementById('fast-mode-toggle');
    if (!toggle) return;
    toggle.addEventListener('change', (e) => {
        fastMode = e.target.checked;
        syncFastModeUi();
        updateEstimatedTime();
        toast(fastMode ? 'Fast Mode enabled: lower tokens + judge/rag off' : 'Fast Mode disabled', 'info');
    });
}

function syncFastModeUi() {
    const judgeToggle = document.getElementById('judge-toggle');
    const ragToggle = document.getElementById('rag-toggle');
    const matrixJudgeToggle = document.getElementById('matrix-judge-toggle');

    if (fastMode) {
        useJudge = false;
        useRag = false;
        if (judgeToggle) judgeToggle.checked = false;
        if (ragToggle) ragToggle.checked = false;
        if (matrixJudgeToggle) matrixJudgeToggle.checked = false;
    }

    if (judgeToggle) judgeToggle.disabled = fastMode;
    if (ragToggle) ragToggle.disabled = fastMode;
    if (matrixJudgeToggle) matrixJudgeToggle.disabled = fastMode;

    const wrap = document.getElementById('rag-context-wrap');
    if (wrap) wrap.style.display = useRag ? '' : 'none';
}


// ═══════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════

function showPage(id) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const page = document.getElementById('page-' + id);
    if (page) page.classList.add('active');

    const navEl = document.getElementById('nav-' + id);
    if (navEl) navEl.classList.add('active');

    const parentMap = { 'results': 'evaluate', 'optimize': 'evaluate' };
    if (parentMap[id]) {
        const parent = document.getElementById('nav-' + parentMap[id]);
        if (parent) parent.classList.add('active');
    }

    if (id === 'history') fetchHistory();
    if (id === 'matrix') populateMatrixModels();
    if (id === 'iterations') fetchIterations();
}

function showLoading(text = 'Processing...', sub = '') {
    document.getElementById('loading-text').textContent = text;
    document.getElementById('loading-sub').textContent = sub;
    document.getElementById('loading-bar').style.width = '0%';
    document.getElementById('loading-overlay').classList.add('active');
    startLoadingTimer();
}

function updateLoading(percent, sub = '') {
    document.getElementById('loading-bar').style.width = percent + '%';
    if (sub) document.getElementById('loading-sub').textContent = sub;
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.remove('active');
    stopLoadingTimer();
}

function startLoadingTimer() {
    const start = Date.now();
    const el = document.getElementById('loading-timer');
    if (loadingTimerHandle) clearInterval(loadingTimerHandle);
    loadingTimerHandle = setInterval(() => {
        const elapsed = ((Date.now() - start) / 1000).toFixed(1);
        if (el) el.textContent = elapsed + 's';
    }, 100);
}

function stopLoadingTimer() {
    if (loadingTimerHandle) {
        clearInterval(loadingTimerHandle);
        loadingTimerHandle = null;
    }
}

function toast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const icons = { success: '✓', error: '✗', info: 'ℹ' };
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ'}</span><span>${message}</span>`;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 4000);
}

function scoreClass(score, max = 100) {
    const pct = max === 1 ? score * 100 : score;
    if (pct >= 75) return 'sc-hi';
    if (pct >= 50) return 'sc-mid';
    return 'sc-lo';
}

function scoreColor(score, max = 100) {
    const pct = max === 1 ? score * 100 : score;
    if (pct >= 75) return 'var(--green)';
    if (pct >= 50) return 'var(--yellow)';
    return 'var(--red)';
}

function chipClass(score, max = 100) {
    const pct = max === 1 ? score * 100 : score;
    if (pct >= 75) return 'chip-hi';
    if (pct >= 50) return 'chip-mid';
    return 'chip-lo';
}

function truncate(text, len = 80) {
    if (!text) return '—';
    return text.length > len ? text.substring(0, len) + '…' : text;
}

function fmtScore(val, max = 100) {
    if (val === null || val === undefined) return '—';
    return (max === 100 ? val.toFixed(1) : (val * 100).toFixed(1));
}


// ═══════════════════════════════════
// TOGGLES
// ═══════════════════════════════════

function setupJudgeToggle() {
    const toggle = document.getElementById('judge-toggle');
    if (toggle) toggle.addEventListener('change', (e) => {
        useJudge = e.target.checked;
        updateEstimatedTime();
    });
}

function setupRagToggle() {
    const toggle = document.getElementById('rag-toggle');
    if (toggle) {
        toggle.addEventListener('change', (e) => {
            useRag = e.target.checked;
            const wrap = document.getElementById('rag-context-wrap');
            if (wrap) wrap.style.display = useRag ? '' : 'none';
            updateEstimatedTime();
        });
    }
}


// ═══════════════════════════════════
// ASSERTIONS
// ═══════════════════════════════════

function toggleAssertions() {
    const panel = document.getElementById('assertions-panel');
    const icon = document.getElementById('assert-toggle-icon');
    if (panel.style.display === 'none') {
        panel.style.display = '';
        icon.textContent = '▼';
    } else {
        panel.style.display = 'none';
        icon.textContent = '▶';
    }
}

function addAssertion() {
    const typeEl = document.getElementById('assert-type-select');
    const valueEl = document.getElementById('assert-value-input');
    const type = typeEl.value;
    const value = valueEl.value.trim();

    if (type === 'is_json') {
        assertions.push({ type, value: '' });
    } else if (!value) {
        return toast('Enter a value for the assertion rule', 'error');
    } else {
        assertions.push({ type, value });
    }

    valueEl.value = '';
    renderAssertions();
}

function removeAssertion(idx) {
    assertions.splice(idx, 1);
    renderAssertions();
}

function renderAssertions() {
    const list = document.getElementById('assertions-list');
    if (!list) return;
    if (assertions.length === 0) {
        list.innerHTML = '<div style="font-size:11px;color:var(--text-muted);padding:6px 0">No rules added yet</div>';
        return;
    }
    const labels = {
        contains: 'contains', not_contains: 'NOT contains', is_json: 'is valid JSON',
        regex: 'matches regex', starts_with: 'starts with', max_length: 'max words', min_length: 'min words'
    };
    list.innerHTML = assertions.map((a, i) =>
        `<div class="assert-rule">
            <span class="assert-rule-type">${labels[a.type] || a.type}</span>
            <span class="assert-rule-val">${a.value || '—'}</span>
            <button class="p-remove" onclick="removeAssertion(${i})" title="Remove">×</button>
        </div>`
    ).join('');
}


// ═══════════════════════════════════
// MODEL TABS
// ═══════════════════════════════════

async function fetchModels() {
    const statusEl = document.getElementById('system-status');
    try {
        const res = await fetch('/api/models');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const models = await res.json();

        if (models.length === 0) {
            statusEl.className = 'status-card error';
            statusEl.innerHTML = `<div class="status-title">System status</div>
                <div class="status-row"><span class="s-dot" style="background:var(--red)"></span>No models found</div>
                <div style="font-size:10px;color:var(--text-muted);margin-top:4px">Run: ollama pull phi3:mini</div>`;
            return;
        }

        const tabs = document.getElementById('model-tabs-container');
        tabs.innerHTML = '';
        models.forEach((m, i) => {
            const tab = document.createElement('div');
            tab.className = `model-tab ${i === 0 ? 'active' : ''}`;
            tab.dataset.model = m.name;
            tab.textContent = m.name;
            tab.onclick = () => selectTab(tab);
            tabs.appendChild(tab);
            if (i === 0) selectedModel = m.name;
        });

        // Store models globally for matrix page
        window._availableModels = models;

        statusEl.className = 'status-card';
        statusEl.innerHTML = `<div class="status-title">System status</div>
            <div class="status-row"><span class="s-dot" style="background:var(--green)"></span>Ollama connected</div>
            <div class="status-row"><span class="s-dot" style="background:var(--green)"></span>${models.length} model${models.length > 1 ? 's' : ''} available</div>
            <div class="status-row"><span class="s-dot" style="background:var(--green)"></span>${selectedModel} active</div>`;

    } catch (e) {
        console.error('Failed to load models:', e);
        statusEl.className = 'status-card error';
        statusEl.innerHTML = `<div class="status-title">System status</div>
            <div class="status-row"><span class="s-dot" style="background:var(--red)"></span>Cannot reach backend</div>
            <div style="font-size:10px;color:var(--text-muted);margin-top:4px">Is the server running?</div>`;
    }
}

function selectTab(el) {
    el.closest('.model-tabs').querySelectorAll('.model-tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    selectedModel = el.dataset.model;
    updateEstimatedTime();
}


// ═══════════════════════════════════
// PROMPT VARIANTS (Evaluate page)
// ═══════════════════════════════════

function addPrompt() {
    promptCount++;
    const idx = (promptCount - 1) % 4;
    const div = document.createElement('div');
    div.className = 'prompt-wrap';
    div.innerHTML = `
      <div class="p-header">
        <span class="p-label">Prompt ${promptCount}</span>
        <div class="p-actions">
          <span class="p-tag ${STRAT_TAGS[idx]}" data-strat="${STRATEGIES[idx]}">${STRATEGIES[idx]}</span>
          <button class="p-remove" onclick="removePrompt(this)" title="Remove">×</button>
        </div>
      </div>
      <textarea rows="2" placeholder="Enter your prompt variant..." oninput="checkQuality(this)"></textarea>
      <div class="quality-hint"><span class="hint-dot" style="background:var(--text-muted)"></span><span style="color:var(--text-muted);font-size:11px">Type to check quality…</span></div>
    `;
    document.getElementById('prompt-list').appendChild(div);
    updateEstimatedTime();
}

function removePrompt(btn) {
    const wrap = btn.closest('.prompt-wrap');
    if (document.querySelectorAll('.prompt-wrap').length > 1) {
        wrap.remove();
        updateEstimatedTime();
    }
}

function checkQuality(el) {
    const val = el.value.toLowerCase();
    const hint = el.nextElementSibling;
    const dot = hint.querySelector('.hint-dot');
    const text = hint.querySelector('span:last-child');
    const wordCount = val.trim().split(/\s+/).filter(Boolean).length;
    const hasRole = /you are|as an expert|act as|you're a/.test(val);
    const hasSteps = /step by step|explain each|walk through|think step/.test(val);
    const hasConstraint = /under \d+|less than|max |within |words|brief|concise/.test(val);

    if (wordCount < 3) {
        dot.style.background = 'var(--red)'; text.style.color = 'var(--red)';
        text.textContent = 'Too vague — add context and specifics';
    } else if (!hasRole && wordCount < 8) {
        dot.style.background = 'var(--yellow)'; text.style.color = 'var(--yellow)';
        text.textContent = 'Missing role — try "You are an expert in..."';
    } else if (!hasRole) {
        dot.style.background = 'var(--yellow)'; text.style.color = 'var(--yellow)';
        text.textContent = 'Good start — add a role for better accuracy';
    } else if (!hasSteps && !hasConstraint) {
        dot.style.background = 'var(--yellow)'; text.style.color = 'var(--yellow)';
        text.textContent = 'Role ✓ — add structure/length constraints';
    } else {
        dot.style.background = 'var(--green)'; text.style.color = 'var(--green)';
        text.textContent = '✓ Excellent — role, steps, constraints all set';
    }
}

function fillTemplates() {
    const q = document.getElementById('query-input').value || 'your topic';
    const templates = [
        q,
        `Explain ${q} in simple terms with real-world examples`,
        `You are an AI expert. Explain ${q} step by step. Keep it under 150 words. Cover key concepts clearly.`
    ];
    document.getElementById('prompt-list').innerHTML = '';
    promptCount = 0;
    templates.forEach(t => {
        addPrompt();
        const tas = document.querySelectorAll('#prompt-list textarea');
        const last = tas[tas.length - 1];
        last.value = t;
        checkQuality(last);
    });
}

function clearEvaluateAll() {
    document.getElementById('query-input').value = '';
    document.getElementById('reference-input').value = '';
    const ragCtx = document.getElementById('rag-context-input');
    if (ragCtx) ragCtx.value = '';
    document.getElementById('prompt-list').innerHTML = '';
    promptCount = 0;
    assertions = [];
    renderAssertions();
    addPrompt();
    updateEstimatedTime();
}

function formatEstimate(seconds) {
    if (seconds < 60) return `~${Math.max(1, Math.round(seconds))}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return secs > 0 ? `~${mins}m ${secs}s` : `~${mins}m`;
}

function updateEstimatedTime() {
    updateEstimatedTimeFromApi();
}

async function updateEstimatedTimeFromApi() {
    const el = document.getElementById('evaluate-time-estimate');
    if (!el) return;

    const variantCount = document.querySelectorAll('.prompt-wrap textarea').length || 1;
    const requestId = ++etaRequestId;

    try {
        const res = await fetch('/api/eta', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                operation: 'evaluate',
                model: selectedModel,
                prompt_count: variantCount,
                use_judge: fastMode ? false : useJudge,
                use_rag: fastMode ? false : useRag,
                fast_mode: fastMode,
                max_tokens: fastMode ? 160 : null
            })
        });

        if (!res.ok) throw new Error('ETA request failed');
        const eta = await res.json();

        // Ignore stale async responses.
        if (requestId !== etaRequestId) return;

        const src = eta.uses_runtime_samples ? 'learned' : 'default';
        el.textContent = `Estimated analysis time: ${formatEstimate(eta.estimated_seconds)} (${variantCount} prompt${variantCount > 1 ? 's' : ''}, ${src})`;
    } catch (_) {
        const secPerPrompt = MODEL_SEC_PER_PROMPT[selectedModel] || 3.0;
        const judgeMultiplier = useJudge ? 1.35 : 1;
        const ragMultiplier = useRag ? 1.2 : 1;
        const estimatedSeconds = variantCount * secPerPrompt * judgeMultiplier * ragMultiplier;
        el.textContent = `Estimated analysis time: ${formatEstimate(estimatedSeconds)} (${variantCount} prompt${variantCount > 1 ? 's' : ''})`;
    }
}


// ═══════════════════════════════════
// EVALUATE (core feature — concurrent)
// ═══════════════════════════════════

async function runEvaluation() {
    const query = document.getElementById('query-input').value.trim();
    const ref = document.getElementById('reference-input').value.trim();
    const ragCtx = document.getElementById('rag-context-input');
    const context = (useRag && ragCtx) ? ragCtx.value.trim() : null;
    if (!query) return toast('Please enter a question', 'error');

    const variants = [];
    document.querySelectorAll('.prompt-wrap').forEach((wrap, i) => {
        const ta = wrap.querySelector('textarea');
        const tag = wrap.querySelector('.p-tag');
        if (ta.value.trim()) {
            variants.push({
                id: i + 1,
                text: ta.value.trim(),
                strategy: tag ? tag.dataset.strat : 'zero-shot'
            });
        }
    });

    if (variants.length === 0) return toast('Enter at least one prompt variant', 'error');

    const btn = document.getElementById('btn-run-eval');
    btn.disabled = true;
    showLoading('Evaluating prompts...', `Testing ${variants.length} variant${variants.length > 1 ? 's' : ''} concurrently with ${selectedModel}`);

    try {
        const res = await fetch('/api/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                reference_answer: ref || null,
                prompt_variants: variants,
                model: selectedModel,
                temperature: 0.7,
                use_judge: fastMode ? false : useJudge,
                assertions: assertions.length > 0 ? assertions : null,
                context: fastMode ? null : (context || null),
                fast_mode: fastMode,
                max_tokens: fastMode ? 160 : null
            })
        });

        if (!res.ok) { const err = await res.text(); throw new Error(err); }
        currentResults = await res.json();

        // Auto-save best result to history
        if (currentResults.length > 0) {
            const best = currentResults[0];
            fetch('/api/history/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: best.prompt_text, expected_output: ref || '',
                    llm_output: best.llm_output, model_name: selectedModel,
                    score: best.overall_score,
                    judge_score: useJudge ? best.scores.judge * 10 : null,
                    semantic_similarity: best.scores.semantic_similarity,
                    feedback: best.feedback || '', timestamp: new Date().toISOString()
                })
            }).catch(() => { });
        }

        hideLoading();
        renderResults();
        showPage('results');
        toast(`Evaluation complete — best score: ${currentResults[0].overall_score.toFixed(1)}`, 'success');

    } catch (e) {
        hideLoading();
        toast('Evaluation failed: ' + e.message, 'error');
        console.error(e);
    } finally {
        btn.disabled = false;
    }
}

function renderAssertionBadges(assertionData) {
    if (!assertionData || !assertionData.results || assertionData.results.length === 0) return '';
    const allPassed = assertionData.all_passed;
    const badge = allPassed
        ? `<span class="pill pill-g">✓ Assert ${assertionData.passed}/${assertionData.total}</span>`
        : `<span class="pill pill-r">✗ Assert ${assertionData.passed}/${assertionData.total}</span>`;

    const details = assertionData.results.map(r =>
        `<div class="assert-result ${r.passed ? 'pass' : 'fail'}">
            <span>${r.passed ? '✓' : '✗'}</span>
            <span>${r.rule_type}: ${r.detail}</span>
        </div>`
    ).join('');

    return badge + `<div class="assert-details">${details}</div>`;
}

function renderRagBadges(ragData) {
    if (!ragData) return '';
    const faith = ragData.faithfulness;
    const relev = ragData.relevance;
    let html = '';
    if (faith) {
        const fColor = faith.score >= 7 ? 'pill-g' : faith.score >= 4 ? 'pill-b' : 'pill-r';
        html += `<span class="pill ${fColor}" title="${faith.explanation}">Faith: ${faith.score}/10</span>`;
    }
    if (relev) {
        const rColor = relev.score >= 7 ? 'pill-g' : relev.score >= 4 ? 'pill-b' : 'pill-r';
        html += `<span class="pill ${rColor}" title="${relev.explanation}">Relev: ${relev.score}/10</span>`;
    }
    return html;
}

function renderResults() {
    if (!currentResults.length) return;

    const best = currentResults[0];
    const avgScore = currentResults.reduce((a, b) => a + b.overall_score, 0) / currentResults.length;
    const hallucinations = currentResults.filter(r => r.hallucination_detected).length;
    const totalTime = currentResults.reduce((a, b) => a + (b.processing_time_ms || 0), 0);

    document.getElementById('results-stats').innerHTML = `
        <div class="stat-card"><div class="stat-label">Best Score</div><div class="stat-value" style="color:var(--green)">${best.overall_score.toFixed(1)}</div><div class="stat-sub">Variant #${best.variant_id}</div></div>
        <div class="stat-card"><div class="stat-label">Avg Score</div><div class="stat-value">${avgScore.toFixed(1)}</div><div class="stat-sub">${currentResults.length} variants</div></div>
        <div class="stat-card"><div class="stat-label">Hallucinations</div><div class="stat-value" style="color:${hallucinations > 0 ? 'var(--red)' : 'var(--green)'}">${hallucinations}</div><div class="stat-sub">detected</div></div>
        <div class="stat-card"><div class="stat-label">Total Time</div><div class="stat-value">${(totalTime / 1000).toFixed(1)}s</div><div class="stat-sub">processing</div></div>
    `;

    const container = document.getElementById('results-cards');
    container.innerHTML = '';

    currentResults.forEach((res, idx) => {
        const isBest = idx === 0;
        const color = scoreColor(res.overall_score);
        const barWidth = Math.min(100, res.overall_score);

        container.innerHTML += `
        <div class="result-card ${isBest ? 'best' : ''}">
            ${isBest ? '<div class="best-badge">★ Best</div>' : ''}
            <div class="rank-row">
                <span class="rank-label">Rank ${idx + 1} · ${res.strategy}</span>
                <span class="rank-score ${scoreClass(res.overall_score)}">${res.overall_score.toFixed(1)}</span>
            </div>
            <div class="prompt-chip">${truncate(res.prompt_text, 120)}</div>
            <div class="response-text">${truncate(res.llm_output, 200)}</div>
            <div class="pill-row">
                <span class="pill pill-v">Sim: ${res.scores.semantic_similarity ? (res.scores.semantic_similarity * 100).toFixed(0) + '%' : '—'}</span>
                <span class="pill pill-b">BLEU: ${res.scores.bleu ? (res.scores.bleu * 100).toFixed(0) + '%' : '—'}</span>
                <span class="pill pill-g">ROUGE: ${res.scores.rouge1 ? (res.scores.rouge1 * 100).toFixed(0) + '%' : '—'}</span>
                ${useJudge ? `<span class="pill pill-v">Judge: ${res.scores.judge ? (res.scores.judge * 100).toFixed(0) + '%' : '—'}</span>` : ''}
                <span class="pill ${res.hallucination_detected ? 'pill-r' : 'pill-g'}">${res.hallucination_detected ? '⚠ Halluc' : '✓ Safe'}</span>
                ${renderRagBadges(res.rag)}
            </div>
            ${res.assertions && res.assertions.results && res.assertions.results.length > 0 ? `
            <div class="assert-section">
                ${renderAssertionBadges(res.assertions)}
            </div>` : ''}
            <div class="score-bar-row">
                <span style="font-size:10px;color:var(--text-muted)">Score</span>
                <div class="bar-bg"><div class="bar-fg" style="width:${barWidth}%;background:${color}"></div></div>
                <span class="score-num" style="color:${color}">${res.overall_score.toFixed(1)}</span>
            </div>
            <div style="font-size:10px;color:var(--text-muted);margin-top:6px">${res.word_count} words · ${(res.processing_time_ms / 1000).toFixed(1)}s</div>
        </div>`;
    });

    // Error Analysis
    const worst = currentResults[currentResults.length - 1];
    document.getElementById('results-analysis').innerHTML = `
        <div class="card-title">Analysis — Rank ${currentResults.length} (worst)</div>
        <div class="err-row">
            <div class="err-icon ${worst.hallucination_detected ? 'ic-r' : 'ic-g'}">${worst.hallucination_detected ? '!' : '✓'}</div>
            <div><div class="err-title">${worst.hallucination_detected ? 'Hallucination risk detected' : 'Factually safe'}</div>
            <div class="err-desc">Semantic similarity: ${worst.scores.semantic_similarity ? (worst.scores.semantic_similarity * 100).toFixed(0) + '%' : 'N/A'}</div></div>
        </div>
        <div class="err-row">
            <div class="err-icon ic-a">↔</div>
            <div><div class="err-title">Word count: ${worst.word_count}</div>
            <div class="err-desc">Response length metric</div></div>
        </div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:10px;font-style:italic;line-height:1.5">${worst.feedback || 'No detailed feedback available.'}</div>
    `;

    document.getElementById('results-suggestions').innerHTML = `
        <div class="card-title">Recommendations</div>
        <div class="next-row"><span class="arr">→</span>Adopt the strategy from Rank 1 (${best.strategy})</div>
        <div class="next-row"><span class="arr">→</span>Click "Improve worst" to auto-optimize</div>
        ${worst.scores.semantic_similarity && worst.scores.semantic_similarity < 0.5 ?
            '<div class="next-row"><span class="arr">→</span>Low similarity — add more specific context to the prompt</div>' : ''}
        ${worst.word_count > 200 ?
            '<div class="next-row"><span class="arr">→</span>Response too long — add word limit constraints</div>' : ''}
        <div class="improved-prompt" style="margin-top:10px">Tip: Add "You are an expert in [topic]. Answer in under ${Math.max(30, (worst.word_count * 0.5) | 0)} words." to tighten output.</div>
    `;
}


// ═══════════════════════════════════
// OPTIMIZE
// ═══════════════════════════════════

async function runOptimize() {
    if (!currentResults.length) return;
    const worst = currentResults[currentResults.length - 1];
    const ref = document.getElementById('reference-input').value.trim();

    if (!ref) return toast('Reference answer is required for optimization', 'error');

    const btn = document.getElementById('btn-improve');
    btn.disabled = true;
    showLoading('Optimizing prompt...', 'Running up to 3 improvement attempts');

    try {
        const res = await fetch('/api/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                original_prompt: worst.prompt_text, expected_output: ref,
                current_score: worst.overall_score, model: selectedModel, use_judge: useJudge
            })
        });

        if (!res.ok) throw new Error(await res.text());
        optimizeResult = await res.json();

        const diffCard = typeof PromptDiff !== 'undefined'
            ? `<div class="card">
                <div class="card-title">Prompt version diff</div>
                ${PromptDiff.promptDiffPanelHtml(
                    optimizeResult.original_prompt,
                    optimizeResult.improved_prompt,
                    optimizeResult.original_score,
                    optimizeResult.improved_score,
                    'Evaluate → Improve worst'
                )}
            </div>`
            : `<div class="two-col">
                <div class="card">
                    <div class="card-title" style="color:var(--red)">Original prompt — ${optimizeResult.original_score.toFixed(1)}</div>
                    <div class="prompt-chip">${optimizeResult.original_prompt}</div>
                </div>
                <div class="card">
                    <div class="card-title" style="color:var(--green)">Improved prompt — ${optimizeResult.improved_score.toFixed(1)}</div>
                    <div class="improved-prompt">${optimizeResult.improved_prompt}</div>
                </div>
            </div>`;

        document.getElementById('optimize-body').innerHTML = `
            <div class="stats-row">
                <div class="stat-card"><div class="stat-label">Original</div><div class="stat-value" style="color:var(--red)">${optimizeResult.original_score.toFixed(1)}</div></div>
                <div class="stat-card"><div class="stat-label">Improved</div><div class="stat-value" style="color:var(--green)">${optimizeResult.improved_score.toFixed(1)}</div></div>
                <div class="stat-card"><div class="stat-label">Gain</div><div class="stat-value" style="color:var(--accent)">${optimizeResult.improvement_percent > 0 ? '+' : ''}${optimizeResult.improvement_percent.toFixed(1)}%</div></div>
                <div class="stat-card"><div class="stat-label">Status</div><div class="stat-value" style="color:${optimizeResult.did_improve ? 'var(--green)' : 'var(--yellow)'}">${optimizeResult.did_improve ? '✓' : '—'}</div><div class="stat-sub">${optimizeResult.did_improve ? 'Improved' : 'No improvement found'}</div></div>
            </div>
            ${diffCard}
            <div class="card">
                <div class="card-title">Change summary</div>
                ${optimizeResult.changes_made.map(c => `<div style="display:flex;gap:6px;font-size:12px;color:var(--text-secondary);padding:3px 0"><span style="color:var(--green)">✓</span>${c}</div>`).join('')}
            </div>
            ${optimizeResult.new_response ? `
            <div class="card">
                <div class="card-title">New model response</div>
                <div style="font-size:12px;color:var(--text-muted);line-height:1.6">${optimizeResult.new_response}</div>
            </div>` : ''}
        `;

        hideLoading();
        showPage('optimize');
        fetchIterations(false);
        toast(optimizeResult.did_improve ? `Score improved: ${optimizeResult.original_score.toFixed(1)} → ${optimizeResult.improved_score.toFixed(1)}` : 'Could not improve — original prompt kept', optimizeResult.did_improve ? 'success' : 'info');

    } catch (e) {
        hideLoading();
        toast('Optimization failed: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

function applyOptimized() {
    if (optimizeResult && optimizeResult.improved_prompt) {
        addPrompt();
        const tas = document.querySelectorAll('#prompt-list textarea');
        const last = tas[tas.length - 1];
        last.value = optimizeResult.improved_prompt;
        checkQuality(last);
        showPage('evaluate');
        toast('Improved prompt added to your variants', 'success');
    }
}


// ═══════════════════════════════════
// DATASET MODE (batch evaluation)
// ═══════════════════════════════════

function setupDragDrop() {
    const zone = document.getElementById('upload-zone');
    if (!zone) return;
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', (e) => {
        e.preventDefault(); zone.classList.remove('drag-over');
        if (e.dataTransfer.files.length) handleCSVFile(e.dataTransfer.files[0]);
    });
}

function handleCSVUpload(e) { if (e.target.files.length) handleCSVFile(e.target.files[0]); }

function handleCSVFile(file) {
    if (!file.name.endsWith('.csv')) return toast('Please upload a .csv file', 'error');
    const reader = new FileReader();
    reader.onload = function (evt) { parseCSV(evt.target.result); };
    reader.readAsText(file);
}

function parseCSV(text) {
    const lines = text.split('\n').filter(l => l.trim());
    if (lines.length < 2) return toast('CSV must have a header row and at least one data row', 'error');
    const headers = parseCSVLine(lines[0]).map(h => h.toLowerCase().trim());
    const promptIdx = headers.findIndex(h => h === 'prompt' || h === 'question');
    const expectedIdx = headers.findIndex(h => h === 'expected_output' || h === 'expected' || h === 'answer');
    const categoryIdx = headers.findIndex(h => h === 'category');
    if (promptIdx === -1) return toast('CSV must have a "prompt" or "question" column', 'error');

    datasetPrompts = [];
    for (let i = 1; i < lines.length; i++) {
        const fields = parseCSVLine(lines[i]);
        const prompt = (fields[promptIdx] || '').trim();
        if (!prompt) continue;
        datasetPrompts.push({
            prompt,
            expected_output: expectedIdx >= 0 ? (fields[expectedIdx] || '').trim() : '',
            category: categoryIdx >= 0 ? (fields[categoryIdx] || 'General').trim() : 'General'
        });
    }

    document.getElementById('ds-count').textContent = datasetPrompts.length;
    document.getElementById('ds-badge').textContent = datasetPrompts.length + ' loaded';

    const tbody = document.getElementById('ds-table-body');
    tbody.innerHTML = '';
    datasetPrompts.forEach((p, i) => {
        tbody.innerHTML += `<tr>
            <td style="color:var(--text-muted)">${i + 1}</td>
            <td style="font-size:11px">${truncate(p.prompt, 60)}</td>
            <td style="font-size:11px;color:var(--text-muted)">${truncate(p.expected_output, 40)}</td>
        </tr>`;
    });
    
    // Reset views
    document.getElementById('ds-standard-view').style.display = '';
    document.getElementById('ds-optimized-view').style.display = 'none';
    document.getElementById('btn-opt-batch').style.display = 'none';
    document.getElementById('btn-export-opt').style.display = 'none';
    document.getElementById('btn-export-bundle-ds').style.display = 'none';
    window._datasetBatchResults = null;

    toast(`Loaded ${datasetPrompts.length} questions from CSV`, 'success');
}

function parseCSVLine(line) {
    const result = []; let current = ''; let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') { if (inQuotes && i + 1 < line.length && line[i + 1] === '"') { current += '"'; i++; } else { inQuotes = !inQuotes; } }
        else if (ch === ',' && !inQuotes) { result.push(current); current = ''; }
        else { current += ch; }
    }
    result.push(current);
    return result.map(f => f.replace(/^"|"$/g, '').trim());
}

function clearDataset() {
    datasetPrompts = [];
    window._datasetBatchResults = null;
    document.getElementById('ds-count').textContent = '0';
    document.getElementById('ds-evaluated').textContent = '0';
    document.getElementById('ds-avg').textContent = '—';
    document.getElementById('ds-time').textContent = '—';
    document.getElementById('ds-badge').textContent = '0 loaded';
    document.getElementById('ds-table-body').innerHTML = '<tr><td colspan="3" class="empty-state">Upload a CSV to start</td></tr>';
    document.getElementById('ds-results-body').innerHTML = '<tr><td colspan="4" class="empty-state">Run evaluation to see results</td></tr>';
    
    document.getElementById('ds-standard-view').style.display = '';
    document.getElementById('ds-optimized-view').style.display = 'none';
    document.getElementById('btn-opt-batch').style.display = 'none';
    document.getElementById('btn-export-opt').style.display = 'none';
    document.getElementById('btn-export-bundle-ds').style.display = 'none';
}

async function runBatchEval() {
    if (datasetPrompts.length === 0) return toast('Upload a CSV dataset first', 'error');
    const btn = document.getElementById('btn-run-batch');
    btn.disabled = true;
    const startTime = Date.now();
    showLoading('Batch evaluation...', `Processing ${datasetPrompts.length} prompts with ${selectedModel}`);

    try {
        const startRes = await fetch('/api/jobs/batch/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompts: datasetPrompts, model: selectedModel,
                temperature: 0.7,
                use_judge: fastMode ? false : useJudge,
                fast_mode: fastMode,
                max_tokens: fastMode ? 128 : null
            })
        });
        if (!startRes.ok) throw new Error(await startRes.text());
        const { job_id: jobId } = await startRes.json();

        const batchResults = await waitForStreamingJob(jobId, (evt) => {
            if (evt.type !== 'progress') return;
            const percent = evt.progress || 0;
            const msg = evt.message || `Processed ${evt.completed || 0}/${evt.total || datasetPrompts.length}`;
            updateLoading(percent, msg);
        });
        
        window._datasetBatchResults = batchResults;

        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        const avgScore = batchResults.length > 0 ? batchResults.reduce((a, b) => a + b.score, 0) / batchResults.length : 0;

        document.getElementById('ds-evaluated').textContent = batchResults.length;
        document.getElementById('ds-avg').textContent = avgScore.toFixed(1);
        document.getElementById('ds-time').textContent = elapsed + 's';

        const tbody = document.getElementById('ds-results-body');
        tbody.innerHTML = '';
        
        let hasFailures = false;
        batchResults.forEach(r => {
            if (r.score < (r.score <= 1.0 ? 0.70 : 70.0)) hasFailures = true;
            tbody.innerHTML += `<tr>
                <td style="color:var(--text-muted)">${r.index}</td>
                <td style="font-size:10px" title="${r.prompt}">${truncate(r.prompt, 50)}</td>
                <td><span class="chip ${chipClass(r.score)}">${r.score.toFixed(1)}</span></td>
                <td style="font-size:10px;color:var(--text-muted)">${r.time_ms ? (r.time_ms / 1000).toFixed(1) + 's' : '—'}</td>
            </tr>`;
        });

        if (hasFailures) {
            document.getElementById('btn-opt-batch').style.display = '';
        }
        document.getElementById('btn-export-bundle-ds').style.display = '';

        hideLoading();
        toast(`Batch complete — ${batchResults.length} prompts, avg: ${avgScore.toFixed(1)}`, 'success');
    } catch (e) {
        hideLoading();
        toast('Batch evaluation failed: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}
// ═══════════════════════════════════
// DATASET OPTIMIZATION
// ═══════════════════════════════════

async function runDatasetOptimize() {
    if (!window._datasetBatchResults || window._datasetBatchResults.length === 0) return;
    
    const btn = document.getElementById('btn-opt-batch');
    const exportBtn = document.getElementById('btn-export-opt');
    btn.disabled = true;
    exportBtn.style.display = 'none';
    
    showLoading('Optimizing Prompts...', 'Rewriting failing prompts using LLM...');

    try {
        const payload = {
            model: selectedModel,
            use_judge: fastMode ? false : useJudge,
            fast_mode: fastMode,
            items: window._datasetBatchResults.map(r => ({
                prompt: r.prompt,
                expected_output: r.expected,
                score: r.score,
                category: r.category || 'General'
            }))
        };

        const res = await fetch('/api/optimize/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        const results = data.results;
        const summary = data.summary;
        
        // Store for export
        window._optimizedDataset = results;
        
        // Update Stats Row
        document.getElementById('ds-avg').innerHTML = `<span style="text-decoration:line-through;opacity:0.6">${summary.original_avg_score.toFixed(1)}</span> <span style="color:var(--green)">${summary.new_avg_score.toFixed(1)}</span>`;
        document.getElementById('ds-evaluated').innerHTML = `${summary.total_prompts} <span style="font-size:10px;color:var(--green)">(${summary.prompts_optimized} fixed)</span>`;
        
        // Switch Views
        document.getElementById('ds-standard-view').style.display = 'none';
        document.getElementById('ds-optimized-view').style.display = '';
        exportBtn.style.display = '';
        btn.style.display = 'none';
        
        // Render optimized results table
        const tbody = document.getElementById('ds-opt-results-body');
        tbody.innerHTML = '';
        
        results.forEach(r => {
            const isImproved = r.status === 'optimized';
            const unchanged = r.status === 'passed';
            
            const origColor = scoreColor(r.original_score);
            const newColor = scoreColor(r.improved_score);
            
            let gainHtml = '';
            if (unchanged) {
                gainHtml = `<span style="color:var(--text-muted);font-size:11px">Already passed (${r.original_score.toFixed(1)})</span>`;
            } else if (isImproved) {
                let itHtml = r.iterations && r.iterations.length > 0 ? `<div style="font-size:9px;color:var(--text-muted);margin-top:4px">${r.iterations.length} iterations run</div>` : '';
                gainHtml = `<span style="color:var(--green);font-weight:700">+${r.improvement_percent.toFixed(1)}%</span>
                            <div style="font-size:10px;margin-top:2px"><span style="color:${origColor}">${r.original_score.toFixed(1)}</span> → <span style="color:${newColor}">${r.improved_score.toFixed(1)}</span></div>${itHtml}`;
            } else {
                let itHtml = r.iterations && r.iterations.length > 0 ? `<div style="font-size:9px;color:var(--text-muted);margin-top:4px">${r.iterations.length} iterations run</div>` : '';
                gainHtml = `<span style="color:var(--yellow);font-size:11px">Failed to improve</span>
                            <div style="font-size:10px;margin-top:2px"><span style="color:${origColor}">${r.original_score.toFixed(1)}</span> → <span style="color:${newColor}">${r.improved_score.toFixed(1)}</span></div>${itHtml}`;
            }
            
            const diffBtn = typeof PromptDiff === 'undefined'
                ? '<span style="color:var(--text-muted);font-size:11px">—</span>'
                : `<button type="button" class="btn-view" onclick="openOptimizedRowDiff(${r.index})">View diff</button>`;

            tbody.innerHTML += `<tr>
                <td style="color:var(--text-muted)">${r.index}</td>
                <td style="font-size:11px;font-family:var(--mono);color:var(--text-secondary)" title="${r.original_prompt.replace(/"/g, '&quot;')}">${truncate(r.original_prompt, 80)}</td>
                <td style="font-size:11px;font-family:var(--mono);color:${isImproved ? 'var(--green)' : 'var(--text-secondary)'}" title="${r.improved_prompt.replace(/"/g, '&quot;')}">${truncate(r.improved_prompt, 80)}</td>
                <td>${gainHtml}</td>
                <td>${diffBtn}</td>
            </tr>`;
        });
        
        hideLoading();
        fetchIterations(false);
        toast(`Optimization completed. Fixed ${summary.prompts_optimized} out of ${summary.total_prompts} prompts.`, 'success');

    } catch (e) {
        hideLoading();
        toast('Optimization failed: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

function exportOptimizedCSV() {
    if (!window._optimizedDataset || window._optimizedDataset.length === 0) return;

    const headers = ['id', 'category', 'original_prompt', 'optimized_prompt', 'original_score', 'optimized_score', 'status'];
    const headerLine = headers.map(csvEscapeField).join(',');
    const dataLines = window._optimizedDataset.map(r =>
        [
            csvEscapeField(r.index),
            csvEscapeField(r.category || 'General'),
            csvEscapeField(r.original_prompt),
            csvEscapeField(r.improved_prompt),
            csvEscapeField(r.original_score),
            csvEscapeField(r.improved_score),
            csvEscapeField(r.status)
        ].join(',')
    );
    const csvContent = buildExcelCsv([headerLine, ...dataLines]);

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `optimized_dataset_${new Date().toISOString().slice(0, 10)}.csv`;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}


// ═══════════════════════════════════
// COMPARE PROMPTS
// ═══════════════════════════════════

async function runCompare() {
    const raw = document.getElementById('compare-prompts').value;
    const prompts = raw.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    const expected = document.getElementById('compare-expected').value.trim();
    if (prompts.length < 2) return toast('Enter at least 2 prompts (one per line)', 'error');
    if (!expected) return toast('Enter the expected output', 'error');

    showLoading('Comparing prompts...', `Testing ${prompts.length} prompts with ${selectedModel}`);

    try {
        const res = await fetch('/api/compare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: '', prompts, expected_output: expected,
                model: selectedModel,
                temperature: 0.7,
                use_judge: fastMode ? false : useJudge,
                fast_mode: fastMode,
                max_tokens: fastMode ? 160 : null
            })
        });
        if (!res.ok) throw new Error(await res.text());
        const ranked = await res.json();

        const grid = document.getElementById('compare-grid');
        grid.innerHTML = '';
        ranked.forEach((r, idx) => {
            const isWinner = idx === 0;
            grid.innerHTML += `
            <div class="compare-card ${isWinner ? 'winner' : ''}">
                <div class="compare-head">
                    <div class="compare-title">Rank ${r.rank}</div>
                    ${isWinner ? '<span class="chip chip-hi">★ Winner</span>' : ''}
                </div>
                <div class="prompt-chip">${truncate(r.prompt, 100)}</div>
                <div class="compare-stat"><span class="cs-label">Overall Score</span><span class="cs-val ${isWinner ? 'green' : ''}">${r.score.toFixed(1)}</span></div>
                <div class="compare-stat"><span class="cs-label">Similarity</span><span class="cs-val">${r.similarity ? (r.similarity * 100).toFixed(0) + '%' : '—'}</span></div>
                <div class="compare-stat"><span class="cs-label">BLEU</span><span class="cs-val">${r.bleu ? (r.bleu * 100).toFixed(0) + '%' : '—'}</span></div>
                <div class="compare-stat"><span class="cs-label">ROUGE-1</span><span class="cs-val">${r.rouge1 ? (r.rouge1 * 100).toFixed(0) + '%' : '—'}</span></div>
                ${r.judge_score !== null && r.judge_score !== undefined ? `<div class="compare-stat"><span class="cs-label">Judge</span><span class="cs-val">${r.judge_score}/10</span></div>` : ''}
                <div class="compare-stat"><span class="cs-label">Time</span><span class="cs-val">${r.time_ms ? (r.time_ms / 1000).toFixed(1) + 's' : '—'}</span></div>
                <div class="compare-response">${r.llm_output || 'No output'}</div>
            </div>`;
        });

        hideLoading();
        toast('Comparison complete!', 'success');
    } catch (e) {
        hideLoading();
        toast('Compare failed: ' + e.message, 'error');
    }
}


// ═══════════════════════════════════
// MATRIX (Multi-Model Grid Testing)
// ═══════════════════════════════════

function populateMatrixModels() {
    const container = document.getElementById('matrix-model-checkboxes');
    if (!container) return;
    const models = window._availableModels || [];
    if (models.length === 0) {
        container.innerHTML = '<div class="matrix-model-loading">No models available — is Ollama running?</div>';
        return;
    }
    container.innerHTML = models.map((m, i) =>
        `<label class="matrix-model-checkbox">
            <input type="checkbox" value="${m.name}" ${i < 2 ? 'checked' : ''}>
            <span class="model-check-name">${m.name}</span>
            <span class="model-check-tag">${m.speed_tag || 'standard'}</span>
        </label>`
    ).join('');
}

function getSelectedMatrixModels() {
    const checkboxes = document.querySelectorAll('#matrix-model-checkboxes input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

async function runMatrix() {
    const raw = document.getElementById('matrix-prompts').value;
    const prompts = raw.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    const expected = document.getElementById('matrix-expected').value.trim();
    const models = getSelectedMatrixModels();
    const matrixJudge = document.getElementById('matrix-judge-toggle')?.checked || false;

    if (prompts.length === 0) return toast('Enter at least one prompt', 'error');
    if (models.length < 2) return toast('Select at least 2 models to compare', 'error');

    const btn = document.getElementById('btn-run-matrix');
    btn.disabled = true;
    showLoading('Running matrix evaluation...', `${prompts.length} prompts × ${models.length} models = ${prompts.length * models.length} evaluations`);

    try {
        const startRes = await fetch('/api/jobs/matrix/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompts, models, expected_output: expected,
                temperature: 0.7,
                use_judge: fastMode ? false : matrixJudge,
                assertions: assertions.length > 0 ? assertions : null,
                fast_mode: fastMode,
                max_tokens: fastMode ? 160 : null
            })
        });
        if (!startRes.ok) throw new Error(await startRes.text());
        const { job_id: jobId } = await startRes.json();

        const result = await waitForStreamingJob(jobId, (evt) => {
            if (evt.type !== 'progress') return;
            const percent = evt.progress || 0;
            const msg = evt.message || `Processed ${evt.completed || 0}/${evt.total || (prompts.length * models.length)} matrix cells`;
            updateLoading(percent, msg);
        });

        renderMatrix(result);
        hideLoading();
        toast(`Matrix complete — best: ${result.summary.best_model} (${result.summary.best_score})`, 'success');
    } catch (e) {
        hideLoading();
        toast('Matrix evaluation failed: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

async function waitForStreamingJob(jobId, onProgress) {
    return new Promise((resolve, reject) => {
        let done = false;
        const es = new EventSource(`/api/jobs/${jobId}/events`);

        es.onmessage = async (msg) => {
            if (!msg || !msg.data) return;
            let evt;
            try {
                evt = JSON.parse(msg.data);
            } catch (_) {
                return;
            }

            if (evt.type === 'progress') {
                if (typeof onProgress === 'function') onProgress(evt);
                return;
            }
            if (evt.type === 'heartbeat' || evt.type === 'started') return;
            if (evt.type === 'error') {
                done = true;
                es.close();
                reject(new Error(evt.message || 'Job failed'));
                return;
            }
            if (evt.type === 'complete') {
                try {
                    const res = await fetch(`/api/jobs/${jobId}/result`);
                    if (!res.ok) throw new Error('Could not fetch job result');
                    const finalPayload = await res.json();
                    if (finalPayload.status !== 'completed') {
                        throw new Error(finalPayload.error || 'Job did not complete');
                    }
                    done = true;
                    es.close();
                    resolve(finalPayload.result);
                } catch (e) {
                    done = true;
                    es.close();
                    reject(e);
                }
            }
        };

        es.onerror = async () => {
            if (done) return;
            // Fallback: if stream disconnects near completion, try reading final result once.
            try {
                const res = await fetch(`/api/jobs/${jobId}/result`);
                if (res.ok) {
                    const finalPayload = await res.json();
                    if (finalPayload.status === 'completed') {
                        done = true;
                        es.close();
                        resolve(finalPayload.result);
                        return;
                    }
                }
            } catch (_) { }
            done = true;
            es.close();
            reject(new Error('Progress stream disconnected'));
        };
    });
}

function renderMatrix(data) {
    const container = document.getElementById('matrix-results');
    if (!data || !data.rows || data.rows.length === 0) {
        container.innerHTML = '<div class="empty-state">No results</div>';
        return;
    }

    const models = data.models;
    const summary = data.summary;

    // Summary stats
    let html = `<div class="stats-row" style="margin-bottom:16px">
        <div class="stat-card"><div class="stat-label">Best Model</div><div class="stat-value" style="color:var(--green);font-size:16px">${summary.best_model}</div><div class="stat-sub">highest score</div></div>
        <div class="stat-card"><div class="stat-label">Best Score</div><div class="stat-value" style="color:var(--green)">${summary.best_score}</div><div class="stat-sub">overall</div></div>
        <div class="stat-card"><div class="stat-label">Evaluations</div><div class="stat-value">${summary.total_evaluations}</div><div class="stat-sub">completed</div></div>
        <div class="stat-card"><div class="stat-label">Total Time</div><div class="stat-value">${(summary.total_time_ms / 1000).toFixed(1)}s</div><div class="stat-sub">wall clock</div></div>
    </div>`;

    // Matrix grid table
    html += `<div class="card" style="overflow-x:auto">
        <div class="card-title">Results Grid</div>
        <table class="matrix-table">
            <thead><tr>
                <th class="matrix-header-prompt">Prompt</th>
                ${models.map(m => `<th class="matrix-header-model">${m}</th>`).join('')}
            </tr></thead>
            <tbody>`;

    data.rows.forEach((row, rIdx) => {
        // Find best in this row
        const rowBestScore = Math.max(...row.cells.map(c => c.score));
        html += `<tr>
            <td class="matrix-prompt-cell" title="${row.prompt_full || row.prompt}">${truncate(row.prompt, 50)}</td>`;
        row.cells.forEach(cell => {
            const isBest = cell.score === rowBestScore && cell.score > 0;
            const color = scoreColor(cell.score);
            const assertBadge = cell.assertions && cell.assertions.total > 0
                ? `<div class="matrix-assert ${cell.assertions.all_passed ? 'pass' : 'fail'}">${cell.assertions.all_passed ? '✓' : '✗'} ${cell.assertions.passed}/${cell.assertions.total}</div>`
                : '';
            html += `<td class="matrix-cell ${isBest ? 'matrix-cell-best' : ''}" title="${truncate(cell.llm_output, 200)}">
                <div class="matrix-score" style="color:${color}">${cell.score.toFixed(1)}</div>
                <div class="matrix-time">${(cell.time_ms / 1000).toFixed(1)}s</div>
                ${isBest ? '<div class="matrix-star">★</div>' : ''}
                ${assertBadge}
                ${cell.error ? '<div class="matrix-error">Error</div>' : ''}
            </td>`;
        });
        html += `</tr>`;
    });

    html += `</tbody></table></div>`;
    container.innerHTML = html;
}


// ═══════════════════════════════════
// HISTORY
// ═══════════════════════════════════

async function fetchHistory() {
    try {
        const res = await fetch('/api/history?limit=100');
        if (!res.ok) return;
        const hist = await res.json();

        const badge = document.getElementById('nav-badge-history');
        if (hist.length > 0) { badge.textContent = hist.length; badge.style.display = ''; }
        else { badge.style.display = 'none'; }

        document.getElementById('history-count').textContent = hist.length + ' total runs';

        const avg = hist.length ? hist.reduce((a, b) => a + (b.score || 0), 0) / hist.length : 0;
        const bestScore = hist.length ? Math.max(...hist.map(h => h.score || 0)) : 0;

        document.getElementById('history-stats').innerHTML = `
            <div class="stat-card"><div class="stat-label">Total Runs</div><div class="stat-value">${hist.length}</div><div class="stat-sub">all time</div></div>
            <div class="stat-card"><div class="stat-label">Avg Score</div><div class="stat-value">${avg.toFixed(1)}</div><div class="stat-sub">overall</div></div>
            <div class="stat-card"><div class="stat-label">Best Score</div><div class="stat-value" style="color:var(--green)">${bestScore.toFixed(1)}</div><div class="stat-sub">all time best</div></div>
            <div class="stat-card"><div class="stat-label">Models Used</div><div class="stat-value">${new Set(hist.map(h => h.model_name)).size}</div><div class="stat-sub">unique</div></div>
        `;

        const tbody = document.getElementById('history-table-body');
        tbody.innerHTML = '';
        if (hist.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No evaluations yet. Run your first evaluation!</td></tr>';
            return;
        }
        hist.forEach(h => {
            const sc = h.score || 0;
            tbody.innerHTML += `<tr>
                <td style="color:var(--text-muted);font-size:11px;white-space:nowrap">${h.timestamp ? new Date(h.timestamp).toLocaleString() : '—'}</td>
                <td style="font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${(h.prompt || '').replace(/"/g, '&quot;')}">${truncate(h.prompt, 50)}</td>
                <td><span class="mono">${h.model_name || '—'}</span></td>
                <td><span class="chip ${chipClass(sc)}">${sc.toFixed(1)}</span></td>
                <td style="font-size:11px">${h.semantic_similarity ? (h.semantic_similarity * 100).toFixed(0) + '%' : '—'}</td>
                <td style="font-size:10px;color:var(--text-muted);max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${(h.feedback || '').replace(/"/g, '&quot;')}">${truncate(h.feedback, 40)}</td>
                <td><button class="btn-view" onclick="viewHistoryEntry(${h.id})">View</button></td>
            </tr>`;
        });
    } catch (e) {
        console.error('History fetch error:', e);
    }
}

async function clearAllHistory() {
    if (!confirm('Clear all evaluation history? This cannot be undone.')) return;
    try {
        await fetch('/api/history/clear', { method: 'POST' });
        await fetchHistory();
        toast('History cleared', 'info');
    } catch (e) {
        toast('Failed to clear history', 'error');
    }
}


// ═══════════════════════════════════
// VIEW HISTORY ENTRY (Session Detail)
// ═══════════════════════════════════

async function viewHistoryEntry(entryId) {
    const modal = document.getElementById('history-detail-modal');
    const body = document.getElementById('history-detail-body');
    body.innerHTML = '<div class="empty-state" style="padding:40px">Loading evaluation details...</div>';
    modal.classList.add('active');

    try {
        const res = await fetch(`/api/history/${entryId}`);
        if (!res.ok) throw new Error(await res.text());
        const entry = await res.json();

        const sc = entry.score || 0;
        const sim = entry.semantic_similarity;
        const judge = entry.judge_score;

        body.innerHTML = `
            <!-- Meta info -->
            <div class="detail-section">
                <div class="detail-meta">
                    <span>📅 ${entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '—'}</span>
                    <span>🤖 ${entry.model_name || '—'}</span>
                    <span>🆔 #${entry.id}</span>
                    ${entry.lineage_id ? `<span>🔗 Lineage: ${entry.lineage_id.substring(0,8)}…</span>` : ''}
                    ${entry.iteration !== null && entry.iteration !== undefined ? `<span>🔄 Iteration ${entry.iteration}</span>` : ''}
                </div>
            </div>

            <!-- Scores -->
            <div class="detail-section">
                <div class="detail-section-title"><span class="detail-icon ic-g">📊</span> Scores</div>
                <div class="detail-scores-grid">
                    <div class="detail-score-pill">
                        <div class="ds-label">Overall Score</div>
                        <div class="ds-value" style="color:${scoreColor(sc)}">${sc.toFixed(1)}</div>
                    </div>
                    <div class="detail-score-pill">
                        <div class="ds-label">Similarity</div>
                        <div class="ds-value" style="color:${sim ? scoreColor(sim * 100) : 'var(--text-muted)'}">${sim ? (sim * 100).toFixed(1) + '%' : '—'}</div>
                    </div>
                    <div class="detail-score-pill">
                        <div class="ds-label">Judge Score</div>
                        <div class="ds-value" style="color:${judge ? scoreColor(judge * 10) : 'var(--text-muted)'}">${judge !== null && judge !== undefined ? judge.toFixed(1) + '/10' : '—'}</div>
                    </div>
                </div>
            </div>

            <!-- Prompt -->
            <div class="detail-section">
                <div class="detail-section-title"><span class="detail-icon" style="background:var(--accent-glow);color:var(--accent)">✏️</span> Prompt</div>
                <div class="detail-text-block">${entry.prompt || '—'}</div>
            </div>

            <!-- Expected Output -->
            ${entry.expected_output ? `
            <div class="detail-section">
                <div class="detail-section-title"><span class="detail-icon" style="background:var(--green-bg);color:var(--green)">✓</span> Expected Output</div>
                <div class="detail-text-block">${entry.expected_output}</div>
            </div>` : ''}

            <!-- LLM Output -->
            <div class="detail-section">
                <div class="detail-section-title"><span class="detail-icon" style="background:var(--blue-bg);color:var(--blue)">🤖</span> LLM Response</div>
                <div class="detail-text-block">${entry.llm_output || '—'}</div>
            </div>

            <!-- Feedback -->
            ${entry.feedback ? `
            <div class="detail-section">
                <div class="detail-section-title"><span class="detail-icon" style="background:var(--yellow-bg);color:var(--yellow)">💬</span> Feedback</div>
                <div class="detail-text-block" style="font-style:italic">${entry.feedback}</div>
            </div>` : ''}

            <div class="detail-actions" style="margin-top:24px;padding-top:16px;border-top:1px solid var(--border);display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
              <button type="button" class="btn green" data-entry-pdf="${entry.id}">Download PDF (this run only)</button>
              <span style="font-size:11px;color:var(--text-muted)">Full history PDF uses the History page &quot;Download PDF&quot; button.</span>
            </div>
        `;
        const pdfBtn = body.querySelector('[data-entry-pdf]');
        if (pdfBtn) {
            pdfBtn.addEventListener('click', () => downloadReport(entry.id));
        }
    } catch (e) {
        body.innerHTML = `<div class="empty-state" style="padding:40px;color:var(--red)">Failed to load details: ${e.message}</div>`;
    }
}

function closeHistoryDetail() {
    document.getElementById('history-detail-modal').classList.remove('active');
}

function openPromptDiffModal(original, improved, originalScore, improvedScore, subtitle) {
    if (typeof PromptDiff === 'undefined') {
        toast('Diff viewer failed to load (prompt-diff.js)', 'error');
        return;
    }
    document.getElementById('prompt-diff-modal-body').innerHTML = PromptDiff.promptDiffPanelHtml(
        original, improved, originalScore, improvedScore, subtitle || ''
    );
    document.getElementById('prompt-diff-modal').classList.add('active');
}

function closePromptDiffModal() {
    document.getElementById('prompt-diff-modal').classList.remove('active');
}

function openOptimizedRowDiff(rowIndex) {
    const rows = window._optimizedDataset;
    if (!rows || typeof PromptDiff === 'undefined') return;
    const r = rows.find(x => x.index === rowIndex);
    if (!r) {
        toast('Row not found', 'error');
        return;
    }
    openPromptDiffModal(
        r.original_prompt,
        r.improved_prompt,
        r.original_score,
        r.improved_score,
        'Dataset row #' + rowIndex
    );
}

function openLineageVersionDiff(lineageId, currIdx) {
    if (typeof PromptDiff === 'undefined') return;
    const lin = window._lineageById && window._lineageById[lineageId];
    if (!lin || currIdx < 1) return;
    const prevIt = lin.iterations[currIdx - 1];
    const curIt = lin.iterations[currIdx];
    if (!prevIt || !curIt) return;
    const prevPrompt = prevIt.prompt || '';
    const curPrompt = curIt.prompt || '';
    const os = prevIt.score != null ? Number(prevIt.score) : 0;
    const ns = curIt.score != null ? Number(curIt.score) : 0;
    openPromptDiffModal(
        prevPrompt,
        curPrompt,
        os,
        ns,
        'Lineage · v' + currIdx + ' → v' + (currIdx + 1)
    );
}

// Close modal on Escape key or clicking overlay background
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closePromptDiffModal();
        closeHistoryDetail();
    }
});
document.getElementById('history-detail-modal')?.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) closeHistoryDetail();
});
document.getElementById('prompt-diff-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'prompt-diff-modal') closePromptDiffModal();
});


// ═══════════════════════════════════
// REPORT DOWNLOAD
// ═══════════════════════════════════

async function downloadReport(entryId) {
    toast('Generating PDF report...', 'info');
    try {
        const wantSingle = entryId != null && entryId !== '';
        let url = '/api/report/download';
        if (wantSingle) {
            url = '/api/report/download?entry_id=' + encodeURIComponent(entryId);
        }
        const res = await fetch(url);
        const ct = (res.headers.get('content-type') || '').toLowerCase();
        if (!res.ok) {
            let msg = await res.text();
            try {
                const j = JSON.parse(msg);
                msg = j.detail || msg;
            } catch (_) { /* plain text */ }
            throw new Error(msg || res.statusText);
        }
        if (!ct.includes('pdf')) {
            const msg = await res.text();
            throw new Error(msg || 'Server did not return a PDF');
        }
        const blob = await res.blob();
        const pdfBlob = blob.type === 'application/pdf' ? blob : new Blob([blob], { type: 'application/pdf' });
        const objUrl = URL.createObjectURL(pdfBlob);
        const a = document.createElement('a');
        a.href = objUrl;
        const day = new Date().toISOString().slice(0, 10);
        a.download = wantSingle ? `eval_run_${entryId}_${day}.pdf` : `eval_report_${day}.pdf`;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(objUrl);
        toast('Report downloaded!', 'success');
    } catch (e) {
        toast('Report generation failed: ' + e.message, 'error');
    }
}

function _downloadBlobAsFile(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

async function downloadTeamBundleFromHistory() {
    toast('Building team bundle (ZIP)...', 'info');
    try {
        const res = await fetch('/api/export/bundle?limit=100');
        if (!res.ok) {
            let msg = await res.text();
            try {
                const j = JSON.parse(msg);
                msg = j.detail || msg;
            } catch (_) { /* plain */ }
            throw new Error(msg || res.statusText);
        }
        const blob = await res.blob();
        const zipBlob = blob.type === 'application/zip' ? blob : new Blob([blob], { type: 'application/zip' });
        const cd = res.headers.get('Content-Disposition') || '';
        let fname = `eval_team_bundle_history_${new Date().toISOString().slice(0, 10)}.zip`;
        const m = cd.match(/filename="([^"]+)"/i) || cd.match(/filename=([^;\s]+)/i);
        if (m) fname = m[1].trim().replace(/^"|"$/g, '');
        _downloadBlobAsFile(zipBlob, fname);
        toast('Team bundle downloaded (JSON, CSV, chart, PDF inside ZIP).', 'success');
    } catch (e) {
        toast('Bundle export failed: ' + e.message, 'error');
    }
}

async function downloadTeamBundleFromDataset() {
    if (!window._datasetBatchResults || window._datasetBatchResults.length === 0) {
        return toast('Run batch evaluation first', 'error');
    }
    if (!datasetPrompts || datasetPrompts.length === 0) {
        return toast('Reload your CSV if prompts are missing', 'error');
    }
    toast('Building team bundle (ZIP)...', 'info');
    try {
        const items = window._datasetBatchResults.map(r => {
            const full = datasetPrompts[r.index - 1];
            return {
                index: r.index,
                category: (full && full.category) || r.category,
                prompt: (full && full.prompt) ? full.prompt : r.prompt,
                expected_output: (full && full.expected_output) ? full.expected_output : r.expected,
                llm_output: r.llm_output,
                score: r.score,
                similarity: r.similarity,
                judge_score: r.judge_score,
                feedback: r.feedback,
            };
        });
        const res = await fetch('/api/export/bundle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                items,
                model_name: selectedModel,
                title: 'dataset_evaluation',
            }),
        });
        if (!res.ok) {
            let msg = await res.text();
            try {
                const j = JSON.parse(msg);
                msg = j.detail || msg;
            } catch (_) { /* plain */ }
            throw new Error(msg || res.statusText);
        }
        const blob = await res.blob();
        const zipBlob = blob.type === 'application/zip' ? blob : new Blob([blob], { type: 'application/zip' });
        const cd = res.headers.get('Content-Disposition') || '';
        let fname = `eval_team_bundle_dataset_${new Date().toISOString().slice(0, 10)}.zip`;
        const m = cd.match(/filename="([^"]+)"/i) || cd.match(/filename=([^;\s]+)/i);
        if (m) fname = m[1].trim().replace(/^"|"$/g, '');
        _downloadBlobAsFile(zipBlob, fname);
        toast('Team bundle downloaded (JSON, CSV, chart, PDF inside ZIP).', 'success');
    } catch (e) {
        toast('Bundle export failed: ' + e.message, 'error');
    }
}

// ═══════════════════════════════════
// ITERATIONS / LINEAGE
// ═══════════════════════════════════

async function fetchIterations(showOverlay = true) {
    if (showOverlay) showLoading('Loading Lineage History...');
    try {
        const res = await fetch('/api/iterations');
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        
        document.getElementById('iterations-count').textContent = data.count + ' lineages tracked';
        
        const badge = document.getElementById('nav-badge-iterations');
        if (data.count > 0) { badge.textContent = data.count; badge.style.display = ''; }
        else { badge.style.display = 'none'; }
        
        const list = document.getElementById('iterations-list');
        list.innerHTML = '';
        
        if (data.count === 0) {
            list.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-muted)">No lineages generated yet.<br>Run batch optimization or click Improve failed prompts to start tracking.</div>`;
            return;
        }

        window._lineageById = {};

        data.iterations.forEach(lin => {
            window._lineageById[lin.lineage_id] = lin;
            const card = document.createElement('div');
            card.className = 'card';
            
            // Header
            const h = document.createElement('div');
            h.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:15px">
                    <div>
                        <div style="font-size:16px; font-weight:700; color:var(--text-primary); margin-bottom:4px;">
                            Lineage — "${lin.original_prompt.substring(0,60)}${lin.original_prompt.length > 60 ? '...' : ''}"
                        </div>
                        <div style="font-size:11px; color:var(--text-muted)">
                            ${lin.iterations.length} versions · Model: ${lin.model_name}
                        </div>
                    </div>
                </div>
                <div style="height:220px; position:relative; margin-bottom:20px; border-bottom:1px solid var(--border); padding-bottom:15px;">
                    <canvas id="chart-${lin.lineage_id}"></canvas>
                </div>
                <table class="data-table">
                  <thead><tr><th>Version</th><th style="min-width:280px">Prompt</th><th>Total Score</th><th>Similarity</th><th>Diff</th></tr></thead>
                  <tbody id="tbody-${lin.lineage_id}"></tbody>
                </table>
            `;
            card.appendChild(h);
            list.appendChild(card);
            
            // Table Elements
            const tbody = document.getElementById(`tbody-${lin.lineage_id}`);
            lin.iterations.forEach((it, idx) => {
                const tr = document.createElement('tr');
                let tag = idx === 0 ? 'v1 (baseline)' : 'v' + (idx+1) + (idx === lin.iterations.length - 1 && it.score > lin.iterations[0].score ? ' winner' : '');
                let sc = it.score;
                let isWinner = (idx === lin.iterations.length - 1 && sc > lin.iterations[0].score);
                
                const diffCell = (idx === 0 || typeof PromptDiff === 'undefined')
                    ? '<span style="color:var(--text-muted);font-size:11px">—</span>'
                    : `<button type="button" class="btn-view" onclick='openLineageVersionDiff(${JSON.stringify(lin.lineage_id)}, ${idx})'>vs prev</button>`;

                tr.innerHTML = `
                    <td><span class="pill ${isWinner ? 'pill-g' : 'pill-b'}">${tag}</span></td>
                    <td style="font-size:11px; max-width:300px; line-height:1.4">${idx === 0 ? lin.original_prompt : it.prompt}</td>
                    <td style="font-weight:600; color:${isWinner ? 'var(--green)' : 'var(--text)'}">${sc.toFixed(1)}</td>
                    <td>${it.semantic_similarity ? (it.semantic_similarity*100).toFixed(0)+'%' : '—'}</td>
                    <td>${diffCell}</td>
                `;
                tbody.appendChild(tr);
            });
            
            // Render Chart.js
            const ctx = document.getElementById(`chart-${lin.lineage_id}`).getContext('2d');
            const labels = lin.iterations.map((_, i) => 'v' + (i+1));
            const scores = lin.iterations.map(i => i.score);
            const sims = lin.iterations.map(i => (i.semantic_similarity || 0) * 100);
            
            Chart.defaults.color = '#9ca3af';
            Chart.defaults.font.family = 'Inter, sans-serif';
            
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        { label: 'Total Score', data: scores, borderColor: '#6366f1', backgroundColor: '#6366f120', tension: 0.2, fill: true, borderWidth: 2, pointRadius: 4, pointBackgroundColor: '#6366f1' },
                        { label: 'Similarity', data: sims, borderColor: '#10b981', backgroundColor: 'transparent', tension: 0.2, borderDash: [5,5], borderWidth: 2, pointRadius: 3 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { 
                        legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true } },
                        tooltip: { backgroundColor: 'rgba(0,0,0,0.8)', padding: 10, borderRadius: 8 }
                    },
                    scales: {
                        y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.05)' } },
                        x: { grid: { display: false } }
                    }
                }
            });
        });
        
    } catch (e) {
        toast('Failed to load iterations: ' + e.message, 'error');
        console.error(e);
    } finally {
        if (showOverlay) hideLoading();
    }
}
