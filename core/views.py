from django.shortcuts import render
from django.db import connection

def db_info(request):
    tables_data = {}

    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            try:
                cursor.execute(f"SELECT * FROM `{table}` LIMIT 10;")
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                tables_data[table] = {"columns": columns, "rows": rows}
            except Exception as e:
                tables_data[table] = {"error": str(e)}

    return render(request, "core/db_info.html", {"tables_data": tables_data})
