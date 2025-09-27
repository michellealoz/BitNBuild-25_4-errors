from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.contrib import messages
from users.models import UserProfile
import requests
import re


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

from .models import ProductAnalysis, ProductComparison 
from itertools import chain
from operator import attrgetter

@login_required(login_url='/user/login/')
def analysis_view(request):
    FASTAPI_ANALYSIS_URL = "http://127.0.0.1:8001/analyze/"
    context = {}
    
    if request.method == "POST":
        product_url = request.POST.get("product_url", "").strip()
        context['product_url'] = product_url # Keep URL in context for re-display
        
        if product_url:
            try:
                # Enhanced Amazon URL validation
                if not any(domain in product_url for domain in ['amazon.com', 'amazon.in', 'amazon.co.uk']):
                    context['error'] = "Please enter a valid Amazon product URL from supported regions (com, in, co.uk)."
                elif '/dp/' not in product_url and '/product/' not in product_url:
                    context['error'] = "Please enter a direct Amazon product URL containing '/dp/' or '/product/'."
                else:
                    # Clean URL
                    if '?' in product_url:
                        product_url = product_url.split('?')[0]
                    
                    # Make request to FastAPI service
                    response = requests.post(FASTAPI_ANALYSIS_URL, 
                                           json={"url": product_url}, 
                                           timeout=120)
                    response.raise_for_status()
                    
                    api_data = response.json()
                    
                    if 'error' in api_data:
                        context['error'] = api_data['error']
                    else:
                        # On success, display the data and save the record
                        context['data'] = api_data

                        ProductAnalysis.objects.create(
                            user=request.user,
                            product_url=product_url,
                            product_name=api_data.get('product_name', 'Unknown Product'),
                            analysis_data=api_data
                        )

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
def records_view(request):
    """
    Fetches and displays all saved product analyses for the logged-in user.
    """
    # Fetch all analysis records for the current user, ordered by most recent
    user_analyses = ProductAnalysis.objects.filter(user=request.user)
    user_comparisons = ProductComparison.objects.filter(user=request.user)    
    
    all_records = sorted(
        chain(user_analyses, user_comparisons),
        key=attrgetter('created_at'),
        reverse=True
    )

    context = {
        'records': all_records
    }
    return render(request, "users/records.html", context)

@login_required(login_url='/user/login/')
def compare_product(request):
    """
    Handles the AI-powered comparison of two products by calling the FastAPI service.
    """
    context = {}
    if request.method == "POST":
        product_url_1 = request.POST.get("product_url_1", "").strip()
        product_url_2 = request.POST.get("product_url_2", "").strip()
        
        context['product_url_1'] = product_url_1
        context['product_url_2'] = product_url_2

        if product_url_1 and product_url_2:
            data1 = fetch_analysis_data(product_url_1)
            data2 = fetch_analysis_data(product_url_2)

            if "error" in data1:
                context['error'] = f"Product 1 analysis failed: {data1['error']}"
            elif "error" in data2:
                context['error'] = f"Product 2 analysis failed: {data2['error']}"
            else:
                context['data1'] = data1
                context['data2'] = data2
                comparison_metrics = generate_comparison_metrics(data1, data2)
                context['comparison'] = comparison_metrics

                ProductComparison.objects.create(
                    user=request.user,
                    product_url_1=product_url_1,
                    product_name_1=data1.get('product_name', 'Unknown Product 1'),
                    analysis_data_1=data1,
                    product_url_2=product_url_2,
                    product_name_2=data2.get('product_name', 'Unknown Product 2'),
                    analysis_data_2=data2,
                    comparison_metrics=comparison_metrics
                )
        else:
            context['error'] = "Please provide both product URLs to compare."

    return render(request, 'users/compare.html', context)


# ==============================================================================
# HELPER FUNCTIONS FOR AI ANALYSIS AND COMPARISON
# ==============================================================================

def fetch_analysis_data(url: str) -> dict:
    """
    Calls the FastAPI endpoint to get product details and AI analysis.
    This is now the single source of truth for product data.
    """
    FASTAPI_ANALYSIS_URL = "http://127.0.0.1:8001/analyze/"
    try:
        response = requests.post(FASTAPI_ANALYSIS_URL, json={"url": url}, timeout=120)
        response.raise_for_status()
        api_data = response.json()
        
        # Calculate the overall score and add it to the data object
        api_data['overall_score'] = calculate_overall_score(api_data)
        
        return api_data

    except requests.exceptions.Timeout:
        return {"error": "The analysis took too long to complete. The product page might be complex or the service is busy."}
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to the analysis service. Please ensure it is running and try again."}
    except requests.exceptions.RequestException as e:
        try:
            error_detail = e.response.json().get('detail', str(e))
        except:
            error_detail = str(e)
        return {"error": f"An error occurred during analysis: {error_detail}"}

def calculate_overall_score(data: dict) -> float:
    """
    Calculates a weighted score out of 10 based on star rating and AI sentiment.
    - 60% weight on the actual star rating.
    - 40% weight on the AI-analyzed positive sentiment from reviews.
    """
    try:
        rating_text = data.get('rating', '0')
        rating_match = re.search(r'(\d+\.?\d*)', rating_text)
        rating_value = float(rating_match.group(1)) if rating_match else 0.0
        rating_score_on_10 = (rating_value / 5) * 10
        
        positive_sentiment_percent = data.get('public_opinion', {}).get('positive_percent', 0)
        sentiment_score_on_10 = positive_sentiment_percent / 10

        weighted_score = (rating_score_on_10 * 0.6) + (sentiment_score_on_10 * 0.4)
        return round(weighted_score, 1)
    except (ValueError, TypeError):
        return 0.0

def generate_comparison_metrics(data1: dict, data2: dict) -> dict:
    """
    Generates detailed comparison metrics between two analyzed products.
    """
    score1 = data1.get('overall_score', 0)
    score2 = data2.get('overall_score', 0)

    if score1 > score2:
        winner = 'Product A'
    elif score2 > score1:
        winner = 'Product B'
    else:
        winner = 'It\'s a Tie'
        
    price1 = float(str(data1.get('price', '0')).replace(',', ''))
    price2 = float(str(data2.get('price', '0')).replace(',', ''))
    
    rating_match1 = re.search(r'(\d+\.?\d*)', data1.get('rating', '0'))
    rating1 = float(rating_match1.group(1)) if rating_match1 else 0.0
    
    rating_match2 = re.search(r'(\d+\.?\d*)', data2.get('rating', '0'))
    rating2 = float(rating_match2.group(1)) if rating_match2 else 0.0

    return {
        'winner': winner,
        'overall_winner_score_diff': round(abs(score1 - score2), 1),
        'price_difference': abs(price1 - price2),
        'rating_difference': round(abs(rating1 - rating2), 1),
        'key_differences': extract_key_differences(data1, data2),
    }

def extract_key_differences(data1: dict, data2: dict) -> list:
    """
    Identifies and returns a list of the most significant differences
    between two products based on their AI-analyzed pros.
    """
    pros1 = set(data1.get('pros_cons_panel', {}).get('pros', []))
    pros2 = set(data2.get('pros_cons_panel', {}).get('pros', []))

    unique_to_1 = list(pros1 - pros2)
    unique_to_2 = list(pros2 - pros1)
    
    differences = []
    if unique_to_1:
        differences.append(f"Product A excels with: {', '.join(unique_to_1[:2])}")
    if unique_to_2:
        differences.append(f"Product B stands out for: {', '.join(unique_to_2[:2])}")

    price1 = float(str(data1.get('price', '0')).replace(',', ''))
    price2 = float(str(data2.get('price', '0')).replace(',', ''))
    if price1 > 0 and price2 > 0:
        if price1 < price2:
            differences.append(f"Product A is more affordable by ₹{price2 - price1:,.0f}")
        elif price2 < price1:
            differences.append(f"Product B is more affordable by ₹{price1 - price2:,.0f}")

    if not differences:
        return ["Both products share very similar strengths according to user reviews."]
        
    return differences

