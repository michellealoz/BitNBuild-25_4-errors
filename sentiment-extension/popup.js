document.addEventListener('DOMContentLoaded', () => {
    // --- Views and Buttons ---
    const mainView = document.getElementById('main-view');
    const bookmarksView = document.getElementById('bookmarks-view');
    const analyzeBtn = document.getElementById('analyze-btn');
    const viewBookmarksBtn = document.getElementById('view-bookmarks-btn');
    const backToMainBtn = document.getElementById('back-to-main-btn');
    const bookmarkBtn = document.getElementById('bookmark-btn'); // **FIX:** Added selector for the bookmark button
    const bookmarksListContainer = document.getElementById('bookmarks-list-container');
    
    // --- UI Elements ---
    const loader = document.getElementById('loader');
    const errorDiv = document.getElementById('error');
    const resultsDiv = document.getElementById('results');
    const productNameEl = document.getElementById('product-name');
    const scoreEl = document.getElementById('overall-score');
    const positiveBarEl = document.getElementById('positive-bar');
    const sentimentTextEl = document.getElementById('sentiment-text');
    const summaryEl = document.getElementById('summary-text');
    const prosListEl = document.getElementById('pros-list');
    const consListEl = document.getElementById('cons-list');

    const FASTAPI_ENDPOINT = 'http://127.0.0.1:8001/analyze/';
    let currentProductData = null; // Holds the data of the currently analyzed product

    // --- Event Listeners for View Switching ---
    viewBookmarksBtn.addEventListener('click', () => {
        mainView.classList.add('hidden');
        bookmarksView.classList.remove('hidden');
        loadAndRenderBookmarks();
    });

    backToMainBtn.addEventListener('click', () => {
        bookmarksView.classList.add('hidden');
        mainView.classList.remove('hidden');
    });

    // --- Main Analyze Logic ---
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
        .then(res => res.ok ? res.json() : res.json().then(err => Promise.reject(err)))
        .then(data => {
            displayResults(data);
        })
        .catch(error => {
            displayError(error.detail || `Connection failed: ${error.message}. Is the local server running?`);
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

        currentProductData = data; // Save data for bookmarking
        currentProductData.url = data.product_url || ''; // Ensure URL is saved

        productNameEl.textContent = data.product_name || 'Product Name Not Found';
        const score = data.overall_score || calculateScore(data);
        scoreEl.textContent = `${score} / 10`;

        const positivePercent = data.public_opinion.positive_percent || 0;
        positiveBarEl.style.width = `${positivePercent}%`;
        sentimentTextEl.textContent = `${positivePercent}% Positive`;
        summaryEl.textContent = data.review_summary_generator || 'No summary available.';
        populateVerdictList(prosListEl, 'Pros', data.pros_cons_panel.pros, 'icon-green');
        populateVerdictList(consListEl, 'Cons', data.pros_cons_panel.cons, 'icon-red');

        resultsDiv.classList.remove('hidden');
    }
    
    function calculateScore(data) {
        const rating = parseFloat((data.rating || "0").split(' ')[0]);
        const positive_percent = data.public_opinion.positive_percent || 0;
        const score = ((rating / 5 * 10) * 0.6) + ((positive_percent / 10) * 0.4);
        return score.toFixed(1);
    }
    
    function populateVerdictList(element, title, items, iconClass) {
        element.innerHTML = '';
        const titleIcon = title === 'Pros' ? 'fa-thumbs-up' : 'fa-thumbs-down';
        const titleEl = document.createElement('h3');
        titleEl.innerHTML = `<i class="fas ${titleIcon} ${iconClass}"></i>${title}`;
        element.appendChild(titleEl);
        const ul = document.createElement('ul');
        ul.className = 'verdict-list';
        if (!items || items.length === 0) {
            ul.innerHTML = '<li class="empty-list">N/A</li>';
        } else {
            items.slice(0, 4).forEach(item => {
                const li = document.createElement('li');
                li.innerHTML = `<span class="keyword">${item.keyword}</span>`;
                if (item.examples && item.examples.length > 0) {
                    const example = item.examples[0].length > 50 ? item.examples[0].substring(0, 50) + '...' : item.examples[0];
                    li.innerHTML += `<blockquote class="example-quote">"${example}"</blockquote>`;
                }
                ul.appendChild(li);
            });
        }
        element.appendChild(ul);
    }

    // --- **NEW:** Bookmark Functionality ---
    bookmarkBtn.addEventListener('click', () => {
        if (!currentProductData) return;
        
        getBookmarks(bookmarks => {
            // Avoid duplicates
            if (bookmarks.some(b => b.product_name === currentProductData.product_name)) {
                alert("This product is already bookmarked!");
                return;
            }
            
            const newBookmarks = [...bookmarks, currentProductData];
            saveBookmarks(newBookmarks, () => {
                alert("Product bookmarked!");
            });
        });
    });

    function getBookmarks(callback) {
        // Use chrome.storage.local for extensions
        chrome.storage.local.get(['bookmarks'], (result) => {
            callback(result.bookmarks || []);
        });
    }

    function saveBookmarks(bookmarks, callback) {
        chrome.storage.local.set({ bookmarks }, callback);
    }

    function loadAndRenderBookmarks() {
        getBookmarks(bookmarks => {
            bookmarksListContainer.innerHTML = ''; // Clear current list
            if (bookmarks.length === 0) {
                bookmarksListContainer.innerHTML = '<p class="no-bookmarks">You have no saved products.</p>';
                return;
            }

            bookmarks.forEach((data, index) => {
                const score = data.overall_score || calculateScore(data);
                const item = document.createElement('div');
                item.className = 'bookmark-item';
                item.innerHTML = `
                    <div class="bookmark-info">
                        <p class="bookmark-title">${data.product_name}</p>
                        <p class="bookmark-score">Score: ${score} / 10</p>
                    </div>
                    <button class="delete-bookmark-btn" data-index="${index}" title="Remove Bookmark"><i class="fas fa-trash-alt"></i></button>
                `;
                bookmarksListContainer.appendChild(item);
            });
        });
    }

    // Event delegation for deleting bookmarks from the list
    bookmarksListContainer.addEventListener('click', (e) => {
        const deleteBtn = e.target.closest('.delete-bookmark-btn');
        if (deleteBtn) {
            const indexToDelete = parseInt(deleteBtn.dataset.index, 10);
            if (confirm("Are you sure you want to remove this bookmark?")) {
                getBookmarks(bookmarks => {
                    const updatedBookmarks = bookmarks.filter((_, index) => index !== indexToDelete);
                    saveBookmarks(updatedBookmarks, () => {
                        loadAndRenderBookmarks(); // Re-render the list after deletion
                    });
                });
            }
        }
    });
});