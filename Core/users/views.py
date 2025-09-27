from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.contrib import messages
from users.models import UserProfile
import requests

# Step 1: Signup
def user_signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('user_profile_setup')  # Step 2
        else:
            if 'username' in form.errors:
                messages.error(request, 'Username already exists. Please choose a different username.')
            elif 'password2' in form.errors:
                messages.error(request, 'Passwords do not match. Please try again.')
            else:
                messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()
    return render(request, 'users/signup.html', {'form': form})


# Step 2: Profile Setup (store in session)
@login_required(login_url='/user/login/')
def user_profile_setup_view(request):
    if request.method == 'POST':
        # Save form data to session
        request.session['user_profile_info'] = {
            'full_name': request.POST.get('full_name'),
            'email': request.POST.get('email'),
            'phone': request.POST.get('phone'),
            'dob': request.POST.get('dob'),
            'address': request.POST.get('address'),
        }
        return redirect('user_profile_complete')

    return render(request, 'users/profile_setup.html')  # basic HTML form, no instance needed


# Step 3: Profile Complete (save to DB)
@login_required(login_url='/user/login/')
def user_profile_complete(request):
    data = request.session.get('user_profile_info')
    if not data:
        return redirect('user_profile_setup')  # If session expired or user directly visits

    # Create or update the profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    profile.full_name = data['full_name']
    profile.email = data['email']
    profile.phone = data['phone']
    profile.dob = data['dob']
    profile.address = data['address']
    profile.save()

    # Clear session
    del request.session['user_profile_info']

    messages.success(request, 'Your profile has been set up successfully!')
    return redirect('user_dashboard')


# Dashboard
@login_required(login_url='/user/login/')
def user_dashboard(request):
    # Get user profile
    profile = UserProfile.objects.filter(user=request.user).first()
    if not profile:
        return redirect('user_profile_setup')
    
    # For now, use placeholder values for stats
    context = {
        'profile': profile,
        'analyses_count': 18,
        'saved_records_count': 5,
        'comparisons_count': 9,
    }
    
    return render(request, 'users/dashboard.html', context)


def user_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')  # changed from email
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('user_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'users/login.html')


@login_required(login_url='/user/login/')
def analysis_view(request):
    FASTAPI_ANALYSIS_URL = "http://127.0.0.1:8001/analyze/"
    context = {}
    
    if request.method == "POST":
        product_url = request.POST.get("product_url", "").strip()
        if product_url:
            try:
                # Enhanced Amazon URL validation
                if not any(domain in product_url for domain in ['amazon.com', 'amazon.in', 'amazon.co.uk']):
                    context['error'] = "Please enter a valid Amazon product URL from supported regions (com, in, co.uk)."
                elif '/dp/' not in product_url and '/product/' not in product_url:
                    context['error'] = "Please enter a direct Amazon product URL containing '/dp/' or '/product/'."
                else:
                    # Clean URL - extract product ID if needed
                    if '?' in product_url:
                        product_url = product_url.split('?')[0]
                    
                    # Set timeout and make request
                    response = requests.post(FASTAPI_ANALYSIS_URL, 
                                           json={"url": product_url}, 
                                           timeout=120)  # Increased timeout
                    response.raise_for_status()
                    
                    api_data = response.json()
                    
                    # Enhanced data validation
                    if 'error' in api_data:
                        context['error'] = api_data['error']
                    else:
                        context['data'] = api_data
                        context['product_url'] = product_url

            except requests.exceptions.Timeout:
                context['error'] = "The analysis took too long to complete. Please try again with a different product."
            except requests.exceptions.ConnectionError:
                context['error'] = "Cannot connect to the analysis service. Please try again later."
            except requests.exceptions.RequestException as e:
                try:
                    error_detail = e.response.json().get('detail', str(e))
                except:
                    error_detail = str(e)
                context['error'] = f"Analysis service error: {error_detail}"
            except Exception as e:
                context['error'] = f"An unexpected error occurred: {str(e)}"
        else:
            context['error'] = "Please enter a product URL."

    return render(request, "users/analyzer.html", context)


@login_required(login_url='/user/login/')
def compare_product(request):
    """
    Handles the comparison of two products using only custom scraper.
    """
    context = {}
    if request.method == "POST":
        product_url_1 = request.POST.get("product_url_1")
        product_url_2 = request.POST.get("product_url_2")
        
        # Pass URLs back to the template to repopulate the form
        context['product_url_1'] = product_url_1
        context['product_url_2'] = product_url_2

        if product_url_1 and product_url_2:
            # Use custom scraper instead of FastAPI endpoint
            data1 = custom_product_analysis(product_url_1)
            data2 = custom_product_analysis(product_url_2)

            if "error" in data1:
                context['error'] = f"Product 1 analysis failed: {data1['error']}"
            elif "error" in data2:
                context['error'] = f"Product 2 analysis failed: {data2['error']}"
            else:
                context['data1'] = data1
                context['data2'] = data2
        else:
            context['error'] = "Please provide both product URLs to compare."

    return render(request, 'users/compare.html', context)


def custom_product_analysis(url: str) -> dict:
    """
    Custom product analysis using only Selenium scraper without AI models.
    """
    try:
        # Scrape basic product data
        product_data = enhanced_amazon_scraper(url)
        
        if not product_data or product_data.get('product_name') == "Not found":
            return {"error": "Could not scrape product details"}
        
        # Generate simple analysis without AI
        analysis = generate_simple_analysis(product_data)
        
        return {**product_data, **analysis}
        
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}


def enhanced_amazon_scraper(url: str) -> dict:
    """Enhanced Selenium scraper for Amazon product details."""
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
    import time
    
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
    }
    
    try:
        driver = webdriver.Firefox(options=options)
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        
        # Wait for product page to load
        try:
            wait.until(EC.presence_of_element_located((By.ID, "productTitle")))
        except:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.a-size-large")))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Product Name
        name_selectors = [
            {'id': 'productTitle'},
            {'class': 'a-size-large'},
        ]
        for selector in name_selectors:
            element = soup.find('span', selector) if 'id' in selector else soup.find('h1', selector)
            if element:
                product_details['product_name'] = element.get_text(strip=True)
                break
        
        # Price
        price_selectors = [
            'span.a-price-whole',
            '.a-price .a-offscreen',
            '.a-text-price'
        ]
        for selector in price_selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
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
        
        # Description
        desc_selectors = [
            {'id': 'feature-bullets'},
            {'id': 'productDescription'},
        ]
        for selector in desc_selectors:
            element = soup.find('div', selector)
            if element:
                product_details['description'] = element.get_text(separator=' ', strip=True)
                break
                
    except Exception as e:
        print(f"Scraper error: {e}")
    finally:
        if driver:
            driver.quit()
            
    return product_details


def generate_simple_analysis(product_data: dict) -> dict:
    """
    Generate simple analysis without AI models - using only scraped data.
    """
    # Extract numeric rating
    rating_text = product_data.get('rating', '0 out of 5 stars')
    try:
        rating_value = float(rating_text.split()[0])
    except:
        rating_value = 0.0
    
    # Calculate simple scores based on rating
    overall_score = round((rating_value / 5) * 10, 1)
    
    # Simple sentiment approximation based on rating
    if rating_value >= 4.5:
        positive_percent = 90
        negative_percent = 5
    elif rating_value >= 4.0:
        positive_percent = 75
        negative_percent = 15
    elif rating_value >= 3.0:
        positive_percent = 50
        negative_percent = 30
    else:
        positive_percent = 25
        negative_percent = 60
    
    # Generate simple pros/cons based on product category and rating
    product_name = product_data.get('product_name', '').lower()
    
    if any(word in product_name for word in ['phone', 'mobile', 'smartphone']):
        pros = ['battery life', 'camera quality', 'performance', 'value for money']
        cons = ['heating issue', 'average display', 'slow charging', 'bloatware']
    elif any(word in product_name for word in ['laptop', 'notebook']):
        pros = ['fast performance', 'good display', 'lightweight', 'battery backup']
        cons = ['heating problem', 'average keyboard', 'poor webcam', 'short battery']
    else:
        pros = ['good quality', 'value for money', 'reliable', 'easy to use']
        cons = ['could be better', 'average performance', 'not durable', 'poor service']
    
    # Adjust pros/cons based on rating
    if rating_value < 3.0:
        pros = pros[:2]  # Fewer pros for low-rated products
        cons = cons + ['poor quality', 'not recommended']
    elif rating_value > 4.0:
        cons = cons[:2]  # Fewer cons for high-rated products
    
    return {
        'overall_score': overall_score,
        'public_opinion': {
            'positive_percent': positive_percent,
            'negative_percent': negative_percent,
            'neutral_percent': 100 - positive_percent - negative_percent,
            'total_reviews_analyzed': 100,  # Placeholder
            'quick_summary': f"Rated {rating_value}/5 stars based on customer reviews",
            'average_rating': rating_value
        },
        'pros_cons_panel': {
            'pros': pros[:4],
            'cons': cons[:4]
        },
        'review_summary_generator': f"This product has an average rating of {rating_value} out of 5 stars. Customers generally find it {'excellent' if rating_value > 4.5 else 'good' if rating_value > 4.0 else 'average' if rating_value > 3.0 else 'below average'}.",
        'review_insights': {
            'verified_reviews_count': 50,  # Placeholder
            'recent_review_count': 25      # Placeholder
        }
    }