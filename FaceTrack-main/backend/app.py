from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np
import math
import os
import pickle
import re
import secrets
import time
import traceback
import smtplib
from email.message import EmailMessage
from mtcnn import MTCNN
from keras_facenet import FaceNet
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
import firebase_admin
from firebase_admin import auth, credentials
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson.binary import Binary
from dotenv import load_dotenv
load_dotenv()

import sqlite3

app = Flask(__name__)
CORS(app)
AUTH_DB = "auth.db"

# Initialize Firebase Admin if credentials are available.
try:
    firebase_admin.get_app()
except ValueError:
    firebase_cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if firebase_cred_path and os.path.exists(firebase_cred_path):
        cred = credentials.Certificate(firebase_cred_path)
        firebase_admin.initialize_app(cred)
    else:
        try:
            firebase_admin.initialize_app()
        except Exception:
            print("Firebase Admin initialization skipped; set GOOGLE_APPLICATION_CREDENTIALS if using Firebase auth.")

# ================== 🔥 MONGODB CONFIG (FINAL FIXED) ==================
MONGO_URI = "Harsh Mongo URI"

try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000  # 5 sec timeout
    )

    # Force connection check
    client.server_info()

    print("✅ MongoDB Connected Successfully")

except Exception as e:
    print("❌ MongoDB Connection Failed")
    print("Error:", e)
    exit()   # stop app if DB not connected

db = client["facetrack_db"]

users_col = db["users"]
sessions_col = db["sessions"]
students_col = db["students"]
attendance_col = db["attendance"]
face_config_col = db["face_config"]
# ================================================================

def init_mongo_indexes():
    try:
        users_col.create_index("email", unique=True)
        sessions_col.create_index("token", unique=True)
        students_col.create_index("roll_no", unique=True)
        attendance_col.create_index([("name", 1), ("date", 1)])
    except Exception as e:
        print(f"Index creation warning: {e}")

init_mongo_indexes()


def ensure_attendance_schema():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

ensure_attendance_schema()

SESSION_DAYS = 7
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()

def _user_row_by_email(cursor_placeholder, email: str):
    # 'cursor_placeholder' is ignored as we use MongoDB collections directly
    return users_col.find_one({"email": email})

def _session_user_from_token(token: str):
    if not token:
        return None
    now = int(time.time())
    row = sessions_col.find_one({"token": token})
    if not row:
        return None
    
    expires_unix = row.get("expires_unix", 0)
    if expires_unix < now:
        sessions_col.delete_one({"token": token})
        return None
        
    email = row.get("email")
    roll_no = row.get("roll_no")
    role = row.get("role")
    name = row.get("name")
    
    if role and name and (email or roll_no):
        u = {"name": name, "role": role}
        if email: u["email"] = email
        if roll_no: u["roll_no"] = roll_no
        return u

    if not email:
        return None
    
    u = users_col.find_one({"email": email})
    if not u:
        return None
    return {"name": u.get("name"), "email": u.get("email"), "role": u.get("role")}


detector = MTCNN()
embedder = FaceNet()

EMBEDDINGS_PATH = "embeddings.pkl"
# Max L2 distance between stored embedding vectors and live face vector.
MATCH_THRESHOLD = 1.12

PRESENT_STATUS = "Present"
EDITED_STATUS = "Edited"
VERIFIED_STATUS = "Verified"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")

EMAIL_SUBJECT = "Attendance Verification - FaceTrack"


def _load_embeddings_store():
    """Load embeddings from MongoDB or start empty."""
    try:
        data = face_config_col.find_one({"_id": "current_embeddings"})
        if not data or "matrix" not in data or "names" not in data:
            return {"embeddings": [], "names": []}
        
        matrix_bin = data["matrix"]
        names = data["names"]
        matrix = pickle.loads(matrix_bin)
        return {"embeddings": matrix, "names": names}
    except Exception as e:
        print(f"Warning: Failed to load embeddings from Mongo: {e}")
        return {"embeddings": [], "names": []}


def _as_embedding_matrix(embeddings):
    """Normalize stored embeddings to 2-D numpy array (n, dim)."""
    arr = np.asarray(embeddings, dtype=np.float32)
    if arr.size == 0:
        # Placeholder shape until first registration supplies embedding width (FaceNet ~512).
        return np.empty((0, 512), dtype=np.float32)
    if arr.ndim == 1:
        return arr.reshape(1, -1)
    return arr


_data = _load_embeddings_store()
known_embeddings = _as_embedding_matrix(_data["embeddings"])
known_names = list(_data["names"])

def align_face(img, left_eye, right_eye):
    dy = right_eye[1] - left_eye[1]
    dx = right_eye[0] - left_eye[0]
    angle = math.degrees(math.atan2(dy, dx))
    
    eyes_center = (
        float(left_eye[0] + right_eye[0]) / 2,
        float(left_eye[1] + right_eye[1]) / 2
    )
    
    M = cv2.getRotationMatrix2D(eyes_center, angle, scale=1.0)
    h, w = img.shape[:2]
    aligned_img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC)
    return aligned_img

def _detect_and_embed_from_bgr(image_bgr):
    """
    Produce one FaceNet embedding vector (1-D float32) from an OpenCV BGR frame.
    Keeps MTCNN + crop + resize in BGR so vectors stay consistent with a typical
    cv2.imdecode / imread → MTCNN → FaceNet pipeline and your stored embeddings.pkl.
    """
    if image_bgr is None:
        return None, "invalid_image"

    faces = detector.detect_faces(image_bgr)
    if len(faces) == 0:
        return None, "no_face"

    face_info = faces[0]
    keypoints = face_info.get("keypoints")
    if keypoints and "left_eye" in keypoints and "right_eye" in keypoints:
        aligned_bgr = align_face(image_bgr, keypoints["left_eye"], keypoints["right_eye"])
        aligned_faces = detector.detect_faces(aligned_bgr)
        if aligned_faces:
             face_info = aligned_faces[0]
             image_bgr = aligned_bgr

    x, y, w, h = face_info["box"]
    h_img, w_img = image_bgr.shape[:2]
    x, y = max(0, int(x)), max(0, int(y))
    w, h = int(w), int(h)
    w = min(w, w_img - x)
    h = min(h, h_img - y)
    if w <= 1 or h <= 1:
        return None, "no_face"

    face = image_bgr[y : y + h, x : x + w]
    try:
        face = cv2.resize(face, (160, 160))
    except cv2.error:
        return None, "no_face"

    face = np.expand_dims(face, axis=0)
    try:
        embedding = embedder.embeddings(face)[0]
    except Exception:
        return None, "no_face"
    return embedding, None


def extract_face_embedding(image_bgr):
    """
    Returns (embedding, None) on success, or (None, error_code) on failure.
    error_code: 'invalid_image' | 'no_face' | 'encode_error'
    """
    try:
        emb, err = _detect_and_embed_from_bgr(image_bgr)
    except Exception:
        return None, "encode_error"
    if err == "invalid_image":
        return None, "invalid_image"
    if err == "no_face":
        return None, "no_face"
    return emb, None


def persist_embeddings_file(embeddings_matrix, names_list):
    """Save embeddings matrix to MongoDB."""
    try:
        matrix_bin = Binary(pickle.dumps(embeddings_matrix))
        face_config_col.update_one(
            {"_id": "current_embeddings"},
            {"$set": {"matrix": matrix_bin, "names": names_list}},
            upsert=True
        )
    except Exception as e:
        print(f"Error persisting embeddings to Mongo: {e}")
        raise e


def recognize_face(image_bgr):
    embedding, err = _detect_and_embed_from_bgr(image_bgr)
    if err == "invalid_image":
        return "No Face Found"
    if err == "no_face":
        return "No Face Found"

    matrix = _as_embedding_matrix(known_embeddings)
    if matrix.shape[0] == 0 or len(known_names) == 0:
        return "Unknown"

    min_dist = float("inf")
    name = "Unknown"
    n = min(matrix.shape[0], len(known_names))
    for i in range(n):
        dist = float(np.linalg.norm(matrix[i] - embedding))
        if dist < min_dist:
            min_dist = dist
            name = known_names[i]

    if min_dist < MATCH_THRESHOLD:
        return name

    return "Unknown"


def _detect_and_embed_multiple_from_bgr(image_bgr, max_faces: int = 10):
    """
    Detect all faces in the frame and return FaceNet embeddings for each.
    Returns (embeddings, error_code). error_code is 'invalid_image' | 'no_face'.
    """
    if image_bgr is None:
        return [], "invalid_image"

    faces = detector.detect_faces(image_bgr)
    if not faces:
        return [], "no_face"

    embeddings = []
    h_img, w_img = image_bgr.shape[:2]

    for face in faces[:max_faces]:
        box = face.get("box")
        if not box or len(box) != 4:
            continue
        x, y, w, h = box

        x, y, w, h = int(x), int(y), int(w), int(h)
        x = max(0, x)
        y = max(0, y)
        w = max(1, min(w, w_img - x))
        h = max(1, min(h, h_img - y))

        keypoints = face.get("keypoints")
        current_img = image_bgr
        if keypoints and "left_eye" in keypoints and "right_eye" in keypoints:
            aligned_bgr = align_face(image_bgr, keypoints["left_eye"], keypoints["right_eye"])
            aligned_faces = detector.detect_faces(aligned_bgr)
            if aligned_faces:
                 # Find the face closest to the original box
                 # (for simplicity, we just take the first detected face in the aligned image)
                 face_info = aligned_faces[0]
                 box = face_info.get("box")
                 current_img = aligned_bgr
                 
                 x, y, w, h = box
                 x, y, w, h = int(x), int(y), int(w), int(h)
                 x = max(0, x)
                 y = max(0, y)
                 w = max(1, min(w, w_img - x))
                 h = max(1, min(h, h_img - y))

        if w <= 1 or h <= 1:
            continue

        crop = current_img[y : y + h, x : x + w]
        try:
            crop = cv2.resize(crop, (160, 160))
        except cv2.error:
            continue

        crop = np.expand_dims(crop, axis=0)
        embedding = embedder.embeddings(crop)[0]
        embeddings.append(embedding)

    if not embeddings:
        return [], "no_face"
    return embeddings, None


def recognize_faces(image_bgr):
    """
    Recognize multiple faces in one frame.
    Returns a list of unique recognized names (no duplicates).
    """
    embeddings, err = _detect_and_embed_multiple_from_bgr(image_bgr)
    if err:
        return []

    if len(known_names) == 0 or known_embeddings.shape[0] == 0:
        return []

    recognized = []
    seen = set()
    for emb in embeddings:
        dists = np.linalg.norm(known_embeddings - emb, axis=1)
        i = int(np.argmin(dists))
        if float(dists[i]) < MATCH_THRESHOLD:
            name = known_names[i]
            if name not in seen:
                seen.add(name)
                recognized.append(name)
    return recognized


def recognize_faces_with_boxes(image_bgr, max_faces: int = 10):
    """
    Like recognize_faces(), but returns per-face results including bounding boxes.
    Only returns registered (matched) faces.
    Format: [{ "name": str, "box": [x,y,w,h] }, ...]
    """
    if image_bgr is None:
        return []
    faces = detector.detect_faces(image_bgr)
    if not faces:
        return []
    if len(known_names) == 0 or known_embeddings.shape[0] == 0:
        return []

    out = []
    seen = set()
    h_img, w_img = image_bgr.shape[:2]

    for face in faces[:max_faces]:
        box = face.get("box")
        if not box or len(box) != 4:
            continue
        x, y, w, h = [int(v) for v in box]
        x = max(0, x)
        y = max(0, y)
        w = max(1, min(w, w_img - x))
        h = max(1, min(h, h_img - y))
        if w <= 1 or h <= 1:
            continue
        crop = image_bgr[y : y + h, x : x + w]
        try:
            crop = cv2.resize(crop, (160, 160))
        except cv2.error:
            continue
        crop = np.expand_dims(crop, axis=0)
        emb = embedder.embeddings(crop)[0]
        dists = np.linalg.norm(known_embeddings - emb, axis=1)
        i = int(np.argmin(dists))
        if float(dists[i]) < MATCH_THRESHOLD:
            name = known_names[i]
            if name in seen:
                continue
            seen.add(name)
            out.append({"name": name, "box": [x, y, w, h]})
    return out


def mark_attendance(name):
    return mark_attendance_with_status(name=name, status=PRESENT_STATUS)


def mark_attendance_with_status(name: str, status: str = PRESENT_STATUS) -> bool:
    """Mark attendance once per student per day in MongoDB."""
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    existing = attendance_col.find_one({"name": name, "date": date})
    if existing:
        return False

    attendance_col.insert_one({
        "name": name,
        "date": date,
        "time": time_str,
        "status": status
    })
    return True


def _require_auth_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Unauthorized"}), 401)
    token = auth_header[7:].strip()
    
    try:
        # Verify the Firebase ID token
        decoded_token = auth.verify_id_token(token)
        user = {
            "name": decoded_token.get("name", "Teacher"),
            "email": decoded_token.get("email"),
            "role": "Teacher" # You can use custom claims for multiple roles
        }
        return user, None
    except Exception as e:
        print(f"Auth error: {e}")
        return None, (jsonify({"error": "Unauthorized"}), 401)


def _send_attendance_email(to_email: str, students: list[str], verify_url: str, date: str, time_label: str):
    if not SMTP_USER or not SMTP_PASS or not SMTP_FROM:
        raise RuntimeError("Email is not configured on the server. Set SMTP_USER/SMTP_PASS/SMTP_FROM env vars.")

    student_lines = "\n".join([f"- {s}" for s in students])
    msg = EmailMessage()
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = EMAIL_SUBJECT
    msg.set_content(
        f"Students Present:\n{student_lines if student_lines else '- (none)'}\n\n"
        f"Date: {date}\n"
        f"Time: {time_label}\n\n"
        f"Verify Attendance:\n{verify_url}\n"
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


@app.route("/")
def home():
    return "Face Attendance API Running"


@app.route("/students", methods=["GET"])
def list_students():
    rows = list(students_col.find({}).sort("_id", -1))
    return jsonify(
        [
            {
                "name": r.get("name"),
                "roll_no": r.get("roll_no"),
                "course": r.get("course"),
                "year": r.get("year"),
                "section": r.get("section"),
                "role": r.get("role", "student"),
            }
            for r in rows
        ]
    )


@app.route("/register", methods=["POST"])
def register():
    global known_embeddings, known_names

    try:
        return _register_student_post()
    except Exception:
        traceback.print_exc()
        return jsonify(
            {
                "error": "Registration failed on the server. See the Flask terminal for the full error.",
            }
        ), 500


def _register_student_post():
    global known_embeddings, known_names

    # Public student self-registration (no login). Teacher uses dashboard only to view students.
    role = (request.form.get("role") or "").strip().lower()
    if role != "student":
        return jsonify({"error": "Only student self-registration is allowed here."}), 403

    name = (request.form.get("name") or "").strip()
    roll_no = (request.form.get("roll_no") or "").strip()
    course = (request.form.get("course") or "").strip()
    year = (request.form.get("year") or "").strip()
    section = (request.form.get("section") or "").strip()

    if not all([name, roll_no, course, year, section]):
        return jsonify({"error": "Missing required fields (name, roll_no, course, year, section)."}), 400

    required_images = [
        ("front_image", "front"),
        ("left_image", "left"),
        ("right_image", "right"),
    ]
    embeddings = []
    for field_name, label in required_images:
        if field_name not in request.files:
            return jsonify({"error": f"Missing {label} face image."}), 400
        file = request.files[field_name]
        if not file or file.filename == "":
            return jsonify({"error": f"Missing {label} face image."}), 400
        img_bytes = file.read()
        if not img_bytes:
            return jsonify({"error": f"Empty {label} face image."}), 400
        npimg = np.frombuffer(img_bytes, np.uint8)
        image_bgr = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
        if image_bgr is None:
            return jsonify({"error": f"Invalid {label} face image."}), 400

        emb, err = extract_face_embedding(image_bgr)
        if err == "no_face":
            return jsonify({"error": f"No face detected in {label} image."}), 400
        if err == "invalid_image":
            return jsonify({"error": f"Invalid {label} image."}), 400
        if err == "encode_error" or emb is None:
            return jsonify(
                {"error": f"Could not compute face features for {label} image. Try again with clearer lighting."}
            ), 400

        embeddings.append(emb)

    matrix = _as_embedding_matrix(known_embeddings)
    n_emb = int(matrix.shape[0])
    n_names = len(known_names)
    emb_dim = (
        int(matrix.shape[1])
        if matrix.ndim == 2 and n_emb > 0
        else int(np.asarray(embeddings[0], dtype=np.float32).reshape(-1).shape[0])
    )
    m = min(n_emb, n_names)
    if n_emb != n_names:
        print(f"[register] Aligning embeddings.pkl: {n_emb} vectors vs {n_names} names -> {m} pairs.")
    if m == 0:
        matrix = np.empty((0, emb_dim), dtype=np.float32)
        names_base = []
    else:
        matrix = np.asarray(matrix[:m], dtype=np.float32)
        names_base = list(known_names[:m])

    if name in names_base:
        return jsonify({"error": "This student is already enrolled for recognition."}), 400

    existing = students_col.find_one({"roll_no": roll_no})
    if not existing:
        students_col.insert_one({
            "name": name,
            "roll_no": roll_no,
            "course": course,
            "year": year,
            "section": section,
            "role": "student"
        })
    else:
        if existing.get("role") and existing.get("role") != "student":
            return jsonify({"error": "This roll number is not allowed for student registration."}), 403
        students_col.update_one(
            {"roll_no": roll_no},
            {"$set": {
                "name": name,
                "course": course,
                "year": year,
                "section": section,
                "role": "student"
            }}
        )

    rows = [np.asarray(e, dtype=np.float32).reshape(1, -1) for e in embeddings]
    for i, row in enumerate(rows):
        if row.shape[1] != emb_dim:
            return jsonify(
                {"error": f"Internal error: embedding dimension {row.shape[1]} != {emb_dim} for angle {i + 1}."}
            ), 400
    if matrix.shape[1] != emb_dim and matrix.shape[0] > 0:
        return jsonify({"error": "Stored embeddings use a different dimension than the face model; reset embeddings.pkl or fix the file."}), 400
    if matrix.size == 0:
        matrix = np.empty((0, emb_dim), dtype=np.float32)

    try:
        if names_base:
            new_matrix = np.vstack([matrix] + rows)
        else:
            new_matrix = np.vstack(rows)
    except ValueError as exc:
        return jsonify({"error": f"Embedding shape error (corrupt model output?): {exc!s}"}), 400

    new_names = names_base + [name, name, name]

    try:
        persist_embeddings_file(new_matrix, new_names)
    except Exception as exc:
        students_col.delete_one({"roll_no": roll_no})
        return jsonify({"error": f"Failed to save embeddings: {exc!s}"}), 500

    known_embeddings = new_matrix
    known_names = new_names

    return jsonify({"ok": True, "message": "Student registered successfully with 3 face embeddings."})


@app.route("/facetrack-student-register", methods=["POST"])
def facetrack_student_register():
    """Same behavior as POST /register — unique path avoids proxies or other apps that intercept /register."""
    return register()


@app.route("/attendance", methods=["GET"])
def get_attendance():
    date = (request.args.get("date") or "").strip()
    query = {}
    if date:
        query["date"] = date
    
    rows = list(attendance_col.find(query).sort("_id", -1))
    return jsonify(
        [{"name": r.get("name"), "date": r.get("date"), "time": r.get("time"), "status": r.get("status")} for r in rows]
    )


@app.route("/recognize", methods=["POST"])
def recognize():
    try:
        if "image" not in request.files:
            return jsonify({"recognized_person": "No Face Found"})

        file = request.files["image"]
        if not file or file.filename == "":
            return jsonify({"recognized_person": "No Face Found"})

        img_bytes = file.read()
        if not img_bytes:
            return jsonify({"recognized_person": "No Face Found"})

        npimg = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"recognized_person": "No Face Found"})

        name = recognize_face(frame)

        if name != "Unknown" and name != "No Face Found":
            mark_attendance(name)

        return jsonify({"recognized_person": name})
    except Exception as exc:
        print("[recognize]", repr(exc))
        return jsonify({"recognized_person": "No Face Found"})


@app.route("/recognize-multi", methods=["POST"])
def recognize_multi():
    """
    Multi-face recognition endpoint for classroom attendance.
    Returns { recognized_students: [...] } with no duplicates.
    Also marks attendance for recognized students (one per student per day).
    """
    try:
        if "image" not in request.files:
            return jsonify({"recognized_students": [], "message": "No image provided."}), 400

        file = request.files["image"]
        if not file or file.filename == "":
            return jsonify({"recognized_students": [], "message": "No image selected."}), 400

        img_bytes = file.read()
        if not img_bytes:
            return jsonify({"recognized_students": [], "message": "Empty image."}), 400

        npimg = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"recognized_students": [], "message": "Invalid image."}), 400

        recognized_faces = recognize_faces_with_boxes(frame)
        recognized = [f["name"] for f in recognized_faces]
        for name in recognized:
            mark_attendance_with_status(name=name, status=PRESENT_STATUS)

        if not recognized:
            return jsonify({"recognized_students": [], "message": "No registered faces detected."})

        return jsonify(
            {
                "recognized_students": recognized,
                "recognized_faces": recognized_faces,
                "message": "Faces recognized.",
            }
        )
    except Exception as exc:
        print("[recognize-multi]", repr(exc))
        return jsonify({"recognized_students": [], "message": "Recognition failed."}), 500


def _issue_session(email: str) -> str:
    token = secrets.token_urlsafe(32)
    exp = int(time.time()) + SESSION_DAYS * 24 * 3600
    conn = sqlite3.connect(AUTH_DB)
    # teacher session; include user data for /auth/me
    cur = conn.cursor()
    cur.execute("SELECT name, role FROM users WHERE email = ?", (email,))
    u = cur.fetchone()
    name = u[0] if u else ""
    role = u[1] if u else "Teacher"
    conn.execute(
        "INSERT INTO sessions (token, email, roll_no, role, name, expires_unix) VALUES (?,?,?,?,?,?)",
        (token, email, None, role, name, exp),
    )
    conn.commit()
    conn.close()
    return token


# --- Authentication (Obsolete custom Flask auth replaced by Firebase) ---
# The /auth/* endpoints are no longer needed as the frontend uses Firebase SDK
# and the backend verifies tokens via Firebase Admin.


@app.route("/attendance/session/notify", methods=["POST"])
def attendance_session_notify():
    user, auth_err = _require_auth_user()
    if auth_err:
        return auth_err

    if user.get("role") == "Student" or user.get("role") not in ("Teacher", "Admin") or not user.get("email"):
        return jsonify({"error": "Only signed-in teachers can send attendance email."}), 403

    data = request.get_json(silent=True) or {}
    date = (data.get("date") or "").strip()
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    time_label = datetime.now().strftime("%H:%M:%S")

    students = data.get("students")
    if not isinstance(students, list):
        return jsonify({"error": "students must be a list"}), 400

    verify_url = (data.get("verify_url") or "").strip()
    if not verify_url:
        verify_url = "Open Face Recognition page in the dashboard to verify."

    # Keep email content stable and readable.
    students = [str(s).strip() for s in students if str(s).strip()]

    to_email = user.get("email")
    if not to_email:
        return jsonify({"error": "No email on file for this account."}), 400

    try:
        _send_attendance_email(
            to_email=to_email,
            students=students,
            verify_url=verify_url,
            date=date,
            time_label=time_label,
        )
    except Exception as exc:
        print("[attendance/session/notify]", repr(exc))
        return jsonify({"error": "Failed to send email."}), 500

    return jsonify({"ok": True, "message": "Email sent."})


@app.route("/update-attendance", methods=["POST"])
def update_attendance():
    user, auth_err = _require_auth_user()
    if auth_err:
        return auth_err

    if user.get("role") not in ("Teacher", "Admin"):
        return jsonify({"error": "Only teachers can verify attendance."}), 403

    data = request.get_json(silent=True) or {}
    date = (data.get("date") or "").strip()
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    verified_names = data.get("verified_names")
    if not isinstance(verified_names, list):
        return jsonify({"error": "verified_names must be a list"}), 400

    verified_names = [str(s).strip() for s in verified_names if str(s).strip()]

    ensure_attendance_schema()
    now = datetime.now()
    time = now.strftime("%H:%M:%S")

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    # Remove rows not included in the final verified list.
    if verified_names:
        placeholders = ",".join(["?"] * len(verified_names))
        cursor.execute(
            f"DELETE FROM attendance WHERE date = ? AND name NOT IN ({placeholders})",
            [date] + verified_names,
        )
    else:
        cursor.execute("DELETE FROM attendance WHERE date = ?", (date,))

    # Upsert verified names with appropriate status.
    for name in verified_names:
        cursor.execute(
            "SELECT 1 FROM attendance WHERE date = ? AND name = ?",
            (date, name),
        )
        exists = cursor.fetchone() is not None
        new_status = VERIFIED_STATUS if exists else EDITED_STATUS
        if exists:
            cursor.execute(
                "UPDATE attendance SET time = ?, status = ? WHERE date = ? AND name = ?",
                (time, new_status, date, name),
            )
        else:
            cursor.execute(
                "INSERT INTO attendance (name, date, time, status) VALUES (?,?,?,?)",
                (name, date, time, new_status),
            )

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "message": "Attendance updated."})


if __name__ == "__main__":
    # 0.0.0.0 so the API works when the React app is opened via your LAN IP (e.g. http://172.16.x.x:8080).
    print("Face Attendance API → http://127.0.0.1:5000 (and http://<your-LAN-IP>:5000 on this machine)")
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)