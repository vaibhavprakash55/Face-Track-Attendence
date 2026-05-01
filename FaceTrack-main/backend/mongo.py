import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# The connection string provided
MONGO_URI = "mongodb+srv://harsh:Harsh2007@cluster0.x2gakgi.mongodb.net/?appName=Cluster0"

# Create a new client and connect to the server
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))

# Access the main database
db = client['facetrack_db']

# Define collection helpers
users_col = db['users']           # Replaces users table
sessions_col = db['sessions']     # Replaces sessions table
students_col = db['students']     # Replaces students table
attendance_col = db['attendance'] # Replaces attendance table

def init_mongo_indexes():
    """Create necessary unique indexes to replicate SQLite constraints."""
    # Teacher/Admin emails must be unique
    users_col.create_index("email", unique=True)
    
    # Session tokens must be unique
    sessions_col.create_index("token", unique=True)
    
    # Student roll numbers must be unique
    students_col.create_index("roll_no", unique=True)
    
    # Optional: compound index for attendance (name + date) for quick lookups
    attendance_col.create_index([("name", 1), ("date", 1)])

def test_connection():
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
        init_mongo_indexes()
        print("Indexes ensured.")
    except Exception as e:
        print(e)

if __name__ == "__main__":
    test_connection()
