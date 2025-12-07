import json
from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password


def home(request):
    if "user_id" not in request.session:
        return redirect("login")

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, hourly_rate, hours_json
            FROM lot
            ORDER BY name;
        """)
        rows = cursor.fetchall()

    lots = []
    for name, rate, hours_raw in rows:
        try:
            data = json.loads(hours_raw)
        except (TypeError, json.JSONDecodeError):
            data = {}

        # Extract values safely
        lot_info = {
            "name": name,
            "rate": rate,
            "day_rate": data.get("day_rate", "—"),
            "day_window": data.get("day_window", "—"),
            "eve_rate": data.get("eve_rate", data.get("evening_rate", "—")),
            "eve_window": data.get("eve_window", "—"),
            "day_max": data.get("day_max", "—"),
            "day_note": data.get("day_note", "—"),
        }
        lots.append(lot_info)

    return render(request, "core/home.html", {"lots": lots})


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


def signup(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")

        if not all([first_name, last_name, email, phone, password]):
            messages.error(request, "All fields are required.")
            return render(request, "core/signup.html")

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

    return render(request, "core/signup.html")


def logout(request):
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect("login")


def profile(request):
    if "user_id" not in request.session:
        return redirect("login")

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT first_name, last_name, email, phone_usa
            FROM user
            WHERE user_id = %s
        """, [request.session["user_id"]])
        row = cursor.fetchone()

    return render(request, "core/profile.html", {"user": row})


def delete_account(request):
    if "user_id" not in request.session:
        return redirect("login")

    if request.method == 'POST':
        user_id = request.session["user_id"]
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM user WHERE user_id = %s", [user_id])
        request.session.flush()
        messages.success(request, "Account deleted successfully.")
        return redirect("home")

    return redirect("profile")


def change_password(request):
    if "user_id" not in request.session:
        return redirect("login")

    modal_open = False
    new_password_value = ""
    confirm_password_value = ""

    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        modal_open = True
        new_password_value = new_password
        confirm_password_value = confirm_password

        user_id = request.session["user_id"]

        with connection.cursor() as cursor:
            cursor.execute("SELECT password_hash FROM user WHERE user_id = %s", [user_id])
            row = cursor.fetchone()

        if not row:
            messages.error(request, "User not found.")
        elif new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
        elif not check_password(current_password, row[0]):
            messages.error(request, "Current password is incorrect.")
        else:
            new_hash = make_password(new_password)
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE user SET password_hash = %s WHERE user_id = %s",
                    [new_hash, user_id]
                )
            messages.success(request, "Password changed successfully!")
            modal_open = False
            new_password_value = confirm_password_value = ""

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT first_name, last_name, email, phone_usa
            FROM user
            WHERE user_id = %s
        """, [request.session["user_id"]])
        user_row = cursor.fetchone()

    return render(request, "core/profile.html", {
        "user": user_row,
        "modal_open": modal_open,
        "new_password_value": new_password_value,
        "confirm_password_value": confirm_password_value
    })
