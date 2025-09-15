from django.db import models
from django.contrib.auth.models import User as DjangoUser

class Clinic(models.Model):
    name=models.CharField(max_length=120); city=models.CharField(max_length=80, blank=True)
    address=models.CharField(max_length=200, blank=True)
    def __str__(self): return self.name

class User(models.Model):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=(('OWNER','OWNER'),('VET','VET'),('CLINIC_ADMIN','CLINIC_ADMIN')), default='OWNER')
    auth_user = models.OneToOneField(DjangoUser, on_delete=models.CASCADE, null=True, blank=True, related_name="profile")  # ⬅️ NOWE

class Vet(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE); clinic=models.ForeignKey(Clinic,on_delete=models.CASCADE)
    title=models.CharField(max_length=80, blank=True)

class Pet(models.Model):
    owner=models.ForeignKey(User,on_delete=models.CASCADE); name=models.CharField(max_length=80); species=models.CharField(max_length=40)

class Appointment(models.Model):
    STATUS=(('NEW','NEW'),('CONFIRMED','CONFIRMED'),('CANCELLED','CANCELLED'))
    clinic=models.ForeignKey(Clinic,on_delete=models.CASCADE)
    vet=models.ForeignKey(Vet,on_delete=models.CASCADE)
    owner=models.ForeignKey(User,on_delete=models.CASCADE)
    pet=models.ForeignKey(Pet,on_delete=models.CASCADE)
    starts_at=models.DateTimeField(); ends_at=models.DateTimeField()
    status=models.CharField(max_length=12,choices=STATUS,default='NEW')

# Godziny pracy i wyjątki

class ClinicHours(models.Model):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="hours")
    weekday = models.IntegerField()  # 0=pon ... 6=niedz
    start = models.CharField(max_length=5)  # "09:00"
    end   = models.CharField(max_length=5)  # "17:00"

    class Meta:
        unique_together = ("clinic", "weekday", "start", "end")
        ordering = ("clinic_id","weekday","start")

class VetHours(models.Model):
    vet = models.ForeignKey(Vet, on_delete=models.CASCADE, related_name="hours")
    weekday = models.IntegerField()
    start = models.CharField(max_length=5)
    end   = models.CharField(max_length=5)

    class Meta:
        unique_together = ("vet", "weekday", "start", "end")
        ordering = ("vet_id","weekday","start")

class AvailabilityException(models.Model):
    """
    Wyjątki: zamknięte całkiem albo okno godzin inne niż standard.
    Jeśli closed=1 – ignorujemy start/end. Entity: "CLINIC" lub "VET".
    """
    entity_type = models.CharField(max_length=10)  # CLINIC | VET
    entity_id   = models.IntegerField()
    date        = models.DateField()
    closed      = models.BooleanField(default=False)
    start = models.CharField(max_length=5, blank=True, null=True)  # "10:00"
    end   = models.CharField(max_length=5, blank=True, null=True)

    class Meta:
        unique_together = ("entity_type","entity_id","date")
        indexes = [models.Index(fields=["entity_type","entity_id","date"])]
