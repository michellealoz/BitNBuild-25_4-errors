from django.shortcuts import get_object_or_404, render, redirect
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .utils import get_sentiment_timeline

# Create your views here.
def landing_page(request):
    return render(request, 'main/landing.html')

def information_view(request):

    return render(request, 'main/information.html')

<<<<<<< HEAD
def about_view(request):
    return render(request, 'main/about.html')
=======
@api_view(['GET'])
def sentiment_timeline_api(request):
    """
    GET params:
      - product_url (required)
      - period: 'day' or 'week'
    Returns:
      [{"date": "2025-09-01", "positive": 5, "negative": 1, "neutral": 2}, ...]
    """
    product_url = request.GET.get('product_url')
    period = request.GET.get('period', 'day')
    if not product_url:
        return Response({"error": "Missing product_url"}, status=400)
    data = get_sentiment_timeline(product_url, period)
    return Response(data)
>>>>>>> b5b45be919248d34ce22af5e5e9d16b0f8ea9c95
