from django.contrib import admin
from .models import Clinic, Vet, Pet, Appointment, ClinicHours, VetHours, AvailabilityException, User as DomainUser

@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("id","name","city","address")

@admin.register(Vet)
class VetAdmin(admin.ModelAdmin):
    list_display = ("id","clinic","title","user")

@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ("id","name","species","owner")

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id","clinic","vet","owner","pet","starts_at","status")
    list_filter = ("status","clinic","vet")

@admin.register(ClinicHours)
class ClinicHoursAdmin(admin.ModelAdmin):
    list_display = ("clinic","weekday","start","end")
    list_filter = ("clinic","weekday")

@admin.register(VetHours)
class VetHoursAdmin(admin.ModelAdmin):
    list_display = ("vet","weekday","start","end")
    list_filter = ("vet","weekday")

@admin.register(AvailabilityException)
class AvailabilityExceptionAdmin(admin.ModelAdmin):
    list_display = ("entity_type","entity_id","date","closed","start","end")
    list_filter = ("entity_type","closed","date")

@admin.register(DomainUser)
class DomainUserAdmin(admin.ModelAdmin):
    list_display = ("id","email","role")
