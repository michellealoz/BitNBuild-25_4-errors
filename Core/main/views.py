from django.shortcuts import get_object_or_404, render, redirect

# Create your views here.
def landing_page(request):
    return render(request, 'main/landing.html')

def information_view(request):

    return render(request, 'main/information.html')

def about_view(request):
    return render(request, 'main/about.html')