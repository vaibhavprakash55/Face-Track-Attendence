import os
import cv2
import numpy as np
import pickle
import math
from keras_facenet import FaceNet
from mtcnn import MTCNN

detector = MTCNN()
embedder = FaceNet()
MATCH_THRESHOLD = 1.12

# Load store
with open("embeddings.pkl", "rb") as f:
    data = pickle.load(f)

known_embeddings = np.asarray(data["embeddings"], dtype=np.float32)
known_names = data["names"]

def align_face(img, left_eye, right_eye):
    # Calculate angle
    dy = right_eye[1] - left_eye[1]
    dx = right_eye[0] - left_eye[0]
    angle = math.degrees(math.atan2(dy, dx))
    
    # Center of rotation
    eyes_center = (
        (left_eye[0] + right_eye[0]) // 2,
        (left_eye[1] + right_eye[1]) // 2
    )
    
    # Get rotation matrix
    M = cv2.getRotationMatrix2D(eyes_center, angle, scale=1.0)
    
    # Apply rotation
    h, w = img.shape[:2]
    aligned_img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC)
    return aligned_img

def predict_face_aligned(image_path, true_name):
    img = cv2.imread(image_path)
    if img is None: return "Unknown"
        
    faces = detector.detect_faces(img)
    if not faces: return "Unknown"
    
    # Get first face and landmarks
    face_info = faces[0]
    box = face_info['box']
    keypoints = face_info['keypoints']
    
    # Align the image
    aligned_img = align_face(img, keypoints['left_eye'], keypoints['right_eye'])
    
    # Detect face again in aligned image to get precise box (or we could rotate the bounding box, but this is safer)
    aligned_faces = detector.detect_faces(aligned_img)
    if not aligned_faces: 
        # Fallback to original
        aligned_img = img
        aligned_faces = faces
        
    x, y, w, h = aligned_faces[0]['box']
    x, y = max(0, int(x)), max(0, int(y))
    h_img, w_img = aligned_img.shape[:2]
    w = min(int(w), w_img - x)
    h = min(int(h), h_img - y)
    
    face_crop = aligned_img[y:y+h, x:x+w]
    try:
        face_crop = cv2.resize(face_crop, (160, 160))
    except:
        return "Unknown"
        
    face_crop = np.expand_dims(face_crop, axis=0)
    embedding = embedder.embeddings(face_crop)[0]
    
    min_dist = float("inf")
    pred_name = "Unknown"
    
    for i in range(len(known_names)):
        dist = float(np.linalg.norm(known_embeddings[i] - embedding))
        if dist < 0.001 and known_names[i] == true_name:
            continue # skip exact same image if it maps to 0 (though alignment might change it from 0)
        
        if dist < min_dist:
            min_dist = dist
            pred_name = known_names[i]
            
    if min_dist < MATCH_THRESHOLD:
        return pred_name
    return "Unknown"

if __name__ == "__main__":
    dataset_dir = "dataset_small"
    correct, total = 0, 0
    
    print("Evaluating Aligned Accuracy...")
    for person_name in os.listdir(dataset_dir):
        person_dir = os.path.join(dataset_dir, person_name)
        if not os.path.isdir(person_dir): continue
            
        for img_name in os.listdir(person_dir):
            if not img_name.endswith(('.png', '.jpg', '.jpeg')): continue
                
            img_path = os.path.join(person_dir, img_name)
            prediction = predict_face_aligned(img_path, person_name)
            
            total += 1
            if prediction == person_name: correct += 1
            print(f"True: {person_name[:15]:15} | Pred: {prediction[:15]:15} | Result: {'PASS' if prediction == person_name else 'FAIL'}")
            
    if total > 0:
        print(f"\nAligned Accuracy: {(correct/total)*100:.2f}% ({correct}/{total})")
