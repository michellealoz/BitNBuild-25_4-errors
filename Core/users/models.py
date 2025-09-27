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

    @property
    def record_type(self):
        return 'analysis'

    def __str__(self):
        return f"Analysis for '{self.product_name}' by {self.user.username}"


    class Meta:
        # Order by most recent first by default
        ordering = ['-created_at']

class ProductComparison(models.Model):
    """
    Stores the result of a two-product comparison for a specific user.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comparisons')
    
    product_url_1 = models.URLField(max_length=1024)
    product_name_1 = models.CharField(max_length=512)
    analysis_data_1 = models.JSONField()

    product_url_2 = models.URLField(max_length=1024)
    product_name_2 = models.CharField(max_length=512)
    analysis_data_2 = models.JSONField()
    
    comparison_metrics = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def record_type(self):
        return 'comparison'

    def __str__(self):
        return f"Comparison of '{self.product_name_1}' vs '{self.product_name_2}' by {self.user.username}"

    class Meta:
        ordering = ['-created_at']
