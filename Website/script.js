document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const resultsContainer = document.getElementById('results');
    const statsText = document.getElementById('stats-text');
    
    // Filters
    const modeRadios = document.querySelectorAll('input[name="mode"]');
    const bookCheckboxes = document.querySelectorAll('#books-filter input[type="checkbox"]');

    let debounceTimer;

    // Event Listeners
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => performSearch(), 400);
    });

    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    modeRadios.forEach(radio => radio.addEventListener('change', () => performSearch()));
    bookCheckboxes.forEach(cb => cb.addEventListener('change', () => performSearch()));

    async function performSearch() {
        const query = searchInput.value.trim();
        
        if (!query) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <h3>Explore Ancient Wisdom</h3>
                    <p>Enter a query above to search through classical Ayurvedic texts.</p>
                </div>`;
            statsText.textContent = '';
            return;
        }

        const mode = document.querySelector('input[name="mode"]:checked').value;
        const books = Array.from(bookCheckboxes).filter(cb => cb.checked).map(cb => cb.value);

        resultsContainer.innerHTML = '<div class="loading-spinner">Searching through ancient texts...</div>';

        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query, mode, books, limit: 30 })
            });

            if (!response.ok) throw new Error("Search failed");
            
            const data = await response.json();
            renderResults(data.hits, data.processingTimeMs, mode);
            
        } catch (error) {
            resultsContainer.innerHTML = `
                <div class="empty-state" style="color: #ef4444;">
                    <h3>An error occurred</h3>
                    <p>Could not reach the search backend. Make sure the API is running.</p>
                </div>`;
            console.error(error);
        }
    }

    function renderResults(hits, timeMs, mode) {
        if (hits.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <h3>No verses found</h3>
                    <p>Try adjusting your search query or removing filters.</p>
                </div>`;
            statsText.textContent = '';
            return;
        }

        statsText.textContent = `Found ${hits.length} results in ${timeMs}ms (Mode: ${mode})`;

        let html = '<div class="results-wrapper">';
        
        hits.forEach((hit, index) => {
            const formatted = hit._formatted || hit;
            
            // Clean up missing fields
            const topic = formatted.topic_heading || '';
            const sanskrit = formatted.sanskrit_text || '';
            const translit = formatted.transliteration || '';
            const commentary = formatted.commentary || '';
            
            // Meta info
            const source = hit.source_file || 'Unknown Book';
            const chapter = hit.chapter_title ? ` · Ch. ${hit.chapter_number} "${hit.chapter_title}"` : '';
            const verse = hit.verse_id ? ` · Verse ${hit.verse_id}` : '';
            const sthana = hit.sthana ? ` (${hit.sthana})` : '';

            // Tags
            let tagsHtml = '';
            const tags = new Set();
            if (hit.primary_category) tags.add(hit.primary_category);
            if (hit.categories_found) hit.categories_found.forEach(t => tags.add(t));
            
            tags.forEach(t => {
                if (t) tagsHtml += `<span class="tag">${t}</span>`;
            });

            html += `
                <div class="verse-card" style="animation-delay: ${index * 0.05}s">
                    <div class="verse-meta">${source}${sthana}${chapter}${verse}</div>
                    ${topic ? `<div class="verse-topic">${topic}</div>` : ''}
                    ${sanskrit ? `<div class="verse-sanskrit">${sanskrit}</div>` : ''}
                    ${translit ? `<div class="verse-translit">${translit}</div>` : ''}
                    ${commentary ? `<div class="verse-commentary">${commentary}</div>` : ''}
                    ${tagsHtml ? `<div class="verse-tags">${tagsHtml}</div>` : ''}
                </div>
            `;
        });

        html += '</div>';
        resultsContainer.innerHTML = html;
    }
});
