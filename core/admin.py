from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Lot

@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = ("lot_id", "name", "capacity_int", "hourly_rate")
    search_fields = ("name",)
