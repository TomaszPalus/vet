from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),  # /
    path("clinics/", views.clinics, name="clinics"),
    path("clinics/<int:clinic_id>/slots", views.clinic_slots, name="clinic_slots"),
    path("clinics/<int:clinic_id>/book/preview", views.book_preview, name="book_preview"),
    path("clinics/<int:clinic_id>/book/confirm", views.book_confirm, name="book_confirm"),
    path("appointments/", views.my_appointments, name="my_appointments"),
    path("pets/", views.pets_list, name="pets_list"),
    path("pets/create", views.pets_create, name="pets_create"),
    path("pets/<int:pet_id>/delete", views.pets_delete, name="pets_delete"),
    path("pets/<int:pet_id>/edit", views.pets_edit, name="pets_edit"),
    path("appointments/<int:appt_id>/undo", views.undo_cancel, name="undo_cancel"),
    path("clinic-admin/", views.clinic_dashboard, name="clinic_dashboard"),
    path("clinic-admin/vets/", views.vets_list, name="vets_list"),
    path("clinic-admin/vets/create", views.vet_create, name="vet_create"),
    path("clinic-admin/vets/<int:vet_id>/delete", views.vet_delete, name="vet_delete"),
    path("clinic-admin/hours/", views.hours_list, name="hours_list"),
    path("clinic-admin/hours/set", views.hours_set, name="hours_set"),
    path("clinic-admin/exceptions/", views.exceptions_list, name="exceptions_list"),
    path("clinic-admin/exceptions/toggle", views.exception_toggle, name="exception_toggle"),
    path("clinic-admin/calendar/", views.clinic_calendar, name="clinic_calendar"),
    path("api/health/", views.health, name="health"),
]
