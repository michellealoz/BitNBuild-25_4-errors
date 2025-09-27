from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django import forms
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
    profile = UserProfile.objects.filter(user=request.user).first()
    if not profile:
        return redirect('user_profile_setup')
    return render(request, 'users/dashboard.html', {'profile': profile})

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
        product_url = request.POST.get("product_url")
        if product_url:
            try:
                # Set a generous timeout as scraping can be slow
                response = requests.post(FASTAPI_ANALYSIS_URL, json={"url": product_url}, timeout=90)
                response.raise_for_status()
                
                context['data'] = response.json()
                context['product_url'] = product_url

            except requests.exceptions.Timeout:
                context['error'] = "The analysis took too long to complete. Please try again."
            except requests.exceptions.RequestException as e:
                # Try to get the error detail from FastAPI's response
                try:
                    error_detail = e.response.json().get('detail', str(e))
                except:
                    error_detail = str(e)
                context['error'] = f"An error occurred: {error_detail}"

    return render(request, "users/analyzer.html", context)

@login_required(login_url='/user/login/')
def compare_product(request):
    """
    Handles the comparison of two products by calling the FastAPI endpoint twice.
    """
    context = {}
    if request.method == "POST":
        product_url_1 = request.POST.get("product_url_1")
        product_url_2 = request.POST.get("product_url_2")
        
        # Pass URLs back to the template to repopulate the form
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
                # --- NEW: Calculate Overall Score ---
                # This simple score combines rating and positive sentiment.
                data1['overall_score'] = calculate_overall_score(data1)
                data2['overall_score'] = calculate_overall_score(data2)
                # ------------------------------------
                context['data1'] = data1
                context['data2'] = data2
        else:
            context['error'] = "Please provide both product URLs to compare."

    return render(request, 'users/compare.html', context)

def fetch_analysis_data(url: str) -> dict:
    """
    A helper function to call the FastAPI endpoint for a single URL.
    """
    FASTAPI_ANALYSIS_URL = "http://127.0.0.1:8001/analyze/"
    try:
        response = requests.post(FASTAPI_ANALYSIS_URL, json={"url": url}, timeout=90)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": "Analysis timed out."}
    except requests.exceptions.RequestException as e:
        try:
            error_detail = e.response.json().get('detail', str(e))
        except (AttributeError, ValueError):
            error_detail = str(e)
        return {"error": error_detail}

def calculate_overall_score(data: dict) -> float:
    """
    Calculates a simple score out of 10 based on rating and sentiment.
    """
    try:
        # Extract the numeric part of the rating (e.g., '4.4 out of 5 stars' -> 4.4)
        rating_value = float(data.get('rating', '0').split()[0])
        # Convert to a score out of 10
        rating_score = (rating_value / 5) * 10 
        
        positive_sentiment = data.get('public_opinion', {}).get('positive_percent', 0)
        sentiment_score = positive_sentiment / 10

        # Weighted average: 60% for rating, 40% for sentiment
        overall_score = (rating_score * 0.6) + (sentiment_score * 0.4)
        return round(overall_score, 1)
    except:
        return 0.0 # Return a default score if data is malformed