from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django import forms
from users.models import UserProfile


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
@login_required
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
@login_required
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