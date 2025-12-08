from django.db import models

# Create your models here.
from django.db import models

class Lot(models.Model):
    lot_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    capacity_int = models.IntegerField(blank=True, null=True)
    hourly_rate = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    hours_json = models.TextField(blank=True, null=True)

    class Meta:
        managed = False          # IMPORTANT: Django will NOT create or migrate this table
        db_table = 'lot'         # must match your actual table name

    def __str__(self):
        return self.name

