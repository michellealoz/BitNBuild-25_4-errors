
# 🛒 Review Radar

**Review Radar** is a smart web tool and browser extension that helps online shoppers make faster, smarter decisions by summarizing and comparing customer reviews from e-commerce product pages. Instead of scrolling through thousands of reviews, Review Radar gives you a clean, AI-powered summary — and even recommends the best product when you're stuck deciding between options.

---

## 🚀 Features

* ✅ **URL-Based Review Scraper**
  Paste a product page URL from major e-commerce websites, and Review Radar automatically scrapes all available customer reviews.

* 🤖 **Pre-trained Sentiment Analysis**
  Uses a robust NLP model to classify each review as **positive**, **neutral**, or **negative**.

* 🔍 **Keyword & Topic Extraction**
  Identifies the most commonly mentioned features or issues in reviews (e.g., "battery," "delivery," "camera quality").

* 📊 **Summary Dashboard**
  Displays a clean visual summary of the review analysis with:

  * Sentiment breakdown 
  * Top positive and negative keywords
  * Overall product impression

* ⚖️ **Product Comparison Tool**
  Compare multiple products side-by-side based on:

  * Sentiment trends
  * Feature mentions
  * Overall user satisfaction

* 🏆 **Best Product Recommendation**
  Automatically highlights the best product among those compared, based on aggregated review sentiment and feature relevance.

* 🕘 **History & Previous Analyses**
  Stores all past products and comparisons so users can revisit them later without redoing the process.

* 🧩 **Browser Extension Integration** 
  Get review summaries while browsing product pages — no copy-pasting needed.

---

## 📌 Use Cases

* **Online shoppers** comparing electronics, fashion, appliances, etc.
* **Researchers or marketers** analyzing customer sentiment.
* **Anyone** overwhelmed by too many reviews on Amazon, Flipkart, etc.

---

## 🛠️ Tech Stack

* **Frontend:** HTML , CSS , JS
* **Backend:** Django
* **Web Scraping:**  BeautifulSoup (Python used), FASTAPI
* **NLP Models:** Hugging Face Transformers ( BERT for sentiment analysis) , FASTAPI
* **Data Processing:** Python / Pandas / Scikit-learn
* **Extension Tool:** Javascript

---


## 📦 How to Run Locally

```bash
# Clone the repository
git clone https://github.com/yourusername/review-radar.git

# Navigate into the project directory
cd review-radar
cd BitNBuild25_4-errors
cd Core
#  Create and activate a virtual environment
python -m venv env
source env/bin/activate       # On Windows use: env\Scripts\activate

# Install project dependencies
pip install -r requirements.txt

# Apply database migrations
python manage.py migrate

# Run the development server
python manage.py runserver

```


