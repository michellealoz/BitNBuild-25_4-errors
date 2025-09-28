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
from transformers import pipeline
from collections import Counter
import os
import re
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# --- 1. Initialize AI Models ---
print("Loading AI models...")
# Using more robust models for better performance
sentiment_classifier = pipeline(
    "sentiment-analysis", 
    model="distilbert-base-uncased-finetuned-sst-2-english", 
    framework="pt"
)
summarizer = pipeline(
    "summarization", 
    model="sshleifer/distilbart-cnn-12-6", 
    framework="pt"
)
print("Models loaded successfully.")


# --- 2. Pydantic Models ---
class URLInput(BaseModel):
    url: str

# --- 3. FastAPI App ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. Scraping & Data Combination Functions ---

def enhanced_amazon_scraper(url: str) -> dict:
    """Enhanced Selenium scraper for Amazon product details."""
    print(f"--- Starting enhanced Amazon scraper for: {url} ---")
    options = FirefoxOptions()
    options.add_argument("--headless")
    options.set_preference("general.useragent.override", 
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0")
    
    driver = None
    product_details = {
        'product_name': "Not found", 'price': "Not found", 'rating': "Not found",
        'description': "Not found", 'images': []
    }
    
    try:
        driver = webdriver.Firefox(options=options)
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        
        # Wait for product title to ensure page is loaded
        try:
            wait.until(EC.presence_of_element_located((By.ID, "productTitle")))
        except:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.a-size-large")))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract Product Name
        name_selectors = [{'id': 'productTitle'}, {'class': 'a-size-large product-title-word-break'}]
        for selector in name_selectors:
            element = soup.find('span', selector)
            if element:
                product_details['product_name'] = element.get_text(strip=True)
                break
        
        # Extract Price
        price_selectors = ['.a-price-whole', '.a-price .a-offscreen']
        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True).replace('₹', '').replace(',', '').strip()
                # Find the integer/float part of the price
                match = re.search(r'[\d,]+\.?\d*', price_text)
                if match:
                    product_details['price'] = match.group(0)
                    break
        
        # Extract Rating
        rating_element = soup.select_one('span.a-icon-alt')
        if rating_element:
            product_details['rating'] = rating_element.get_text(strip=True)
        
        # Extract Description
        desc_element = soup.select_one('#feature-bullets')
        if desc_element:
            product_details['description'] = " ".join([li.get_text(strip=True) for li in desc_element.find_all('li')])

        # Extract Images
        image_container = soup.select_one('#imgTagWrapperId')
        if image_container and image_container.find('img'):
            src = image_container.find('img').get('src')
            if src and 'http' in src:
                product_details['images'] = [src]

        print(f"✅ Successfully scraped product: {product_details['product_name']}")
        
    except Exception as e:
        print(f"❌ Enhanced scraper failed: {e}")
    finally:
        if driver:
            driver.quit()
            
    return product_details

def enhanced_apify_review_scraper(url: str, api_token: str) -> list:
    """Enhanced Apify scraper for fetching reviews."""
    print(f"--- Starting enhanced Apify scraper for: {url} ---")
    client = ApifyClient(api_token)
    
    run_input = {
        "productUrls": [{"url": url}], "maxReviews": 50, "sort": "helpful",
    }
    
    try:
        run = client.actor("R8WeJwLuzLZ6g4Bkk").call(run_input=run_input)
        
        reviews_data = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            review_text = f"{item.get('reviewTitle', '')}. {item.get('reviewDescription', '')}".strip()
            if review_text and review_text != ".":
                reviews_data.append({
                    'text': review_text, 'rating': item.get('ratingScore', 0),
                    'date': item.get('date', ''), 'verified': item.get('isVerified', False),
                })
        
        print(f"✅ Successfully scraped {len(reviews_data)} reviews using Apify.")
        return reviews_data
        
    except Exception as e:
        print(f"❌ Enhanced Apify scraper failed: {e}")
        return []

def combine_scraped_data(product_details: dict, reviews: list) -> dict:
    """Combine data from both scrapers."""
    combined_data = {**product_details}
    combined_data['reviews'] = [r['text'] for r in reviews if r.get('text')]
    combined_data['raw_reviews'] = reviews  # **IMPORTANT:** Pass raw reviews for rating distribution
    return combined_data

# --- 5. Analysis Functions ---

def extract_key_phrases(texts: list, num_keywords: int = 5) -> list:
    """Extract meaningful phrases using TF-IDF."""
    if not texts or len(texts) < 2: return []
    try:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(2, 3), max_df=0.85, min_df=2)
        X = vectorizer.fit_transform(texts)
        scores = X.sum(axis=0).tolist()[0]
        terms = vectorizer.get_feature_names_out()
        df = pd.DataFrame({"term": terms, "score": scores})
        top_terms = df.sort_values("score", ascending=False).head(num_keywords)
        return top_terms["term"].tolist()
    except Exception as e:
        print(f"Keyword extraction failed: {e}")
        return []

def get_quotes_for_phrases(reviews: list, phrases: list) -> dict:
    """Find specific sentences in reviews that contain key phrases."""
    phrase_quotes = {p: [] for p in phrases}
    for phrase in phrases:
        for review in reviews:
            # Find a sentence containing the phrase
            match = re.search(r'([^.!?]*' + re.escape(phrase) + r'[^.!?]*[.!?])', review, re.IGNORECASE)
            if match:
                phrase_quotes[phrase].append(match.group(0).strip())
                if len(phrase_quotes[phrase]) >= 1: # Get one clear example
                    break
    return phrase_quotes

def generate_comprehensive_analysis(product_data: dict) -> dict:
    """Generate the full analysis report from combined data."""
    reviews = product_data.get('reviews', [])
    if not reviews: return {"error": "No reviews to analyze."}

    # --- Sentiment Analysis ---
    sentiments = [r['label'] for r in sentiment_classifier(reviews, truncation=True, max_length=512)]
    sentiment_counts = Counter(sentiments)
    total = len(reviews)
    positive_percent = round((sentiment_counts.get('POSITIVE', 0) / total) * 100) if total > 0 else 0

    # --- Pros & Cons Extraction ---
    positive_reviews = [r for r, s in zip(reviews, sentiments) if s == "POSITIVE"]
    negative_reviews = [r for r, s in zip(reviews, sentiments) if s == "NEGATIVE"]
    top_pros_phrases = extract_key_phrases(positive_reviews)
    top_cons_phrases = extract_key_phrases(negative_reviews)
    pros_quotes = get_quotes_for_phrases(positive_reviews, top_pros_phrases)
    cons_quotes = get_quotes_for_phrases(negative_reviews, top_cons_phrases)
    
    # --- AI Summaries ---
    full_text = " ".join(reviews)[:4000] # Truncate for performance
    overall_summary = summarizer(full_text, max_length=100, min_length=40)[0]['summary_text'] if len(full_text) > 200 else "Not enough review data for a detailed summary."
    quick_summary = summarizer(full_text, max_length=50, min_length=20)[0]['summary_text'] if len(full_text) > 100 else "Not enough review data."

    # --- **NEW**: Calculate Rating Distribution ---
    raw_reviews = product_data.get('raw_reviews', [])
    rating_counts = Counter([r.get('rating', 0) for r in raw_reviews])
    rating_distribution = {
        "5 stars": rating_counts.get(5, 0), "4 stars": rating_counts.get(4, 0),
        "3 stars": rating_counts.get(3, 0), "2 stars": rating_counts.get(2, 0),
        "1 star": rating_counts.get(1, 0)
    }

    # --- Compile Final Analysis ---
    return {
        "public_opinion": {
            "positive_percent": positive_percent,
            "total_reviews_analyzed": total,
            "quick_summary": quick_summary,
        },
        "pros_cons_panel": {
            "pros": [{"keyword": p, "examples": pros_quotes.get(p, [])} for p in top_pros_phrases],
            "cons": [{"keyword": c, "examples": cons_quotes.get(c, [])} for c in top_cons_phrases]
        },
        "review_summary_generator": overall_summary,
        "rating_distribution": rating_distribution,
        "review_insights": {
             "verified_reviews_count": sum(1 for r in raw_reviews if r.get('verified')),
             "recent_review_count": sum(1 for r in raw_reviews if '2025' in r.get('date', '')) # Example year
        }
    }

# --- 6. Main API Endpoint ---
@app.post("/analyze/")
async def analyze_url(input_data: URLInput):
    """Orchestrates the scraping and analysis workflow."""
    APIFY_API_TOKEN = os.getenv("APIFY")
    if not APIFY_API_TOKEN:
        raise HTTPException(status_code=500, detail="APIFY API token is not configured.")

    try:
        loop = asyncio.get_event_loop()
        
        # Run scraping concurrently
        product_task = loop.run_in_executor(None, enhanced_amazon_scraper, input_data.url)
        reviews_task = loop.run_in_executor(None, enhanced_apify_review_scraper, input_data.url, APIFY_API_TOKEN)
        
        product_details = await product_task
        review_data = await reviews_task

        if not product_details or product_details.get('product_name') == "Not found":
            raise HTTPException(status_code=404, detail="Could not scrape product details. The URL may be invalid or the page structure may have changed.")
        
        if not review_data:
            raise HTTPException(status_code=404, detail="Could not scrape reviews for this product.")

        combined_data = combine_scraped_data(product_details, review_data)
        
        analysis_results = await loop.run_in_executor(None, generate_comprehensive_analysis, combined_data)
        
        # Combine all data for the final response
        final_response = {**product_details, **analysis_results}
        
        # Clean up unnecessary fields before sending
        if 'reviews' in final_response: del final_response['reviews']
        if 'raw_reviews' in final_response: del final_response['raw_reviews']
            
        return final_response

    except HTTPException as e:
        raise e # Re-raise known HTTP exceptions
    except Exception as e:
        logger.exception("An unexpected error occurred during analysis.")
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {str(e)}")