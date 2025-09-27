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

    analyzeBtn.addEventListener('click', () => {
        // Get the current active tab
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const currentTab = tabs[0];
            if (!currentTab || !currentTab.url) {
                displayError("Could not get the URL of the current tab.");
                return;
            }
            
            // Show loader and hide previous results/errors
            loader.classList.remove('hidden');
            resultsDiv.classList.add('hidden');
            errorDiv.classList.add('hidden');
            analyzeBtn.disabled = true;

            // Call the FastAPI backend
            callBackend(currentTab.url);
        });
    });

    function callBackend(url) {
        const FASTAPI_ENDPOINT = 'http://127.0.0.1:8001/analyze/';

        fetch(FASTAPI_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url }),
        })
        .then(response => {
            if (!response.ok) {
                // Try to get a detailed error message from the backend
                return response.json().then(err => {
                    throw new Error(err.detail || `Server responded with status: ${response.status}`);
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

        // Product Name
        productNameEl.textContent = data.product_name || 'Product Name Not Found';

        // Overall Score (requires calculation, let's approximate for now)
        const rating = parseFloat((data.rating || "0").split(' ')[0]);
        const positive_percent = data.public_opinion.positive_percent || 0;
        const score = ((rating / 5 * 10) * 0.6) + ((positive_percent / 10) * 0.4);
        scoreEl.textContent = `${score.toFixed(1)} / 10`;

        // Sentiment Bar
        positiveBarEl.style.width = `${positive_percent}%`;
        sentimentTextEl.textContent = `${positive_percent}% Positive Sentiment`;

        // Summary
        summaryEl.textContent = data.review_summary_generator || 'No summary available.';

        // Pros
        const pros = data.pros_cons_panel.pros || [];
        let prosHtml = '<h4>Pros</h4><ul>';
        if (pros.length > 0) {
            pros.forEach(pro => { prosHtml += `<li>${pro}</li>`; });
        } else {
            prosHtml += '<li>N/A</li>';
        }
        prosHtml += '</ul>';
        prosListEl.innerHTML = prosHtml;

        // Cons
        const cons = data.pros_cons_panel.cons || [];
        let consHtml = '<h4>Cons</h4><ul>';
        if (cons.length > 0) {
            cons.forEach(con => { consHtml += `<li>${con}</li>`; });
        } else {
            consHtml += '<li>N/A</li>';
        }
        consHtml += '</ul>';
        consListEl.innerHTML = consHtml;

        resultsDiv.classList.remove('hidden');
    }
});
