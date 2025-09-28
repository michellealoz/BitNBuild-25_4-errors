document.addEventListener('DOMContentLoaded', () => {
    const analyzeBtn = document.getElementById('analyze-btn');
    const loader = document.getElementById('loader');
    const errorDiv = document.getElementById('error');
    const resultsDiv = document.getElementById('results');

    // --- Result Elements ---
    const productNameEl = document.getElementById('product-name');
    const scoreEl = document.getElementById('overall-score');
    const positiveBarEl = document.getElementById('positive-bar');
    const sentimentTextEl = document.getElementById('sentiment-text');
    const summaryEl = document.getElementById('summary-text');
    const prosListEl = document.getElementById('pros-list');
    const consListEl = document.getElementById('cons-list');

    const FASTAPI_ENDPOINT = 'http://127.0.0.1:8001/analyze/';

    analyzeBtn.addEventListener('click', () => {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const currentTab = tabs[0];
            if (!currentTab || !currentTab.url) {
                displayError("Could not get the URL of the current tab.");
                return;
            }
            
            loader.classList.remove('hidden');
            resultsDiv.classList.add('hidden');
            errorDiv.classList.add('hidden');
            analyzeBtn.disabled = true;

            callBackend(currentTab.url);
        });
    });

    function callBackend(url) {
        fetch(FASTAPI_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url }),
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || `Server error: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            displayResults(data);
        })
        .catch(error => {
            displayError(`Connection failed: ${error.message}. Is the local server running?`);
        })
        .finally(() => {
            loader.classList.add('hidden');
            analyzeBtn.disabled = false;
        });
    }

    function displayError(message) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    }

    function displayResults(data) {
        if (!data || !data.public_opinion) {
            displayError("Received invalid data from the server.");
            return;
        }

        productNameEl.textContent = data.product_name || 'Product Name Not Found';

        if (data.overall_score) {
            scoreEl.textContent = `${data.overall_score} / 10`;
        } else {
            const rating = parseFloat((data.rating || "0").split(' ')[0]);
            const positive_percent = data.public_opinion.positive_percent || 0;
            const score = ((rating / 5 * 10) * 0.6) + ((positive_percent / 10) * 0.4);
            scoreEl.textContent = `${score.toFixed(1)} / 10`;
        }

        const positivePercent = data.public_opinion.positive_percent || 0;
        positiveBarEl.style.width = `${positivePercent}%`;
        sentimentTextEl.textContent = `${positivePercent}% Positive`;
        summaryEl.textContent = data.review_summary_generator || 'No summary available.';

        populateVerdictList(prosListEl, 'Pros', data.pros_cons_panel.pros, 'icon-green');
        populateVerdictList(consListEl, 'Cons', data.pros_cons_panel.cons, 'icon-red');

        resultsDiv.classList.remove('hidden');
    }

    /**
     * Helper function to build and display the pros and cons lists correctly.
     */
    function populateVerdictList(element, title, items, iconClass) {
        element.innerHTML = ''; 

        const titleIcon = title === 'Pros' ? 'fa-thumbs-up' : 'fa-thumbs-down';
        const titleEl = document.createElement('h3');
        titleEl.innerHTML = `<i class="fas ${titleIcon} ${iconClass}"></i>${title}`;
        element.appendChild(titleEl);

        const ul = document.createElement('ul');
        ul.className = 'verdict-list';

        if (!items || items.length === 0) {
            const li = document.createElement('li');
            li.className = 'empty-list';
            li.textContent = 'N/A';
            ul.appendChild(li);
        } else {
            items.slice(0, 4).forEach(item => {
                const li = document.createElement('li');
                
                // **FIX 1:** Use "keyword" with a lowercase k
                const keywordEl = document.createElement('span');
                keywordEl.className = 'keyword';
                keywordEl.textContent = item.keyword; // Corrected from item.Keyword
                li.appendChild(keywordEl);

                // **FIX 2:** Use "examples" with a lowercase e
                if (item.examples && item.examples.length > 0) {
                    const example = item.examples[0].length > 50 ? item.examples[0].substring(0, 50) + '...' : item.examples[0];
                    const quoteEl = document.createElement('blockquote');
                    quoteEl.className = 'example-quote';
                    quoteEl.textContent = `"${example}"`;
                    li.appendChild(quoteEl);
                }
                ul.appendChild(li);
            });
        }
        element.appendChild(ul);
    }
});