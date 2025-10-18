# Scout/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("paper/<str:paper_id>/", views.paper_detail, name="paper_detail"),
  

]
