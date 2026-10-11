from django.db import models
class CachedArticle(models.Model):
    headline = models.CharField(max_length=500)
    source = models.CharField(max_length=200)
    original_url = models.URLField()
    ai_summary = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, default='general')
    fetched_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.headline
