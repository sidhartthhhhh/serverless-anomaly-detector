from dataclasses import dataclass
from statistics import mean, pstdev

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Alert, Prediction, SensorReading


@dataclass
class DetectionResult:
    score: float
    is_anomaly: bool
    explanation: str
    model_name: str


def create_reading(data):
    reading = SensorReading.objects.create(
        source=data.get("source") or "api",
        metric=data.get("metric") or "temperature",
        value=float(data["value"]),
        unit=data.get("unit", ""),
        recorded_at=data.get("recorded_at") or timezone.now(),
        payload=data.get("payload") or {},
    )
    return analyze_reading(reading)


def analyze_reading(reading):
    with transaction.atomic():
        result = detect_anomaly(reading)
        prediction, _created = Prediction.objects.update_or_create(
            reading=reading,
            defaults={
                "score": result.score,
                "is_anomaly": result.is_anomaly,
                "model_name": result.model_name,
                "explanation": result.explanation,
            },
        )
        reading.processed_at = timezone.now()
        reading.save(update_fields=["processed_at"])

    if prediction.is_anomaly:
        send_anomaly_alert(prediction)

    return reading, prediction


def detect_anomaly(reading):
    values = list(
        SensorReading.objects.filter(
            source=reading.source,
            metric=reading.metric,
            recorded_at__lte=reading.recorded_at,
        )
        .order_by("-recorded_at")
        .values_list("value", flat=True)[:120]
    )
    values.reverse()

    if len(values) < settings.ANOMALY_MIN_SAMPLES:
        return _z_score_detection(reading.value, values)

    try:
        from sklearn.ensemble import IsolationForest

        model = IsolationForest(
            contamination=settings.ANOMALY_CONTAMINATION,
            random_state=42,
        )
        matrix = [[value] for value in values]
        labels = model.fit_predict(matrix)
        scores = model.decision_function(matrix)
        score = float(scores[-1])
        is_anomaly = labels[-1] == -1
        explanation = (
            "Isolation Forest compared this reading with the recent metric window."
        )
        return DetectionResult(score, is_anomaly, explanation, "isolation_forest")
    except Exception:
        return _z_score_detection(reading.value, values)


def _z_score_detection(value, values):
    if len(values) < 3:
        return DetectionResult(
            0.0,
            False,
            "Waiting for more readings before anomaly scoring becomes meaningful.",
            "warmup_z_score",
        )

    baseline = mean(values[:-1] or values)
    deviation = pstdev(values[:-1] or values) or 1.0
    z_score = abs((value - baseline) / deviation)
    is_anomaly = z_score >= 3.0
    return DetectionResult(
        round(z_score, 4),
        is_anomaly,
        f"Fallback z-score detector compared value against baseline {baseline:.2f}.",
        "fallback_z_score",
    )


def process_pending_readings(limit=200):
    pending = SensorReading.objects.filter(processed_at__isnull=True).order_by(
        "recorded_at"
    )[:limit]
    processed = 0
    anomalies = 0

    for reading in pending:
        _reading, prediction = analyze_reading(reading)
        processed += 1
        if prediction.is_anomaly:
            anomalies += 1

    return {"processed": processed, "anomalies": anomalies}


def send_anomaly_alert(prediction):
    if prediction.alerts.exists():
        return

    reading = prediction.reading
    subject = f"Anomaly detected: {reading.source} {reading.metric}"
    message = (
        f"Anomaly detected for {reading.source}/{reading.metric}\n"
        f"Value: {reading.value} {reading.unit}\n"
        f"Score: {prediction.score}\n"
        f"Recorded at: {reading.recorded_at.isoformat()}\n"
        f"Explanation: {prediction.explanation}"
    )

    recipient = settings.ALERT_RECIPIENT_EMAIL
    if not recipient:
        Alert.objects.create(
            prediction=prediction,
            channel=Alert.CHANNEL_EMAIL,
            status=Alert.STATUS_SKIPPED,
            message="No ALERT_RECIPIENT_EMAIL configured.",
        )
        return

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
        status = Alert.STATUS_SENT
    except Exception as exc:
        status = Alert.STATUS_FAILED
        message = f"{message}\n\nEmail error: {exc}"

    Alert.objects.create(
        prediction=prediction,
        channel=Alert.CHANNEL_EMAIL,
        status=status,
        message=message,
    )
