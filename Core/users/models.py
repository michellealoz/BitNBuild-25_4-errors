from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    dob = models.DateField(null=True, blank=True)
    address = models.TextField()
    
    def __str__(self):
        return self.full_name

class ProductAnalysis(models.Model):
    """
    Stores the result of a product review analysis for a specific user.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analyses')
    product_url = models.URLField(max_length=1024)
    product_name = models.CharField(max_length=512)
    # Using JSONField to store the entire analysis dictionary from the API
    analysis_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analysis for '{self.product_name}' by {self.user.username}"

    class Meta:
        # Order by most recent first by default
        ordering = ['-created_at']
