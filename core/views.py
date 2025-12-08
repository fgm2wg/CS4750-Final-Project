import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import connection, transaction
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
import uuid


def home(request):
    if "user_id" not in request.session:
        return redirect("login")

    search = request.GET.get("search", "").strip().lower()
    show_fav = request.GET.get("favorites") == "1"
    user_id = request.session["user_id"]

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT l.lot_id, l.name, l.hourly_rate, l.hours_json, l.capacity_int,
                   z.name AS zone_name
            FROM lot l
            JOIN zone z ON l.zone_id = z.zone_id
            ORDER BY l.name;
        """)
        rows = cursor.fetchall()

    favorites = set()
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT lot_id FROM favorite WHERE user_id=%s
        """, [user_id])
        favorites = {row[0] for row in cursor.fetchall()}

    lots = []
    for lot_id, name, rate, hours_raw, capacity, zone_name in rows:
        try:
            data = json.loads(hours_raw) if hours_raw else {}
        except json.JSONDecodeError:
            data = {}

        lot = {
            "id": lot_id,
            "name": name,
            "zone": zone_name,
            "rate": data.get("day_rate", float(rate)),
            "eve_rate": data.get("eve_rate", float(rate)),
            "day_window": data.get("day_window", "07:30-17:00"),
            "capacity": capacity,
            "favorite": lot_id in favorites,
        }

        lots.append(lot)

    if search:
        lots = [l for l in lots if search in l["name"].lower()]

    if show_fav:
        lots = [l for l in lots if l["favorite"]]

    return render(request, "core/home.html", {
        "lots": lots,
        "show_fav": show_fav,
    })


def lot_details(request, lot_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT l.name, z.name AS zone_name, l.hourly_rate,
                   l.hours_json, l.capacity_int
            FROM lot l
            JOIN zone z ON l.zone_id = z.zone_id
            WHERE l.lot_id = %s
        """, [lot_id])
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Lot not found.")
        return redirect("home")

    name, zone, rate, hours_raw, capacity = row

    try:
        data = json.loads(hours_raw) if hours_raw else {}
    except:
        data = {}

    is_favorite = False
    if "user_id" in request.session:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM favorite
                WHERE user_id=%s AND lot_id=%s
                LIMIT 1
            """, [request.session["user_id"], lot_id])
            is_favorite = cursor.fetchone() is not None

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT reported_at, fill_pct_int
            FROM occupancy_report
            WHERE lot_id=%s
            ORDER BY reported_at DESC
            LIMIT 10
        """, [lot_id])
        trend = cursor.fetchall()

        cursor.execute("""
            SELECT note
            FROM lot_note
            WHERE lot_id=%s
        """, [lot_id])
        reports = cursor.fetchall()

    return render(request, "core/lot_details.html", {
        "lot": {
            "id": lot_id,
            "name": name,
            "zone": zone,
            "rate": data.get("day_rate", rate),
            "eve_rate": data.get("eve_rate", rate),
            "day_window": data.get("day_window", "07:30-17:00"),
            "capacity": capacity,
        },
        "trend": trend,
        "reports": reports,
        "is_favorite": is_favorite
    })


def toggle_favorite(request, lot_id):
    if "user_id" not in request.session:
        return JsonResponse({"error": "Not logged in"}, status=403)

    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    user_id = request.session["user_id"]

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT favorite_id FROM favorite
                WHERE user_id=%s AND lot_id=%s
            """, [user_id, lot_id])
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    DELETE FROM favorite
                    WHERE user_id=%s AND lot_id=%s
                """, [user_id, lot_id])
                transaction.commit()
                return JsonResponse({"favorited": False})

            else:
                cursor.execute("""
                    INSERT INTO favorite (user_id, lot_id)
                    VALUES (%s, %s)
                """, [user_id, lot_id])
                transaction.commit()
                return JsonResponse({"favorited": True})

    except Exception as e:
        print("TOGGLE FAVORITE ERROR:", e)
        return JsonResponse({"error": str(e)}, status=500)


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
                request.session["user_role"] = "REGISTERED"
                messages.success(request, "Login successful.")
                return redirect("home")
            else:
                messages.error(request, "Invalid password.")
        else:
            messages.error(request, "Email not found.")
    return render(request, "core/login.html")


def guest_login(request):
    request.session.flush()

    random_suffix = str(uuid.uuid4())[:8]
    guest_email = f"guest_{random_suffix}@guest.local"
    guest_phone = "0000000000"

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO user (first_name, last_name, email, phone_usa, password_hash)
                VALUES (%s, %s, %s, %s, %s)
            """, ["Guest", f"Visitor{random_suffix}", guest_email, guest_phone, "GUEST"])

            new_user_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO visitor (user_id, affiliation_note)
                VALUES (%s, %s)
            """, [new_user_id, "Guest access – not a UVA-affiliated account"])

        request.session["user_id"] = new_user_id
        request.session["user_role"] = "VISITOR"

        messages.success(request, "You are logged in as a guest.")
        return redirect("home")

    except Exception as e:
        messages.error(request, f"Guest login failed: {e}")
        return redirect("login")


def signup(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        password = request.POST.get("password")
        role = request.POST.get("role")

        if not all([first_name, last_name, email, phone, password, role]):
            messages.error(request, "All fields including role are required.")
            return render(request, "core/signup.html")

        password_hash = make_password(password)

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO user (first_name, last_name, email, phone_usa, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                """, [first_name, last_name, email, phone, password_hash])
                user_id = cursor.lastrowid

                if role == "STUDENT":
                    uva_id = request.POST.get("uva_student_id")
                    level = request.POST.get("level")
                    school = request.POST.get("school")
                    cursor.execute("""
                        INSERT INTO student(user_id, uva_student_id, level, school)
                        VALUES (%s, %s, %s, %s)
                    """, [user_id, uva_id, level, school])
                elif role == "EMPLOYEE":
                    emp_id = request.POST.get("employee_id")
                    dept = request.POST.get("department")
                    title = request.POST.get("title")
                    cursor.execute("""
                        INSERT INTO employee(user_id, employee_id, department, title)
                        VALUES (%s, %s, %s, %s)
                    """, [user_id, emp_id, dept, title])

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
            SELECT u.first_name, u.last_name, u.email, u.phone_usa,
                   s.uva_student_id, s.level, s.school,
                   e.employee_id, e.department, e.title,
                   v.affiliation_note
            FROM user u
            LEFT JOIN student s ON u.user_id = s.user_id
            LEFT JOIN employee e ON u.user_id = e.user_id
            LEFT JOIN visitor v ON u.user_id = v.user_id
            WHERE u.user_id = %s
        """, [request.session["user_id"]])
        user_row = cursor.fetchone()

    if not user_row:
        messages.error(request, "User not found.")
        return redirect("login")

    role = "Student" if user_row[4] else "Employee" if user_row[7] else "Visitor"

    return render(request, "core/profile.html", {
        "user": user_row,
        "role": role,
        "modal_open": False,
        "new_password_value": "",
        "confirm_password_value": ""
    })


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


def vehicles(request):
    if "user_id" not in request.session:
        return redirect("login")

    modal_open = None
    vehicle_to_edit = None

    if request.method == "POST":
        action = request.POST.get("action")
        plate = request.POST.get("plate", "").upper()
        state = request.POST.get("state", "").upper()
        make = request.POST.get("make")
        model = request.POST.get("model")
        color = request.POST.get("color")
        nickname = request.POST.get("nickname")
        vehicle_id = request.POST.get("vehicle_id")

        try:
            with connection.cursor() as cursor:
                if action == "add":
                    if not plate or not state:
                        messages.error(request, "Plate and state are required.")
                        modal_open = "add"
                    else:
                        cursor.execute("""
                            INSERT INTO vehicle (user_id, plate, state, make, model, color, nickname)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                        """, [request.session["user_id"], plate, state, make, model, color, nickname])
                        messages.success(request, "Vehicle added successfully.")

                elif action == "edit":
                    if not plate or not state:
                        messages.error(request, "Plate and state are required.")
                        modal_open = "edit"
                        vehicle_to_edit = (vehicle_id, plate, state, make, model, color, nickname)
                    else:
                        cursor.execute("""
                            UPDATE vehicle
                            SET plate=%s, state=%s, make=%s, model=%s, color=%s, nickname=%s
                            WHERE vehicle_id=%s AND user_id=%s
                        """, [plate, state, make, model, color, nickname, vehicle_id, request.session["user_id"]])
                        messages.success(request, "Vehicle updated successfully.")

                elif action == "delete":
                    cursor.execute("""
                        DELETE FROM vehicle WHERE vehicle_id=%s AND user_id=%s
                    """, [vehicle_id, request.session["user_id"]])
                    messages.success(request, "Vehicle deleted successfully.")
        except Exception as e:
            if "Duplicate entry" in str(e):
                messages.error(request, "A vehicle with this plate and state already exists.")
                if action in ("add", "edit"):
                    modal_open = action
                    if action == "edit":
                        vehicle_to_edit = (vehicle_id, plate, state, make, model, color, nickname)
            else:
                messages.error(request, f"Error: {e}")
                if action in ("add", "edit"):
                    modal_open = action
                    if action == "edit":
                        vehicle_to_edit = (vehicle_id, plate, state, make, model, color, nickname)

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT vehicle_id, plate, state, make, model, color, nickname
            FROM vehicle
            WHERE user_id = %s
            ORDER BY nickname, plate
        """, [request.session["user_id"]])
        vehicles_list = cursor.fetchall()

    return render(request, "core/vehicles.html", {
        "vehicles": vehicles_list,
        "modal_open": modal_open,
        "vehicle_to_edit": vehicle_to_edit
    })


def parking_dashboard(request):
    if "user_id" not in request.session:
        return redirect("login")

    user_id = request.session["user_id"]

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "start":
            lot_id = request.POST.get("lot_id")
            vehicle_id = request.POST.get("vehicle_id")

            with connection.cursor() as cursor:
                cursor.execute("""
                        INSERT INTO parking_session (user_id, vehicle_id, lot_id, start_ts, end_ts)
                        VALUES (%s, %s, %s, NOW(), NULL)
                    """, [user_id, vehicle_id, lot_id])

            messages.success(request, "Parking session started.")
            return redirect("parking")

        elif action == "end":
            session_id = request.POST.get("session_id")

            with connection.cursor() as cursor:
                cursor.execute("""
                        UPDATE parking_session
                        SET end_ts = NOW()
                        WHERE session_id = %s AND user_id = %s AND end_ts IS NULL
                    """, [session_id, user_id])

            messages.success(request, "Parking session ended.")
            return redirect("parking")

    with connection.cursor() as cursor:
        cursor.execute("""
                SELECT vehicle_id, plate, state, make, model, color, nickname
                FROM vehicle
                WHERE user_id = %s
            """, [user_id])
        vehicles = cursor.fetchall()

        cursor.execute("""
                SELECT lot_id, name, hourly_rate
                FROM lot
                ORDER BY name
            """)
        lots = cursor.fetchall()

        cursor.execute("""
                SELECT s.session_id, s.start_ts, l.name, v.nickname
                FROM parking_session s
                JOIN lot l ON s.lot_id = l.lot_id
                JOIN vehicle v ON s.vehicle_id = v.vehicle_id
                WHERE s.user_id = %s
                  AND s.start_ts IS NOT NULL
                  AND s.end_ts IS NULL
                ORDER BY s.start_ts DESC
                LIMIT 1
            """, [user_id])
        row = cursor.fetchone()

    active_session = None
    if row:
        active_session = {
            "session_id": row[0],
            "start_ts": row[1],
            "lot_name": row[2],
            "vehicle_nickname": row[3],
        }

    return render(request, "core/parking.html", {
        "vehicles": vehicles,
        "lots": lots,
        "active_session": active_session,
    })


def parking_history(request):
    if "user_id" not in request.session:
        return redirect("login")

    user_id = request.session["user_id"]

    with connection.cursor() as cursor:
        cursor.execute("""
                SELECT s.start_ts, s.end_ts,
                       l.name AS lot_name,
                       v.nickname, v.plate
                FROM parking_session s
                JOIN lot l ON s.lot_id = l.lot_id
                JOIN vehicle v ON s.vehicle_id = v.vehicle_id
                WHERE s.user_id = %s
                ORDER BY s.start_ts DESC
            """, [user_id])

        sessions = cursor.fetchall()

    return render(request, "core/parking_history.html", {
        "sessions": sessions
    })