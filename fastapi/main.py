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
from sklearn.feature_extraction.text import TfidfVectorizer # Switched from CountVectorizer
import pandas as pd
from apify_client import ApifyClient
from transformers import pipeline
from collections import Counter
import os
import re # Import regex for sentence splitting
import logging
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# --- 1. Initialize AI Models ---
# (Keep this section as is)
print("Loading AI models...")
sentiment_classifier = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english", framework="pt")
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", framework="pt")
print("Models loaded successfully.")


# --- 2. Pydantic Models ---
# (Keep this section as is)
class URLInput(BaseModel):
    url: str

# --- 3. FastAPI App ---
# (Keep this section as is)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. Enhanced Scraping Functions ---
# (Keep your scraping functions as they are)

def enhanced_amazon_scraper(url: str) -> dict:
    """Enhanced Selenium scraper for Amazon product details with better error handling."""
    print(f"--- Starting enhanced Amazon scraper for: {url} ---")
    options = FirefoxOptions()
    options.add_argument("--headless")
    options.set_preference("general.useragent.override", 
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0")
    
    driver = None
    product_details = {
        'product_name': "Not found",
        'price': "Not found", 
        'rating': "Not found",
        'description': "Not found",
        'images': []
    }
    
    try:
        driver = webdriver.Firefox(options=options)
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        
        try:
            wait.until(EC.presence_of_element_located((By.ID, "productTitle")))
        except:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.a-size-large")))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        name_selectors = [{'id': 'productTitle'}, {'class': 'a-size-large'}, {'class': 'product-title'}]
        for selector in name_selectors:
            element = soup.find('span', selector) if 'id' in selector else soup.find('h1', selector)
            if element:
                product_details['product_name'] = element.get_text(strip=True)
                break
        
        price_selectors = ['span.a-price-whole', '.a-price[data-a-size="xl"] span', '.a-price .a-offscreen', '.a-text-price']
        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                if '₹' in price_text:
                    product_details['price'] = price_text.replace('₹', '').replace(',', '').strip()
                else:
                    product_details['price'] = price_text
                break
        
        rating_element = soup.find('span', {'class': 'a-icon-alt'})
        if rating_element:
            rating_text = rating_element.get_text(strip=True)
            if 'out of' in rating_text:
                product_details['rating'] = rating_text
        
        desc_selectors = [{'id': 'feature-bullets'}, {'id': 'productDescription'}, {'class': 'product-description'}]
        for selector in desc_selectors:
            element = soup.find('div', selector)
            if element:
                product_details['description'] = element.get_text(separator=' ', strip=True)
                break
        
        image_elements = soup.find_all('img', {'class': 'a-dynamic-image'})
        for img in image_elements[:3]:
            src = img.get('src') or img.get('data-src')
            if src and 'http' in src:
                product_details['images'].append(src)
        
        print(f"✅ Successfully scraped product: {product_details['product_name']}")
        
    except Exception as e:
        print(f"❌ Enhanced scraper failed: {e}")
    finally:
        if driver:
            driver.quit()
            
    return product_details

def enhanced_apify_review_scraper(url: str, api_token: str) -> list:
    """Enhanced Apify scraper with better error handling and data extraction."""
    print(f"--- Starting enhanced Apify scraper for: {url} ---")
    client = ApifyClient(api_token)
    
    run_input = {
        "productUrls": [{"url": url}],
        "maxReviews": 50,
        "includeGdprSensitive": False,
        "sort": "helpful",
        "filterByRatings": ["allStars"],
        "reviewsUseProductVariantFilter": False,
        "scrapeProductDetails": False,
        "reviewsAlwaysSaveCategoryData": False,
        "deduplicateRedirectedAsins": True,
    }
    
    try:
        run = client.actor("R8WeJwLuzLZ6g4Bkk").call(run_input=run_input)
        
        reviews_data = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            review_text = ""
            if item.get('reviewTitle'):
                review_text += item['reviewTitle'] + ". "
            if item.get('reviewDescription'):
                review_text += item['reviewDescription']
            
            if review_text.strip():
                reviews_data.append({
                    'text': review_text.strip(),
                    'rating': item.get('ratingScore', 0),
                    'date': item.get('date', ''),
                    'verified': item.get('isVerified', False),
                    'helpful': item.get('reviewReaction', '')
                })
        
        print(f"✅ Successfully scraped {len(reviews_data)} reviews using Apify.")
        return reviews_data
        
    except Exception as e:
        print(f"❌ Enhanced Apify scraper failed: {e}")
        return []

def combine_scraped_data(product_details: dict, reviews: list) -> dict:
    """Combine data from both scrapers and enhance with metadata."""
    combined_data = {**product_details}
    
    review_texts = [review['text'] for review in reviews if review['text']]
    combined_data['reviews'] = review_texts
    
    combined_data['review_metadata'] = {
        'total_reviews': len(reviews),
        'average_rating': sum([r['rating'] for r in reviews if r['rating']]) / len(reviews) if reviews else 0,
        'verified_reviews': sum([1 for r in reviews if r.get('verified', False)]),
        'recent_reviews': [r for r in reviews if '2025' in r.get('date', '')][:5]
    }
    
    return combined_data

# ====================================================================
# START OF MODIFIED CODE
# ====================================================================

def extract_key_phrases(texts: list, num_keywords: int = 6) -> list:
    """
    Extract meaningful phrases (bigrams/trigrams) using TF-IDF.
    This finds phrases that are important and characteristic, not just frequent.
    """
    if not texts:
        return []
    try:
        # Use TfidfVectorizer to find important terms, not just frequent ones
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(2, 3),  # Focus on phrases (2-3 words)
            max_df=0.8,
            min_df=2  # Phrase must appear in at least 2 reviews
        )
        X = vectorizer.fit_transform(texts)
        
        # Get scores and feature names
        scores = X.sum(axis=0).tolist()[0]
        terms = vectorizer.get_feature_names_out()
        
        # Create a DataFrame and sort by score
        df = pd.DataFrame({"term": terms, "score": scores})
        top_terms = df.sort_values("score", ascending=False).head(num_keywords * 2) # Get more to filter down

        # Clean up and filter generic terms
        blacklist = {"good", "bad", "product", "buy", "purchase", "item", "really", "great", "nice", "love"}
        
        # Filter out phrases that contain blacklisted words or are too short
        filtered_terms = [
            term for term in top_terms["term"].tolist()
            if not any(b in term.split() for b in blacklist)
        ]

        return filtered_terms[:num_keywords]
    except Exception as e:
        print(f"Keyword extraction failed: {e}")
        return []


def get_quotes_for_phrases(reviews: list, phrases: list, max_quotes: int = 2) -> dict:
    """
    For each key phrase, find the specific sentence in a review that contains it.
    This provides a short, contextual quote.
    """
    phrase_quotes = {phrase: [] for phrase in phrases}
    for phrase in phrases:
        quotes_found = 0
        for review in reviews:
            # Split review into sentences using regex for better accuracy
            sentences = re.split(r'(?<=[.!?])\s+', review)
            for sentence in sentences:
                if phrase.lower() in sentence.lower():
                    # Add the specific sentence as a quote
                    phrase_quotes[phrase].append(sentence.strip())
                    quotes_found += 1
                    break # Move to the next review after finding a quote
            if quotes_found >= max_quotes:
                break # Stop searching once we have enough quotes for this phrase
    return phrase_quotes

# --- Main Analysis function with the new quote logic ---

def generate_comprehensive_analysis(product_data: dict) -> dict:
    """Generate comprehensive analysis with improved pros & cons using phrases and quotes."""
    reviews = product_data.get('reviews', [])
    if not reviews:
        return {"error": "No reviews to analyze."}

    # --- Sentiment Analysis (no changes here) ---
    sentiments = [result['label'] for result in sentiment_classifier(
        reviews, truncation=True, max_length=512, padding=True)]
    sentiment_counts = Counter(sentiments)
    total = len(reviews)
    positive_percent = round((sentiment_counts.get('POSITIVE', 0) / total) * 100) if total > 0 else 0
    negative_percent = round((sentiment_counts.get('NEGATIVE', 0) / total) * 100) if total > 0 else 0
    neutral_percent = 100 - positive_percent - negative_percent

    # --- Improved Pros & Cons using new functions ---
    positive_reviews = [r for r, s in zip(reviews, sentiments) if s == "POSITIVE"]
    negative_reviews = [r for r, s in zip(reviews, sentiments) if s == "NEGATIVE"]

    # Use the new function to get meaningful phrases
    top_pros_phrases = extract_key_phrases(positive_reviews, num_keywords=5)
    top_cons_phrases = extract_key_phrases(negative_reviews, num_keywords=5)
    
    # Use the new function to get specific sentence quotes
    pros_quotes = get_quotes_for_phrases(positive_reviews, top_pros_phrases)
    cons_quotes = get_quotes_for_phrases(negative_reviews, top_cons_phrases)

    # --- Summaries (no changes here) ---
    summary_text = " ".join(reviews)
    truncated_text = summary_text[:4000]
    overall_summary = summarizer(
        truncated_text, max_length=80, min_length=30, do_sample=False, truncation=True
    )[0]['summary_text'] if len(truncated_text) > 100 else "Not enough reviews for detailed summary."
    quick_summary = summarizer(
        truncated_text, max_length=40, min_length=15, do_sample=False, truncation=True
    )[0]['summary_text'] if len(truncated_text) > 50 else "Insufficient review data."

    return {
        "public_opinion": {
            "positive_percent": positive_percent,
            "negative_percent": negative_percent,
            "neutral_percent": neutral_percent,
            "total_reviews_analyzed": total,
            "quick_summary": quick_summary,
            "average_rating": product_data.get('review_metadata', {}).get('average_rating', 0)
        },
        "pros_cons_panel": {
            # Structure the response with the phrase and its example quotes
            "pros": [{"keyword": phrase, "examples": pros_quotes[phrase]} for phrase in top_pros_phrases if pros_quotes.get(phrase)],
            "cons": [{"keyword": phrase, "examples": cons_quotes[phrase]} for phrase in top_cons_phrases if cons_quotes.get(phrase)]
        },
        "review_summary_generator": overall_summary,
        "review_insights": {
            "verified_reviews_count": product_data.get('review_metadata', {}).get('verified_reviews', 0),
            "recent_review_count": len([r for r in product_data.get('review_metadata', {}).get('recent_reviews', [])])
        }
    }


# ====================================================================
# END OF MODIFIED CODE
# ====================================================================


# --- 5. Main API Endpoint with Dual Scraping ---
# (Keep this section as is)
@app.post("/analyze/")
async def analyze_url(input_data: URLInput):
    """Orchestrates dual scraping strategy and analysis."""
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
            raise HTTPException(status_code=404, detail="Could not scrape product details. URL may be invalid.")
        
        if not review_data:
            raise HTTPException(status_code=404, detail="Could not scrape reviews. Product may have no reviews or URL structure has changed.")

        combined_data = combine_scraped_data(product_details, review_data)
        
        analytics_task = loop.run_in_executor(None, generate_comprehensive_analysis, combined_data)
        analysis_results = await analytics_task

        final_response = {
            **product_details,
            **analysis_results
        }
        
        if 'reviews' in final_response:
            del final_response['reviews']
            
        return final_response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")