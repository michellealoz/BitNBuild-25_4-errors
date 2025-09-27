import time
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from apify_client import ApifyClient
from transformers import pipeline
from collections import Counter
import os
import logging

logger = logging.getLogger(__name__)

# --- 1. Initialize AI Models (Global - loaded once on startup) ---
print("Loading AI models...")
# Model for the main pie chart (Positive/Negative)
sentiment_classifier = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english", framework="pt")
# Model for the TL;DR Summary
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", framework="pt")
print("Models loaded successfully.")


# --- 2. Define Pydantic Models for API data structure ---
class URLInput(BaseModel):
    url: str

# --- 3. Create FastAPI App Instance ---
app = FastAPI()

# --- 4. Helper Functions (Scraping and Analysis) ---

def local_product_scraper_sync(url: str) -> dict:
    """The synchronous (blocking) Selenium scraper for product details."""
    print("--- Starting local scraper for product details... ---")
    options = FirefoxOptions()
    options.headless = True
    options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0")
    
    driver = webdriver.Firefox(options=options)
    product_details = {}
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.ID, "productTitle")))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        product_details['product_name'] = soup.find('span', {'id': 'productTitle'}).get_text(strip=True) if soup.find('span', {'id': 'productTitle'}) else "Not found"
        product_details['price'] = soup.find('span', {'class': 'a-price-whole'}).get_text(strip=True) if soup.find('span', {'class': 'a-price-whole'}) else "Not found"
        product_details['rating'] = soup.find('span', {'class': 'a-icon-alt'}).get_text(strip=True) if soup.find('span', {'class': 'a-icon-alt'}) else "Not found"
        product_details['description'] = soup.find('div', {'id': 'feature-bullets'}).get_text(separator=' ', strip=True) if soup.find('div', {'id': 'feature-bullets'}) else "Not found"
        
        print("Successfully scraped product details locally.")
    except Exception as e:
        print(f"Local scraper failed: {e}")
    finally:
        driver.quit()
        
    return product_details

def apify_review_scraper_sync(url: str, api_token: str) -> list:
    """The synchronous (blocking) Apify scraper for reviews."""
    print("--- Starting Apify scraper for reviews... ---")
    client = ApifyClient(api_token)
    run_input = {
        "productUrls": [{"url": url}],
        "maxReviews": 10, 
        "scrapeProductDetails": False,
    }
    try:
        run = client.actor("R8WeJwLuzLZ6g4Bkk").call(run_input=run_input)
        
        reviews = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            if item.get('text'):
                reviews.append(item.get('text'))
        
        print(f"Successfully scraped {len(reviews)} reviews using Apify.")
        return reviews
    except Exception as e:
        print(f"Apify scraper failed: {e}")
        return []

def generate_dashboard_data(product_data: dict) -> dict:
    """Takes combined scraped data and generates the full analytics report."""
    reviews = product_data.get('reviews', [])
    if not reviews:
        return {"error": "No reviews to analyze."}

    # Public Opinion Summary
    sentiments = [result['label'] for result in sentiment_classifier(reviews, truncation=True)]
    sentiment_counts = Counter(sentiments)
    total = len(reviews)
    positive_percent = round((sentiment_counts.get('POSITIVE', 0) / total) * 100)
    negative_percent = round((sentiment_counts.get('NEGATIVE', 0) / total) * 100)
    
    # Simple Pros/Cons heuristic
    pros, cons = [], []
    positive_reviews = [r for r, s in zip(reviews, sentiments) if s == 'POSITIVE']
    negative_reviews = [r for r, s in zip(reviews, sentiments) if s == 'NEGATIVE']
    
    if positive_reviews:
        pros_summary = summarizer( ". ".join(positive_reviews), max_length=30, min_length=5, do_sample=False)[0]['summary_text']
        pros = [p.strip() for p in pros_summary.split(',')]
    if negative_reviews:
        cons_summary = summarizer( ". ".join(negative_reviews), max_length=30, min_length=5, do_sample=False)[0]['summary_text']
        cons = [c.strip() for c in cons_summary.split(',')]

    # Overall Summary
    overall_summary = summarizer(" ".join(reviews), max_length=60, min_length=20, do_sample=False)[0]['summary_text']

    return {
        "public_opinion": {
            "positive_percent": positive_percent,
            "negative_percent": negative_percent,
            "neutral_percent": 100 - positive_percent - negative_percent,
            "total_reviews_analyzed": total,
            "quick_summary": f"Most users are satisfied ({positive_percent}%), especially with features like {pros[0] if pros else 'performance'}, but {negative_percent}% mention issues like {cons[0] if cons else 'bugs'}."
        },
        "pros_cons_panel": { "pros": pros[:4], "cons": cons[:4] },
        "review_summary_generator": overall_summary
    }

# --- 5. Define the Main API Endpoint ---
@app.post("/analyze/")
async def analyze_url(input_data: URLInput):
    """Orchestrates scraping and analysis."""
    APIFY_API_TOKEN = os.getenv("APIFY") # Fallback for local 
    if not APIFY_API_TOKEN:
            logger.error("APIFY not set in environment")
            return None

    try:
        # Run synchronous code in threads to avoid blocking the server
        loop = asyncio.get_event_loop()
        local_task = loop.run_in_executor(None, local_product_scraper_sync, input_data.url)
        apify_task = loop.run_in_executor(None, apify_review_scraper_sync, input_data.url, APIFY_API_TOKEN)
        
        product_details = await local_task
        review_list = await apify_task

        if not product_details or not review_list:
            raise HTTPException(status_code=404, detail="Could not scrape all necessary data.")

        product_details['reviews'] = review_list
        
        analytics_task = loop.run_in_executor(None, generate_dashboard_data, product_details)
        dashboard_json = await analytics_task

        return dashboard_json
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

# To run: uvicorn main:app --reload --port 8001