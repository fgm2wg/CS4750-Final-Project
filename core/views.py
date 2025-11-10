from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password


def home(request):
    if "user_id" not in request.session:
        return redirect("login")

    return render(request, "core/home.html")


def login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        with connection.cursor() as cursor:
            cursor.execute("SELECT user_id, password_hash FROM user WHERE email = %s", [email])
            row = cursor.fetchone()

        if row:
            user_id, password_hash = row

            if check_password(password, password_hash):
                request.session["user_id"] = user_id
                messages.success(request, "Login successful.")
                return redirect("home")
            else:
                messages.error(request, "Invalid password.")
        else:
            messages.error(request, "Email not found.")

    return render(request, "core/login.html")


def sign_up(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")

        if not all([first_name, last_name, email, phone, password]):
            messages.error(request, "All fields are required.")
            return render(request, "core/sign_up.html")

        password_hash = make_password(password)

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO user (first_name, last_name, email, phone_usa, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                """, [first_name, last_name, email, phone, password_hash])

            messages.success(request, "Account created successfully! Please login.")
            return redirect("login")

        except Exception as e:
            if "Duplicate entry" in str(e):
                messages.error(request, "Email already registered.")
            else:
                messages.error(request, f"Error creating account: {e}")

    return render(request, "core/sign_up.html")


def logout(request):
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect("login")
