import sqlite3
import pickle
import os

print("Resetting database...")
try:
    conn = sqlite3.connect("backend/attendance.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students")
    cursor.execute("DELETE FROM attendance")
    cursor.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()
    print("Database tables cleared successfully.")
except Exception as e:
    print("Error clearing database:", e)

print("Resetting embeddings...")
try:
    with open("backend/embeddings.pkl", "wb") as f:
        pickle.dump({"embeddings": [], "names": []}, f)
    print("Embeddings reset successfully.")
except Exception as e:
    print("Error resetting embeddings:", e)

try:
    if os.path.exists("mongo.py"):
        os.remove("mongo.py")
        print("Removed unused mongo.py")
except Exception as e:
    print("Error removing mongo.py:", e)

print("ALL RESET COMPLETE.")
