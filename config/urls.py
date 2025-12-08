from django.urls import path
from core import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login, name="login"),
    path('guest-login/', views.guest_login, name='guest_login'),
    path("signup/", views.signup, name="signup"),
    path("logout/", views.logout, name="logout"),
    path("profile/", views.profile, name="profile"),
    path('delete-account/', views.delete_account, name='delete_account'),
    path("change-password/", views.change_password, name="change_password"),
    path("vehicles/", views.vehicles, name="vehicles"),
    path("lot/<int:lot_id>/", views.lot_details, name="lot_details"),
    path("lot/<int:lot_id>/favorite/", views.toggle_favorite, name="toggle_favorite"),
]
