// ─────────────────────────────────────────────────────────────────────────────
// Ayurveda Explorer – script.js
// Features: Search, Persistent Memory (localStorage), Results Limit slider
// ─────────────────────────────────────────────────────────────────────────────

const STORAGE_KEY = 'ayurveda_explorer_state';
const HISTORY_KEY = 'ayurveda_explorer_history';
const MAX_HISTORY  = 15;

document.addEventListener('DOMContentLoaded', () => {
    const searchInput      = document.getElementById('search-input');
    const resultsContainer = document.getElementById('results');
    const statsText        = document.getElementById('stats-text');
    const limitSlider      = document.getElementById('results-limit');
    const limitDisplay     = document.getElementById('limit-display');
    const historyList      = document.getElementById('history-list');
    const clearMemoryBtn   = document.getElementById('clear-memory-btn');
    const clearSearchBtn   = document.getElementById('clear-search-btn');
    const modeRadios       = document.querySelectorAll('input[name="mode"]');
    const bookCheckboxes   = document.querySelectorAll('#books-filter input[type="checkbox"]');

    let debounceTimer;

    // ─── Persistent State ────────────────────────────────────────────────────

    function saveState() {
        const state = {
            query  : searchInput.value,
            mode   : document.querySelector('input[name="mode"]:checked')?.value || 'Hybrid',
            books  : Array.from(bookCheckboxes).filter(cb => cb.checked).map(cb => cb.value),
            limit  : limitSlider.value
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }

    function loadState() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return;
            const state = JSON.parse(raw);

            if (state.query)  searchInput.value = state.query;
            if (state.limit)  { limitSlider.value = state.limit; limitDisplay.textContent = state.limit; }
            if (state.mode) {
                modeRadios.forEach(r => { r.checked = (r.value === state.mode); });
            }
            if (state.books && state.books.length) {
                bookCheckboxes.forEach(cb => { cb.checked = state.books.includes(cb.value); });
            }
        } catch (e) { /* ignore corrupt storage */ }
    }

    // ─── Search History ───────────────────────────────────────────────────────

    function getHistory() {
        try { return JSON.parse(localStorage.getItem(HISTORY_KEY)) || []; }
        catch { return []; }
    }

    function addToHistory(query) {
        if (!query) return;
        let history = getHistory().filter(q => q.toLowerCase() !== query.toLowerCase());
        history.unshift(query);
        history = history.slice(0, MAX_HISTORY);
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
        renderHistory();
    }

    function renderHistory() {
        const history = getHistory();
        if (!history.length) {
            historyList.innerHTML = '<p class="history-empty">No recent searches.</p>';
            return;
        }
        historyList.innerHTML = history.map(q =>
            `<button class="history-item" data-query="${q.replace(/"/g, '&quot;')}">${q}</button>`
        ).join('');

        historyList.querySelectorAll('.history-item').forEach(btn => {
            btn.addEventListener('click', () => {
                searchInput.value = btn.dataset.query;
                saveState();
                performSearch();
            });
        });
    }

    function clearMemory() {
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem(HISTORY_KEY);
        // Reset UI
        searchInput.value = '';
        limitSlider.value = 20;
        limitDisplay.textContent = '20';
        modeRadios.forEach((r, i) => r.checked = (i === 0));
        bookCheckboxes.forEach(cb => cb.checked = false);
        resultsContainer.innerHTML = `<div class="empty-state"><h3>Explore Ancient Wisdom</h3><p>Enter a query above to search through classical Ayurvedic texts.</p></div>`;
        statsText.textContent = '';
        renderHistory();
    }

    // ─── Event Listeners ─────────────────────────────────────────────────────

    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => { saveState(); performSearch(); }, 400);
    });

    searchInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') { saveState(); performSearch(); }
    });

    clearSearchBtn.addEventListener('click', () => {
        searchInput.value = '';
        saveState();
        resultsContainer.innerHTML = `<div class="empty-state"><h3>Explore Ancient Wisdom</h3><p>Enter a query above to search through classical Ayurvedic texts.</p></div>`;
        statsText.textContent = '';
    });

    limitSlider.addEventListener('input', () => {
        limitDisplay.textContent = limitSlider.value;
        saveState();
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => performSearch(), 300);
    });

    modeRadios.forEach(radio => radio.addEventListener('change', () => { saveState(); performSearch(); }));
    bookCheckboxes.forEach(cb => cb.addEventListener('change', () => { saveState(); performSearch(); }));
    clearMemoryBtn.addEventListener('click', clearMemory);

    // ─── Search ───────────────────────────────────────────────────────────────

    async function performSearch() {
        const query = searchInput.value.trim();

        if (!query) {
            resultsContainer.innerHTML = `<div class="empty-state"><h3>Explore Ancient Wisdom</h3><p>Enter a query above to search through classical Ayurvedic texts.</p></div>`;
            statsText.textContent = '';
            return;
        }

        const mode  = document.querySelector('input[name="mode"]:checked')?.value || 'Hybrid';
        const books = Array.from(bookCheckboxes).filter(cb => cb.checked).map(cb => cb.value);
        const limit = parseInt(limitSlider.value, 10);

        resultsContainer.innerHTML = '<div class="loading-spinner">Searching through ancient texts...</div>';

        try {
            const response = await fetch('/api/search', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body   : JSON.stringify({ query, mode, books, limit })
            });

            if (!response.ok) throw new Error('Search failed');

            const data = await response.json();
            addToHistory(query);
            renderResults(data.hits, data.processingTimeMs, mode);

        } catch (error) {
            resultsContainer.innerHTML = `
                <div class="empty-state" style="color:#ef4444;">
                    <h3>An error occurred</h3>
                    <p>Could not reach the search backend. Make sure the API is running.</p>
                </div>`;
            console.error(error);
        }
    }

    // ─── Render ───────────────────────────────────────────────────────────────

    function renderResults(hits, timeMs, mode) {
        if (!hits.length) {
            resultsContainer.innerHTML = `<div class="empty-state"><h3>No verses found</h3><p>Try adjusting your search query or removing filters.</p></div>`;
            statsText.textContent = '';
            return;
        }

        statsText.textContent = `Found ${hits.length} results in ${timeMs}ms (Mode: ${mode})`;

        let html = '<div class="results-wrapper">';

        hits.forEach((hit, index) => {
            const formatted   = hit._formatted || hit;
            const topic       = formatted.topic_heading    || '';
            const sanskrit    = formatted.sanskrit_text    || '';
            const translit    = formatted.transliteration  || '';
            const commentary  = formatted.commentary       || '';
            const source      = hit.source_file            || 'Unknown Book';
            const chapter     = hit.chapter_title ? ` · Ch. ${hit.chapter_number} "${hit.chapter_title}"` : '';
            const verse       = hit.verse_id  ? ` · Verse ${hit.verse_id}` : '';
            const sthana      = hit.sthana    ? ` (${hit.sthana})` : '';

            let tagsHtml = '';
            const tags = new Set();
            if (hit.primary_category)  tags.add(hit.primary_category);
            if (hit.categories_found)  hit.categories_found.forEach(t => tags.add(t));
            tags.forEach(t => { if (t) tagsHtml += `<span class="tag">${t}</span>`; });

            html += `
                <div class="verse-card" style="animation-delay:${index * 0.05}s">
                    <div class="verse-meta">${source}${sthana}${chapter}${verse}</div>
                    ${topic      ? `<div class="verse-topic">${topic}</div>`           : ''}
                    ${sanskrit   ? `<div class="verse-sanskrit">${sanskrit}</div>`     : ''}
                    ${translit   ? `<div class="verse-translit">${translit}</div>`     : ''}
                    ${commentary ? `<div class="verse-commentary">${commentary}</div>` : ''}
                    ${tagsHtml   ? `<div class="verse-tags">${tagsHtml}</div>`         : ''}
                </div>`;
        });

        html += '</div>';
        resultsContainer.innerHTML = html;
    }

    // ─── Init ─────────────────────────────────────────────────────────────────

    loadState();
    renderHistory();

    // Re-run search if there is a saved query
    if (searchInput.value.trim()) {
        performSearch();
    }
});
