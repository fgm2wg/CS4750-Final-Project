from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("db-info/", views.db_info, name="db_info"),
]
