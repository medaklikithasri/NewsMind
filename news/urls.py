from django.urls import path
from . import views
urlpatterns = [
    path('', views.home, name='home'),
    path('summarize-article/', views.summarize_article, name='summarize_article'),
]
