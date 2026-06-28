from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("upload/", views.upload_csv, name="upload_csv"),
    path("simulator/", views.simulator, name="simulator"),
    path("api/readings/", views.readings_api, name="readings_api"),
    path("api/readings/bulk/", views.bulk_readings_api, name="bulk_readings_api"),
    path("api/process-pending/", views.process_pending_api, name="process_pending_api"),
]
