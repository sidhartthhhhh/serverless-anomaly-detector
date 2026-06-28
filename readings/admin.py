from django.contrib import admin

from .models import Alert, Prediction, SensorReading


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    list_display = ("source", "metric", "value", "unit", "recorded_at", "processed_at")
    list_filter = ("source", "metric")
    search_fields = ("source", "metric")


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("reading", "score", "is_anomaly", "model_name", "created_at")
    list_filter = ("is_anomaly", "model_name")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("channel", "status", "prediction", "created_at")
    list_filter = ("channel", "status")
