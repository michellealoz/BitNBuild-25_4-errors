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
from sklearn.feature_extraction.text import TfidfVectorizer
import pandas as pd
from apify_client import ApifyClient
from transformers import pipeline
from collections import Counter
import os
import logging
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# --- 1. Initialize AI Models ---
print("Loading AI models...")
sentiment_classifier = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english", framework="pt")
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", framework="pt")
print("Models loaded successfully.")

# --- 2. Pydantic Models ---
class URLInput(BaseModel):
    url: str

# --- 3. FastAPI App ---
app = FastAPI()

# --- 4. Enhanced Scraping Functions ---

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
        
        # Wait for critical elements with multiple fallbacks
        try:
            wait.until(EC.presence_of_element_located((By.ID, "productTitle")))
        except:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.a-size-large")))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Product Name with multiple selectors
        name_selectors = [
            {'id': 'productTitle'},
            {'class': 'a-size-large'},
            {'class': 'product-title'}
        ]
        for selector in name_selectors:
            element = soup.find('span', selector) if 'id' in selector else soup.find('h1', selector)
            if element:
                product_details['product_name'] = element.get_text(strip=True)
                break
        
        # Price with multiple selectors
        price_selectors = [
            'span.a-price-whole',
            '.a-price[data-a-size="xl"] span',
            '.a-price .a-offscreen',
            '.a-text-price'
        ]
        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                # Clean price text
                if '₹' in price_text:
                    product_details['price'] = price_text.replace('₹', '').replace(',', '').strip()
                else:
                    product_details['price'] = price_text
                break
        
        # Rating
        rating_element = soup.find('span', {'class': 'a-icon-alt'})
        if rating_element:
            rating_text = rating_element.get_text(strip=True)
            if 'out of' in rating_text:
                product_details['rating'] = rating_text
        
        # Description/Highlights
        desc_selectors = [
            {'id': 'feature-bullets'},
            {'id': 'productDescription'},
            {'class': 'product-description'}
        ]
        for selector in desc_selectors:
            element = soup.find('div', selector)
            if element:
                product_details['description'] = element.get_text(separator=' ', strip=True)
                break
        
        # Try to get product images
        image_elements = soup.find_all('img', {'class': 'a-dynamic-image'})
        for img in image_elements[:3]:  # Get first 3 images
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
    
    # Enhanced input configuration
    run_input = {
        "productUrls": [{"url": url}],
        "maxReviews": 50,  # Increased for better analysis
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
        
        # Wait for completion and get all items
        reviews_data = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            # Extract both title and description for richer analysis
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
    
    # Extract just review texts for analysis
    review_texts = [review['text'] for review in reviews if review['text']]
    combined_data['reviews'] = review_texts
    
    # Add review metadata for display
    combined_data['review_metadata'] = {
        'total_reviews': len(reviews),
        'average_rating': sum([r['rating'] for r in reviews if r['rating']]) / len(reviews) if reviews else 0,
        'verified_reviews': sum([1 for r in reviews if r.get('verified', False)]),
        'recent_reviews': [r for r in reviews if '2025' in r.get('date', '')][:5]  # Recent reviews
    }
    
    return combined_data

def extract_top_keywords_tfidf(texts: list, num_keywords: int = 5) -> list:
    """Enhanced keyword extraction with better preprocessing."""
    if not texts or len(texts) < 2:
        return []
    
    try:
        vectorizer = TfidfVectorizer(
            stop_words='english', 
            ngram_range=(1, 2),
            max_df=0.85,
            min_df=1,  # Reduced for smaller datasets
            max_features=1000
        )
        tfidf_matrix = vectorizer.fit_transform(texts)
        sum_tfidf = tfidf_matrix.sum(axis=0)
        words = vectorizer.get_feature_names_out()
        tfidf_scores = list(sum_tfidf.tolist()[0])
        
        df = pd.DataFrame({'term': words, 'score': tfidf_scores})
        keywords = df.sort_values(by='score', ascending=False).head(num_keywords)['term'].tolist()
        
        # Filter out generic terms
        generic_terms = ['phone', 'product', 'item', 'buy', 'purchase']
        return [kw for kw in keywords if kw not in generic_terms]
        
    except Exception as e:
        print(f"TF-IDF failed: {e}")
        return []

def generate_comprehensive_analysis(product_data: dict) -> dict:
    """Generate comprehensive analysis with enhanced features."""
    reviews = product_data.get('reviews', [])
    if not reviews:
        return {"error": "No reviews to analyze."}

    # Sentiment Analysis
    sentiments = [result['label'] for result in sentiment_classifier(reviews, truncation=True, max_length=512, padding=True)]
    sentiment_counts = Counter(sentiments)
    total = len(reviews)
    positive_percent = round((sentiment_counts.get('POSITIVE', 0) / total) * 100) if total > 0 else 0
    negative_percent = round((sentiment_counts.get('NEGATIVE', 0) / total) * 100) if total > 0 else 0
    neutral_percent = 100 - positive_percent - negative_percent
    
    # Enhanced keyword extraction with sentiment context
    positive_reviews = [r for r, s in zip(reviews, sentiments) if s == 'POSITIVE']
    negative_reviews = [r for r, s in zip(reviews, sentiments) if s == 'NEGATIVE']
    
    top_pros_keywords = extract_top_keywords_tfidf(positive_reviews, num_keywords=6)
    top_cons_keywords = extract_top_keywords_tfidf(negative_reviews, num_keywords=6)

    # Enhanced summaries
    summary_text = " ".join(reviews)
    truncated_text = summary_text[:4000]  # Safe limit for summarization
    
    overall_summary = summarizer(
    truncated_text, 
    max_length=80, 
    min_length=30, 
    do_sample=False,
    truncation=True
    )[0]['summary_text'] if len(truncated_text) > 100 else "Not enough reviews for detailed summary."
 

    quick_summary = summarizer(
    truncated_text, 
    max_length=40, 
    min_length=15, 
    do_sample=False,
    truncation=True
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
            "pros": top_pros_keywords[:4],  # Top 4 pros
            "cons": top_cons_keywords[:4]   # Top 4 cons
        },
        "review_summary_generator": overall_summary,
        "review_insights": {
            "verified_reviews_count": product_data.get('review_metadata', {}).get('verified_reviews', 0),
            "recent_review_count": len([r for r in product_data.get('review_metadata', {}).get('recent_reviews', [])])
        }
    }

# --- 5. Main API Endpoint with Dual Scraping ---
@app.post("/analyze/")
async def analyze_url(input_data: URLInput):
    """Orchestrates dual scraping strategy and analysis."""
    APIFY_API_TOKEN = os.getenv("APIFY")
    if not APIFY_API_TOKEN:
        raise HTTPException(status_code=500, detail="APIFY API token is not configured.")

    try:
        loop = asyncio.get_event_loop()
        
        # Run both scrapers in parallel
        product_task = loop.run_in_executor(None, enhanced_amazon_scraper, input_data.url)
        reviews_task = loop.run_in_executor(None, enhanced_apify_review_scraper, input_data.url, APIFY_API_TOKEN)
        
        product_details = await product_task
        review_data = await reviews_task

        # Check if we have minimum required data
        if not product_details or product_details.get('product_name') == "Not found":
            raise HTTPException(status_code=404, detail="Could not scrape product details. URL may be invalid.")
        
        if not review_data:
            raise HTTPException(status_code=404, detail="Could not scrape reviews. Product may have no reviews or URL structure has changed.")

        # Combine data from both sources
        combined_data = combine_scraped_data(product_details, review_data)
        
        # Generate analysis
        analytics_task = loop.run_in_executor(None, generate_comprehensive_analysis, combined_data)
        analysis_results = await analytics_task

        # Combine all data for response
        final_response = {
            **product_details,
            **analysis_results
        }
        
        # Remove raw reviews to reduce response size
        if 'reviews' in final_response:
            del final_response['reviews']
            
        return final_response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# import time
# import asyncio
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from selenium import webdriver
# from selenium.webdriver.firefox.options import Options as FirefoxOptions
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from bs4 import BeautifulSoup
# from sklearn.feature_extraction.text import TfidfVectorizer
# import pandas as pd
# from apify_client import ApifyClient
# from transformers import pipeline
# from collections import Counter
# import os
# import logging
# from dotenv import load_dotenv
# load_dotenv()

# logger = logging.getLogger(__name__)

# # --- 1. Initialize AI Models (Global - loaded once on startup) ---
# print("Loading AI models...")
# sentiment_classifier = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english", framework="pt")
# summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", framework="pt")
# print("Models loaded successfully.")


# # --- 2. Define Pydantic Models for API data structure ---
# class URLInput(BaseModel):
#     url: str

# # --- 3. Create FastAPI App Instance ---
# app = FastAPI()

# # --- 4. Helper Functions (Scraping and Analysis) ---

# def local_product_scraper_sync(url: str) -> dict:
#     """The synchronous (blocking) Selenium scraper for Amazon product details."""
#     print(f"--- Starting local scraper for: {url} ---")
#     options = FirefoxOptions()
#     options.add_argument("--headless")
#     options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0")
    
#     driver = None
#     product_details = {}
    
#     try:
#         driver = webdriver.Firefox(options=options)
#         driver.get(url)
#         wait = WebDriverWait(driver, 15)
        
#         # More robust waiting for Amazon elements
#         wait.until(EC.presence_of_element_located((By.ID, "productTitle")))
        
#         soup = BeautifulSoup(driver.page_source, 'html.parser')
        
#         # Amazon-specific selectors
#         product_details['product_name'] = soup.find('span', {'id': 'productTitle'}).get_text(strip=True) if soup.find('span', {'id': 'productTitle'}) else "Not found"
        
#         # Price - multiple possible selectors for Amazon
#         price_selectors = [
#             'span.a-price-whole',
#             'span.a-price[data-a-size="xl"] span',
#             '.a-price .a-offscreen'
#         ]
#         product_details['price'] = "Not found"
#         for selector in price_selectors:
#             price_element = soup.select_one(selector)
#             if price_element:
#                 product_details['price'] = price_element.get_text(strip=True)
#                 break
        
#         # Rating
#         rating_element = soup.find('span', {'class': 'a-icon-alt'})
#         product_details['rating'] = rating_element.get_text(strip=True) if rating_element else "Not found"
        
#         # Description
#         description_element = soup.find('div', {'id': 'feature-bullets'})
#         product_details['description'] = description_element.get_text(separator=' ', strip=True) if description_element else "Not found"
        
#         print(f"Successfully scraped product details for: {product_details.get('product_name')}")
#     except Exception as e:
#         print(f"Local scraper failed: {e}")
#     finally:
#         if driver:
#             driver.quit()
            
#     return product_details

# def apify_review_scraper_sync(url: str, api_token: str) -> list:
#     """The synchronous (blocking) Apify scraper for reviews."""
#     print(f"--- Starting Apify scraper for: {url} ---")
#     client = ApifyClient(api_token)
#     run_input = {
#         "productUrls": [{"url": url}],
#         "maxReviews": 10, 
#         "scrapeProductDetails": False,
#     }
#     try:
#         run = client.actor("R8WeJwLuzLZ6g4Bkk").call(run_input=run_input)
        
#         # --- FIX: Use list_items() for reliable data retrieval ---
#         # This prevents the race condition and ensures you get the data
#         # after the Apify run is completely finished.
#         reviews = [item.get('text') for item in client.dataset(run["defaultDatasetId"]).list_items().items if item.get('text')]
        
#         print(f"Successfully scraped {len(reviews)} reviews using Apify.")
#         return reviews
#     except Exception as e:
#         print(f"Apify scraper failed: {e}")
#         return []

# def extract_top_keywords_tfidf(texts: list, num_keywords: int = 5) -> list:
#     """Extracts the most significant keywords from a list of texts using TF-IDF."""
#     if not texts:
#         return []
#     try:
#         vectorizer = TfidfVectorizer(
#             stop_words='english', 
#             ngram_range=(1, 2),
#             max_df=0.85,
#             min_df=2
#         )
#         tfidf_matrix = vectorizer.fit_transform(texts)
#         sum_tfidf = tfidf_matrix.sum(axis=0)
#         words = vectorizer.get_feature_names_out()
#         tfidf_scores = list(sum_tfidf.tolist()[0])
#         df = pd.DataFrame({'term': words, 'score': tfidf_scores})
#         return df.sort_values(by='score', ascending=False).head(num_keywords)['term'].tolist()
#     except Exception as e:
#         print(f"TF-IDF failed: {e}")
#         return []

# def generate_dashboard_data(product_data: dict) -> dict:
#     """Takes combined scraped data and generates the full analytics report."""
#     reviews = product_data.get('reviews', [])
#     if not reviews:
#         return {"error": "No reviews to analyze."}

#     sentiments = [result['label'] for result in sentiment_classifier(reviews, truncation=True)]
#     sentiment_counts = Counter(sentiments)
#     total = len(reviews)
#     positive_percent = round((sentiment_counts.get('POSITIVE', 0) / total) * 100)
#     negative_percent = round((sentiment_counts.get('NEGATIVE', 0) / total) * 100)
    
#     positive_reviews = [r for r, s in zip(reviews, sentiments) if s == 'POSITIVE']
#     negative_reviews = [r for r, s in zip(reviews, sentiments) if s == 'NEGATIVE']
    
#     top_pros_keywords = extract_top_keywords_tfidf(positive_reviews, num_keywords=4)
#     top_cons_keywords = extract_top_keywords_tfidf(negative_reviews, num_keywords=4)

#     # Use a larger chunk of reviews for a better summary
#     summary_text = " ".join(reviews)
#     overall_summary = summarizer(summary_text, max_length=60, min_length=20, do_sample=False)[0]['summary_text']
#     quick_summary = summarizer(summary_text, max_length=40, min_length=15, do_sample=False)[0]['summary_text']

#     return {
#         "public_opinion": {
#             "positive_percent": positive_percent,
#             "negative_percent": negative_percent,
#             "neutral_percent": 100 - positive_percent - negative_percent,
#             "total_reviews_analyzed": total,
#             "quick_summary": quick_summary
#         },
#         "pros_cons_panel": { 
#             "pros": top_pros_keywords, 
#             "cons": top_cons_keywords 
#         },
#         "review_summary_generator": overall_summary
#     }

# # --- 5. Define the Main API Endpoint ---
# @app.post("/analyze/")
# async def analyze_url(input_data: URLInput):
#     """Orchestrates scraping and analysis."""
#     APIFY_API_TOKEN = os.getenv("APIFY")
#     if not APIFY_API_TOKEN:
#         raise HTTPException(status_code=500, detail="APIFY API token is not configured on the server.")

#     try:
#         loop = asyncio.get_event_loop()
#         local_task = loop.run_in_executor(None, local_product_scraper_sync, input_data.url)
#         apify_task = loop.run_in_executor(None, apify_review_scraper_sync, input_data.url, APIFY_API_TOKEN)
        
#         product_details = await local_task
#         review_list = await apify_task

#         # More robust check for scraping success
#         if not product_details or 'product_name' not in product_details or not review_list:
#             raise HTTPException(status_code=404, detail="Could not scrape all necessary data. The URL may be invalid or the page structure has changed.")

#         product_details['reviews'] = review_list
        
#         analytics_task = loop.run_in_executor(None, generate_dashboard_data, product_details)
#         dashboard_json = await analytics_task

#         # --- FIX: Combine product details with analysis results ---
#         final_response = {**product_details, **dashboard_json}
#         # Don't send all the raw reviews back to the frontend
#         if 'reviews' in final_response:
#             del final_response['reviews']
            
#         return final_response

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

# # To run: uvicorn Core.Core.main:app --reload --port 8001

