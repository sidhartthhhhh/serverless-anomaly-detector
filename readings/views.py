import csv
import io
import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .forms import CsvUploadForm
from .models import Alert, Prediction, SensorReading
from .services import create_reading, process_pending_readings


def dashboard(request):
    recent_predictions = Prediction.objects.select_related("reading")[:50]
    recent_readings = SensorReading.objects.all()[:80]
    since = timezone.now() - timedelta(days=7)

    totals = {
        "readings": SensorReading.objects.count(),
        "predictions": Prediction.objects.count(),
        "anomalies": Prediction.objects.filter(is_anomaly=True).count(),
        "alerts": Alert.objects.count(),
    }
    by_metric = list(
        SensorReading.objects.values("metric")
        .annotate(total=Count("id"))
        .order_by("-total")[:6]
    )

    chart_rows = list(
        Prediction.objects.select_related("reading")
        .filter(created_at__gte=since)
        .order_by("reading__recorded_at")
        .values(
            "reading__recorded_at",
            "reading__value",
            "reading__metric",
            "score",
            "is_anomaly",
        )[:200]
    )

    return render(
        request,
        "readings/dashboard.html",
        {
            "totals": totals,
            "by_metric": by_metric,
            "recent_predictions": recent_predictions,
            "recent_readings": recent_readings,
            "chart_data": [
                {
                    "time": row["reading__recorded_at"].strftime("%m-%d %H:%M"),
                    "value": row["reading__value"],
                    "metric": row["reading__metric"],
                    "score": row["score"],
                    "isAnomaly": row["is_anomaly"],
                }
                for row in chart_rows
            ],
        },
    )


def upload_csv(request):
    form = CsvUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        uploaded = form.cleaned_data["file"]
        text = uploaded.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        created = 0
        errors = []

        for index, row in enumerate(reader, start=2):
            try:
                create_reading(
                    {
                        "source": row.get("source") or "csv",
                        "metric": row.get("metric") or "temperature",
                        "value": row["value"],
                        "unit": row.get("unit", ""),
                        "payload": {"csv_row": index},
                    }
                )
                created += 1
            except Exception as exc:
                errors.append(f"Row {index}: {exc}")

        if created:
            messages.success(request, f"Imported and scored {created} readings.")
        if errors:
            messages.warning(request, " ".join(errors[:3]))
        return redirect("dashboard")

    return render(request, "readings/upload.html", {"form": form})


def simulator(request):
    return render(request, "readings/simulator.html")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def readings_api(request):
    if request.method == "GET":
        readings = SensorReading.objects.select_related("prediction")[:100]
        return JsonResponse(
            {
                "results": [
                    _reading_payload(reading)
                    for reading in readings
                ]
            }
        )

    try:
        data = json.loads(request.body.decode("utf-8"))
        reading, prediction = create_reading(data)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(_reading_payload(reading, prediction), status=201)


@csrf_exempt
@require_POST
def bulk_readings_api(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        rows = data.get("readings", [])
        if not isinstance(rows, list):
            raise ValueError("readings must be a list")
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    created = []
    for row in rows:
        try:
            reading, prediction = create_reading(row)
            created.append(_reading_payload(reading, prediction))
        except Exception as exc:
            created.append({"error": str(exc), "input": row})

    return JsonResponse({"results": created}, status=201)


@csrf_exempt
@require_POST
def process_pending_api(request):
    if settings.PROCESS_TOKEN:
        token = request.headers.get("X-Process-Token") or request.POST.get("token")
        if token != settings.PROCESS_TOKEN:
            return JsonResponse({"error": "Invalid process token."}, status=403)

    result = process_pending_readings()
    return JsonResponse(result)


def _reading_payload(reading, prediction=None):
    prediction = prediction or getattr(reading, "prediction", None)
    payload = {
        "id": reading.id,
        "source": reading.source,
        "metric": reading.metric,
        "value": reading.value,
        "unit": reading.unit,
        "recorded_at": reading.recorded_at.isoformat(),
        "processed_at": reading.processed_at.isoformat() if reading.processed_at else None,
    }
    if prediction:
        payload["prediction"] = {
            "score": prediction.score,
            "is_anomaly": prediction.is_anomaly,
            "model_name": prediction.model_name,
            "explanation": prediction.explanation,
        }
    return payload
