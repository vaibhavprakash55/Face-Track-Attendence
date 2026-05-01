import sqlite3

conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

print("=== STUDENTS TABLE ===")
try:
    cursor.execute("SELECT * FROM students")
    rows = cursor.fetchall()
    cursor.execute("PRAGMA table_info(students)")
    cols = [row[1] for row in cursor.fetchall()]
    print("Columns:", cols)
    if rows:
        for r in rows:
            print(r)
    else:
        print("NO STUDENTS FOUND IN DATABASE")
except Exception as e:
    print("Error:", e)

print()
print("=== USERS TABLE (Teachers/Admins) ===")
try:
    cursor.execute("SELECT email, name, role FROM users")
    rows = cursor.fetchall()
    if rows:
        for r in rows:
            print(r)
    else:
        print("NO USERS FOUND IN DATABASE")
except Exception as e:
    print("Error:", e)

print()
print("=== ATTENDANCE TABLE ===")
try:
    cursor.execute("SELECT * FROM attendance ORDER BY rowid DESC LIMIT 10")
    rows = cursor.fetchall()
    if rows:
        for r in rows:
            print(r)
    else:
        print("NO ATTENDANCE RECORDS FOUND")
except Exception as e:
    print("Error:", e)

conn.close()
print()
print("Done.")
