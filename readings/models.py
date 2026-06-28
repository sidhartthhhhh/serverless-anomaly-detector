from django.db import models
from django.utils import timezone


class SensorReading(models.Model):
    source = models.CharField(max_length=120, default="simulator")
    metric = models.CharField(max_length=80, default="temperature")
    value = models.FloatField()
    unit = models.CharField(max_length=24, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)
    payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["source", "metric", "recorded_at"]),
            models.Index(fields=["processed_at"]),
        ]
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.source}:{self.metric}={self.value}"


class Prediction(models.Model):
    reading = models.OneToOneField(
        SensorReading,
        on_delete=models.CASCADE,
        related_name="prediction",
    )
    score = models.FloatField()
    is_anomaly = models.BooleanField(default=False)
    model_name = models.CharField(max_length=120, default="isolation_forest")
    explanation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_anomaly", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        status = "anomaly" if self.is_anomaly else "normal"
        return f"{status} score={self.score:.3f}"


class Alert(models.Model):
    CHANNEL_EMAIL = "email"
    CHANNEL_CHOICES = [(CHANNEL_EMAIL, "Email")]

    STATUS_SENT = "sent"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SENT, "Sent"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_FAILED, "Failed"),
    ]

    prediction = models.ForeignKey(
        Prediction,
        on_delete=models.CASCADE,
        related_name="alerts",
    )
    channel = models.CharField(max_length=24, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.channel}:{self.status}"
