import time
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd
from apify_client import ApifyClient
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from collections import Counter
import os
import logging
import re
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# --- 1. Initialize AI Models ---
print("Loading AI models...")
# NEW: Using a model specifically trained on Amazon reviews for star ratings
rating_classifier = pipeline("sentiment-analysis", model="LiYuan/amazon-review-sentiment-analysis", framework="pt")
# The summarizer remains the same
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", framework="pt")
print("Models loaded successfully.")


# --- 2. Pydantic Models ---
class URLInput(BaseModel):
    url: str

# --- 3. FastAPI App ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. Scraping and Analysis Functions ---

def enhanced_amazon_scraper(url: str) -> dict:
    """Enhanced Selenium scraper for Amazon product details."""
    print(f"--- Starting enhanced Amazon scraper for: {url} ---")
    options = FirefoxOptions()
    options.add_argument("--headless")
    options.set_preference("general.useragent.override", 
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0")
    
    driver = None
    product_details = { 'product_name': "Not found", 'price': "Not found", 'rating': "Not found" }
    
    try:
        driver = webdriver.Firefox(options=options)
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.ID, "productTitle")))
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Product Name
        name_element = soup.find('span', {'id': 'productTitle'})
        if name_element:
            product_details['product_name'] = name_element.get_text(strip=True)
        
        # Price
        price_element = soup.select_one('span.a-price-whole')
        if price_element:
            product_details['price'] = price_element.get_text(strip=True).replace(',', '')
        
        # Rating
        rating_element = soup.find('span', {'class': 'a-icon-alt'})
        if rating_element:
            product_details['rating'] = rating_element.get_text(strip=True)
            
        print(f"✅ Successfully scraped product: {product_details['product_name']}")
    except Exception as e:
        print(f"❌ Enhanced scraper failed: {e}")
    finally:
        if driver:
            driver.quit()
    return product_details

def enhanced_apify_review_scraper(url: str, api_token: str) -> list:
    """Enhanced Apify scraper for reviews."""
    print(f"--- Starting enhanced Apify scraper for: {url} ---")
    client = ApifyClient(api_token)
    run_input = { "productUrls": [{"url": url}], "maxReviews": 50, "sort": "helpful" }
    try:
        run = client.actor("R8WeJwLuzLZ6g4Bkk").call(run_input=run_input)
        reviews_data = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            review_text = f"{item.get('reviewTitle', '')}. {item.get('reviewDescription', '')}".strip()
            if review_text and review_text != ".":
                reviews_data.append({'text': review_text, 'rating': item.get('ratingScore', 0)})
        print(f"✅ Successfully scraped {len(reviews_data)} reviews using Apify.")
        return reviews_data
    except Exception as e:
        print(f"❌ Enhanced Apify scraper failed: {e}")
        return []

# --- Context-Aware Keyword Extraction ---

PRODUCT_KEYWORDS = {
    "Smartphone": ["camera", "battery", "performance", "display", "screen", "charging", "design", "build", "value"],
    "Laptop": ["performance", "battery", "display", "keyboard", "trackpad", "build", "portability", "speed", "screen"],
    "Headphones": ["sound quality", "noise cancellation", "battery", "comfort", "build", "connectivity", "mic"],
    "Generic": ["quality", "value", "performance", "design", "price", "easy to use"]
}

def categorize_product(product_name: str) -> str:
    """Simple product categorization based on title."""
    name = product_name.lower()
    if any(k in name for k in ["phone", "mobile", "smartphone"]): return "Smartphone"
    if any(k in name for k in ["laptop", "notebook", "macbook"]): return "Laptop"
    if any(k in name for k in ["headphone", "earbuds", "headset"]): return "Headphones"
    return "Generic"

def extract_focused_keywords(texts: list, product_name: str, num_keywords: int = 4) -> list:
    """
    Extracts keywords, prioritizes relevant ones, and pads with top statistical
    keywords to ensure the desired count is met.
    """
    if not texts: return []
    
    category = categorize_product(product_name)
    relevant_keywords = PRODUCT_KEYWORDS.get(category, PRODUCT_KEYWORDS["Generic"])
    
    try:
        vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2), max_df=0.9, min_df=1)
        tfidf_matrix = vectorizer.fit_transform(texts)
        sum_tfidf = tfidf_matrix.sum(axis=0)
        words = vectorizer.get_feature_names_out()
        df = pd.DataFrame({'term': words, 'score': list(sum_tfidf.tolist()[0])})
        
        if df.empty:
            return []

        # Get top 20 statistical keywords to work with
        top_statistical_keywords = df.sort_values(by='score', ascending=False).head(20)['term'].tolist()
        
        # 1. Prioritize keywords that match our context list
        focused_keywords = [kw for kw in top_statistical_keywords if any(focus in kw for focus in relevant_keywords)]
        
        # Create a combined list, ensuring no duplicates and preserving order
        combined_keywords = []
        for kw in focused_keywords:
            if kw not in combined_keywords:
                combined_keywords.append(kw)
        
        # 2. Pad the list with the top statistical keywords if we don't have enough
        for kw in top_statistical_keywords:
            if len(combined_keywords) >= num_keywords:
                break
            if kw not in combined_keywords:
                combined_keywords.append(kw)
        
        return combined_keywords[:num_keywords]

    except Exception as e:
        print(f"TF-IDF failed: {e}")
        return []

def generate_comprehensive_analysis(product_data: dict) -> dict:
    """Generate comprehensive analysis using the new rating model and focused keywords."""
    reviews = product_data.get('reviews', [])
    if not reviews: return {"error": "No reviews to analyze."}

    review_texts = [r['text'] for r in reviews]
    
    predictions = rating_classifier(review_texts, truncation=True, max_length=512, padding=True)
    
    star_ratings = [int(p['label'].split()[0]) for p in predictions]

    positive_count = sum(1 for star in star_ratings if star >= 4)
    negative_count = sum(1 for star in star_ratings if star <= 2)
    total = len(reviews)
    
    positive_percent = round((positive_count / total) * 100) if total > 0 else 0
    negative_percent = round((negative_count / total) * 100) if total > 0 else 0

    positive_reviews = [text for text, star in zip(review_texts, star_ratings) if star >= 4]
    negative_reviews = [text for text, star in zip(review_texts, star_ratings) if star <= 2]
    
    product_name = product_data.get('product_name', '')
    top_pros = extract_focused_keywords(positive_reviews, product_name)
    top_cons = extract_focused_keywords(negative_reviews, product_name)

    # --- FIX: Added truncation=True to prevent crashes on long review text ---
    summary_text = " ".join(review_texts)
    if len(summary_text) > 100: # Only summarize if there's enough text
        summary = summarizer(summary_text, max_length=50, min_length=15, do_sample=False, truncation=True)[0]['summary_text']
    else:
        summary = "Not enough review text for a summary."


    return {
        "public_opinion": {
            "positive_percent": positive_percent,
            "negative_percent": negative_percent,
            "neutral_percent": 100 - positive_percent - negative_percent,
            "total_reviews_analyzed": total,
            "quick_summary": summary,
            "average_rating": sum(star_ratings) / total if total > 0 else 0
        },
        "pros_cons_panel": {"pros": top_pros, "cons": top_cons}
    }

@app.post("/analyze/")
async def analyze_url(input_data: URLInput):
    APIFY_API_TOKEN = os.getenv("APIFY")
    if not APIFY_API_TOKEN:
        raise HTTPException(status_code=500, detail="APIFY API token is not configured.")

    try:
        loop = asyncio.get_event_loop()
        product_task = loop.run_in_executor(None, enhanced_amazon_scraper, input_data.url)
        reviews_task = loop.run_in_executor(None, enhanced_apify_review_scraper, input_data.url, APIFY_API_TOKEN)
        
        product_details = await product_task
        review_data = await reviews_task

        if not product_details or product_details.get('product_name') == "Not found":
            raise HTTPException(status_code=404, detail="Could not scrape product details.")
        if not review_data:
            raise HTTPException(status_code=404, detail="Could not scrape reviews.")

        combined_data = {**product_details, "reviews": review_data}
        analysis_results = await loop.run_in_executor(None, generate_comprehensive_analysis, combined_data)

        final_response = {**product_details, **analysis_results}
        if 'reviews' in final_response:
            del final_response['reviews']
            
        return final_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

