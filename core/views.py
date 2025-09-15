# core/views.py
from datetime import datetime, time as dtime, timedelta, date as ddate
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User as DjangoUser
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import make_aware
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods, require_GET

from .models import (
    Appointment, Clinic, Pet, User as DomainUser, Vet,
    ClinicHours, VetHours, AvailabilityException
)

# ───────────────────────────────────────────────────────────────────────────────
# Healthcheck (do monitoringu/stagingu)
# ───────────────────────────────────────────────────────────────────────────────

@require_GET
def health(_request):
    return JsonResponse({"ok": True})

# ───────────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────────

def _owner_for_request(request):
    if not request.user.is_authenticated:
        return None
    # znajdź lub utwórz DomainUser powiązany z Django userem
    du, _ = DomainUser.objects.get_or_create(auth_user=request.user, defaults={
        "email": request.user.username, "role": "OWNER"
    })
    return du

def _overlaps(a_start, a_end, b_start, b_end):
    """Czy przedziały [a_start, a_end) i [b_start, b_end) się nakładają?"""
    return a_start < b_end and b_start < a_end

# ───────────────────────────────────────────────────────────────────────────────
# Public / Landing
# ───────────────────────────────────────────────────────────────────────────────

def home(request):
    return render(
        request,
        "home.html",
        {"clinics": Clinic.objects.all().order_by("city", "name")}
    )

# ───────────────────────────────────────────────────────────────────────────────
# Auth (Django sessions)
# ───────────────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.method == "POST":
        u = request.POST.get("username")
        p = request.POST.get("password")
        user = authenticate(request, username=u, password=p)
        if user:
            login(request, user)
            return redirect("clinics")
        messages.error(request, "Błędne dane logowania")
    return render(request, "auth/login.html")

def signup(request):
    if request.method == "POST":
        u = request.POST.get("username")
        p = request.POST.get("password")

        if not u or not p:
            messages.error(request, "Podaj login i hasło")
        elif DjangoUser.objects.filter(username=u).exists():
            messages.error(request, "Użytkownik już istnieje")
        else:
            # 1. Tworzymy konto Django
            user = DjangoUser.objects.create_user(username=u, password=p)
            # 2. Tworzymy DomainUser powiązany z kontem Django
            DomainUser.objects.get_or_create(
                auth_user=user,
                defaults={"email": u, "role": "OWNER"}
            )
            # 3. Automatycznie logujemy
            login(request, user)
            return redirect("clinics")

    return render(request, "auth/signup.html")

def logout_view(request):
    logout(request)
    return redirect("home")

# ───────────────────────────────────────────────────────────────────────────────
# Clinics / Slots / Booking
# ───────────────────────────────────────────────────────────────────────────────

def clinics(request):
    return render(request, "clinics.html", {
        "clinics": Clinic.objects.all(),
        "now": timezone.localdate()
    })

def _hhmm_to_time(hhmm: str) -> dtime:
    h, m = map(int, hhmm.split(":"))
    return dtime(hour=h, minute=m)

def _range_to_slots(day: ddate, start_str: str, end_str: str, step_min: int = 30):
    start_t = _hhmm_to_time(start_str)
    end_t   = _hhmm_to_time(end_str)
    start_dt = make_aware(datetime.combine(day, start_t))
    end_dt   = make_aware(datetime.combine(day, end_t))
    t = start_dt
    while t < end_dt:
        yield (t, t + timedelta(minutes=step_min))
        t += timedelta(minutes=step_min)

def clinic_slots(request, clinic_id: int):
    """
    Generuje wolne sloty dla kliniki w danym dniu:
    - precedence: VetHours > ClinicHours
    - wyjątki: AvailabilityException (CLINIC/VET). Jeśli closed — brak slotów.
    - kolizje z Appointment != CANCELLED odfiltrowują sloty (po nakładaniu).
    Param: ?date=YYYY-MM-DD (domyślnie dzisiaj).
    """
    clinic = get_object_or_404(Clinic, pk=clinic_id)

    # Data
    try:
        day_str = request.GET.get("date")
        day = datetime.strptime(day_str, "%Y-%m-%d").date() if day_str else timezone.localdate()
    except Exception:
        day = timezone.localdate()
    weekday = day.weekday()  # 0=Mon

    # Czy klinika zamknięta (wyjątek)?
    ex_clinic = AvailabilityException.objects.filter(
        entity_type="CLINIC", entity_id=clinic.id, date=day
    ).first()
    if ex_clinic and ex_clinic.closed:
        return render(request, "partials/slots.html", {"clinic": clinic, "slots": []})

    # Godziny kliniki (fallback, gdy vet nie ma własnych)
    clinic_hours = list(ClinicHours.objects.filter(clinic=clinic, weekday=weekday))

    # Weterynarze w klinice
    vets = list(Vet.objects.filter(clinic=clinic))
    slots = []

    # Oś dnia
    day_start = make_aware(datetime.combine(day, dtime(0, 0)))
    day_end   = make_aware(datetime.combine(day, dtime(23, 59)))

    # Pobierz istniejące wizyty (na kolizje) — zakresowe, nie równościowe
    busy = list(Appointment.objects.filter(
        clinic=clinic,
        starts_at__lt=day_end,
        ends_at__gt=day_start
    ).exclude(status="CANCELLED").values_list("vet_id", "starts_at", "ends_at"))

    busy_by_vet = {}
    for vid, bs, be in busy:
        busy_by_vet.setdefault(vid, []).append((bs, be))

    for v in vets:
        # Wyjątek veta
        ex_vet = AvailabilityException.objects.filter(
            entity_type="VET", entity_id=v.id, date=day
        ).first()
        if ex_vet and ex_vet.closed:
            continue

        # Godziny veta (jeśli są, mają pierwszeństwo), inaczej kliniki
        v_hours = list(VetHours.objects.filter(vet=v, weekday=weekday))
        base_hours = v_hours if v_hours else clinic_hours

        # Jeśli wyjątek veta z oknem godzin (nie closed): nadpisz bazę jednym oknem
        if ex_vet and not ex_vet.closed and ex_vet.start and ex_vet.end:
            base_hours = [type("X", (object,), {"start": ex_vet.start, "end": ex_vet.end})()]

        # Jeśli wyjątek kliniki z oknem (np. skrócone godziny) – przycięcie
        if ex_clinic and not ex_clinic.closed and ex_clinic.start and ex_clinic.end:
            ch_start, ch_end = ex_clinic.start, ex_clinic.end
        else:
            ch_start = ch_end = None

        for h in base_hours:
            start_s, end_s = h.start, h.end
            if ch_start and ch_end:
                # przytnij okno do zakresu kliniki
                start_s = max(start_s, ch_start)
                end_s   = min(end_s, ch_end)
                if start_s >= end_s:
                    continue

            for s, e in _range_to_slots(day, start_s, end_s, 30):
                # kolizje zakresowe
                collisions = any(_overlaps(s, e, bs, be) for (bs, be) in busy_by_vet.get(v.id, []))
                if not collisions:
                    slots.append((s, e))

    # posortuj i wyślij
    slots.sort(key=lambda x: x[0])
    return render(request, "partials/slots.html", {"clinic": clinic, "slots": slots})

def book_preview(request, clinic_id: int):
    clinic = get_object_or_404(Clinic, pk=clinic_id)
    owner = _owner_for_request(request)
    pets = Pet.objects.filter(owner=owner) if owner else []
    return render(request, "partials/book_preview.html", {
        "clinic": clinic,
        "start": request.GET.get("start"),
        "end": request.GET.get("end"),
        "pets": pets,
    })

@login_required
def book_confirm(request, clinic_id: int):
    clinic = get_object_or_404(Clinic, pk=clinic_id)
    vet = Vet.objects.filter(clinic=clinic).first()
    owner = _owner_for_request(request)

    pet_id = request.POST.get("pet_id")
    start_s = request.POST.get("start")
    end_s   = request.POST.get("end")

    if not all([vet, owner, pet_id, start_s, end_s]):
        return JsonResponse({"ok": False, "msg": "Brak danych"}, status=400)

    # ISO → datetime → aware
    start_dt = parse_datetime(start_s)
    end_dt   = parse_datetime(end_s)
    if not start_dt or not end_dt:
        return JsonResponse({"ok": False, "msg": "Zły format daty"}, status=400)
    if timezone.is_naive(start_dt): start_dt = make_aware(start_dt)
    if timezone.is_naive(end_dt):   end_dt   = make_aware(end_dt)

    Appointment.objects.create(
        clinic=clinic, vet=vet, owner=owner, pet_id=pet_id,
        starts_at=start_dt, ends_at=end_dt, status="NEW"
    )
    return render(request, "partials/toast_success.html", {"msg": "Zarezerwowano!"})

# ───────────────────────────────────────────────────────────────────────────────
# Owner Portal
# ───────────────────────────────────────────────────────────────────────────────

@login_required
def my_appointments(request):
    owner = _owner_for_request(request)
    appts = Appointment.objects.filter(owner=owner).order_by("starts_at") if owner else []
    return render(request, "appointments.html", {"appts": appts})

@login_required
def cancel_appointment(request, appt_id: int):
    """Proste anulowanie (POST). Zwraca toast dla HTMX."""
    appt = get_object_or_404(Appointment, pk=appt_id)
    appt.status = "CANCELLED"
    appt.save(update_fields=["status"])
    return render(request, "partials/toast_success.html", {"msg": "Anulowano wizytę"})

@login_required
def pets_list(request):
    owner = _owner_for_request(request)
    pets = Pet.objects.filter(owner=owner)
    return render(request, "pets/list.html", {"pets": pets})

@login_required
@require_http_methods(["POST"])
def pets_create(request):
    owner = _owner_for_request(request)
    name = request.POST.get("name")
    species = request.POST.get("species")
    if not name or not species:
        return render(request, "partials/toast_success.html", {"msg": "Podaj imię i gatunek"})
    Pet.objects.create(owner=owner, name=name, species=species)
    return render(request, "partials/toast_success.html", {"msg": "Dodano pupila"})

@login_required
@require_http_methods(["POST"])
def pets_delete(request, pet_id: int):
    owner = _owner_for_request(request)
    p = get_object_or_404(Pet, pk=pet_id, owner=owner)
    p.delete()
    return render(request, "partials/toast_success.html", {"msg": "Usunięto pupila"})

@login_required
@require_http_methods(["POST"])
def pets_edit(request, pet_id: int):
    owner = _owner_for_request(request)
    p = get_object_or_404(Pet, pk=pet_id, owner=owner)
    p.name = request.POST.get("name") or p.name
    p.species = request.POST.get("species") or p.species
    p.save(update_fields=["name", "species"])
    return render(request, "partials/toast_success.html", {"msg": "Zaktualizowano pupila"})

@login_required
@require_http_methods(["POST"])
def undo_cancel(request, appt_id: int):
    owner = _owner_for_request(request)
    a = get_object_or_404(Appointment, pk=appt_id, owner=owner)
    if a.status == "CANCELLED":
        a.status = "NEW"
        a.save(update_fields=["status"])
        return render(request, "partials/toast_success.html", {"msg": "Przywrócono wizytę"})
    return render(request, "partials/toast_success.html", {"msg": "Nie można przywrócić"})

# ───────────────────────────────────────────────────────────────────────────────
# Clinic Admin (MVP)
# ───────────────────────────────────────────────────────────────────────────────

def _is_clinic_admin(user):
    # Sprawdzenie roli w DomainUser
    try:
        return DomainUser.objects.filter(auth_user=user, role="CLINIC_ADMIN").exists()
    except Exception:
        return False

def _clinic_for_admin(_user):
    # MVP: pierwszy clinic w systemie; docelowo relacja admin->clinic
    return Clinic.objects.first()

@login_required
@user_passes_test(_is_clinic_admin)
def clinic_dashboard(request):
    c = _clinic_for_admin(request.user)
    vets = Vet.objects.filter(clinic=c).count()
    hrs = ClinicHours.objects.filter(clinic=c).count()
    appts = Appointment.objects.filter(clinic=c).count()
    return render(request, "clinic_admin/dashboard.html", {"clinic": c, "vets": vets, "hrs": hrs, "appts": appts})

@login_required
@user_passes_test(_is_clinic_admin)
def vets_list(request):
    c = _clinic_for_admin(request.user)
    return render(request, "clinic_admin/vets.html", {"clinic": c, "vets": Vet.objects.filter(clinic=c)})

@login_required
@user_passes_test(_is_clinic_admin)
@require_http_methods(["POST"])
def vet_create(request):
    c = _clinic_for_admin(request.user)
    email = request.POST.get("email")
    title = request.POST.get("title", "")
    if not email:
        return render(request, "partials/toast_success.html", {"msg": "Podaj e-mail veta"})
    du, _ = DomainUser.objects.get_or_create(email=email, defaults={"role": "VET"})
    Vet.objects.create(user=du, clinic=c, title=title)
    return render(request, "partials/toast_success.html", {"msg": "Dodano veta"})

@login_required
@user_passes_test(_is_clinic_admin)
@require_http_methods(["POST"])
def vet_delete(request, vet_id: int):
    c = _clinic_for_admin(request.user)
    get_object_or_404(Vet, id=vet_id, clinic=c).delete()
    return render(request, "partials/toast_success.html", {"msg": "Usunięto veta"})

@login_required
@user_passes_test(_is_clinic_admin)
def hours_list(request):
    c = _clinic_for_admin(request.user)
    return render(request, "clinic_admin/hours.html", {
        "clinic": c,
        "hours": ClinicHours.objects.filter(clinic=c).order_by("weekday", "start")
    })

@login_required
@user_passes_test(_is_clinic_admin)
@require_http_methods(["POST"])
def hours_set(request):
    c = _clinic_for_admin(request.user)
    try:
        wd = int(request.POST.get("weekday"))
    except (TypeError, ValueError):
        wd = -1
    start = request.POST.get("start")
    end = request.POST.get("end")
    if not (0 <= wd <= 6 and start and end):
        return render(request, "partials/toast_success.html", {"msg": "Błędne dane"})
    ClinicHours.objects.get_or_create(clinic=c, weekday=wd, start=start, end=end)
    return render(request, "partials/toast_success.html", {"msg": "Zapisano godziny"})

@login_required
@user_passes_test(_is_clinic_admin)
def exceptions_list(request):
    c = _clinic_for_admin(request.user)
    ex = AvailabilityException.objects.filter(entity_type="CLINIC", entity_id=c.id).order_by("-date")[:30]
    return render(request, "clinic_admin/exceptions.html", {"clinic": c, "exceptions": ex})

@login_required
@user_passes_test(_is_clinic_admin)
@require_http_methods(["POST"])
def exception_toggle(request):
    c = _clinic_for_admin(request.user)
    date_str = request.POST.get("date")
    closed = request.POST.get("closed") == "1"
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    obj, _ = AvailabilityException.objects.get_or_create(entity_type="CLINIC", entity_id=c.id, date=d)
    obj.closed = closed
    obj.save(update_fields=["closed"])
    return render(request, "partials/toast_success.html", {"msg": "Zaktualizowano wyjątek"})

@login_required
@user_passes_test(_is_clinic_admin)
def clinic_calendar(request):
    c = _clinic_for_admin(request.user)
    day = request.GET.get("date") or timezone.localdate().isoformat()
    start = timezone.make_aware(datetime.strptime(day, "%Y-%m-%d"))
    end = start + timedelta(days=1)
    appts = Appointment.objects.filter(clinic=c, starts_at__gte=start, starts_at__lt=end).order_by("starts_at")
    return render(request, "clinic_admin/calendar.html", {"clinic": c, "day": day, "appts": appts})
