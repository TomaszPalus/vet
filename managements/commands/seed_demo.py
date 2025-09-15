from django.core.management.base import BaseCommand
from core.models import User, Clinic, Vet, Pet, ClinicHours, VetHours, AvailabilityException
class Command(BaseCommand):
  def handle(self,*a,**k):
    owner,_=User.objects.get_or_create(email="owner@demo.io",defaults={"role":"OWNER"})
    vet_u,_=User.objects.get_or_create(email="vet@demo.io",defaults={"role":"VET"})
    c1,_=Clinic.objects.get_or_create(name="Vet Premium Wrocław",city="Wrocław",address="ul. Kocia 1")
    c2,_=Clinic.objects.get_or_create(name="AnimalCare Kraków",city="Kraków",address="ul. Psia 2")
    Vet.objects.get_or_create(user=vet_u, clinic=c1, defaults={"title":"lek. wet."})
    Pet.objects.get_or_create(owner=owner, name="Rex", species="dog")
    self.stdout.write(self.style.SUCCESS("Seed OK"))

# Godziny kliniki c1: pn-pt 09-17
for wd in range(0,5):
    ClinicHours.objects.get_or_create(clinic=c1, weekday=wd, start="09:00", end="17:00")

# Wet ma swoje godziny (opcjonalnie – nadpisują klinikę)
v1 = Vet.objects.filter(clinic=c1).first()
if v1:
    for wd in (0,2,4):  # pon, śr, pt 10-16
        VetHours.objects.get_or_create(vet=v1, weekday=wd, start="10:00", end="16:00")
