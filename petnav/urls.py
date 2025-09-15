from django.contrib import admin
from django.urls import path, include
from core import views as v

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("login/", v.login_view, name="login"),
    path("signup/", v.signup, name="signup"),
    path("logout/", v.logout_view, name="logout"),
]
