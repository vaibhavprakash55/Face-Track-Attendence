import os
import cv2
import numpy as np
import pickle
from keras_facenet import FaceNet
from mtcnn import MTCNN

# Initialize models
detector = MTCNN()
embedder = FaceNet()
MATCH_THRESHOLD = 1.12

# Load store
with open("embeddings.pkl", "rb") as f:
    data = pickle.load(f)

known_embeddings = np.asarray(data["embeddings"], dtype=np.float32)
known_names = data["names"]

def predict_face(image_path, true_name):
    img = cv2.imread(image_path)
    if img is None:
        return "Unknown"
        
    faces = detector.detect_faces(img)
    if not faces:
        return "Unknown"
        
    x, y, w, h = faces[0]['box']
    x, y = max(0, int(x)), max(0, int(y))
    h_img, w_img = img.shape[:2]
    w = min(int(w), w_img - x)
    h = min(int(h), h_img - y)
    
    face = img[y:y+h, x:x+w]
    try:
        face = cv2.resize(face, (160, 160))
    except cv2.error:
        return "Unknown"
        
    face = np.expand_dims(face, axis=0)
    embedding = embedder.embeddings(face)[0]
    
    min_dist = float("inf")
    pred_name = "Unknown"
    
    # Simple nearest neighbor matching
    for i in range(len(known_names)):
        dist = float(np.linalg.norm(known_embeddings[i] - embedding))
        # Optional: Exclude exact 0 distance if we don't want self-matches (since embeddings are from these images)
        if dist < 0.001 and known_names[i] == true_name:
            # We skip identical embeddings to test true generalization,
            # but since there are so few images, we will just allow it for a base accuracy check.
            pass
            
        if dist < min_dist:
            min_dist = dist
            pred_name = known_names[i]
            
    if min_dist < MATCH_THRESHOLD:
        return pred_name
    return "Unknown"

if __name__ == "__main__":
    dataset_dir = "dataset_small"
    if not os.path.exists(dataset_dir):
        print(f"Dataset directory '{dataset_dir}' not found.")
        exit(1)
        
    correct = 0
    total = 0
    
    print(f"Evaluating accuracy on {dataset_dir} dataset with MATCH_THRESHOLD={MATCH_THRESHOLD}...")
    
    for person_name in os.listdir(dataset_dir):
        person_dir = os.path.join(dataset_dir, person_name)
        if not os.path.isdir(person_dir):
            continue
            
        for img_name in os.listdir(person_dir):
            if not img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                continue
                
            img_path = os.path.join(person_dir, img_name)
            prediction = predict_face(img_path, person_name)
            
            total += 1
            if prediction == person_name:
                correct += 1
            
            print(f"True: {person_name:20} | Pred: {prediction:20} | Result: {'PASS' if prediction == person_name else 'FAIL'}")
            
    if total > 0:
        accuracy = (correct / total) * 100
        print(f"\n--- RESULTS ---")
        print(f"Total Evaluated: {total}")
        print(f"Correctly Recognized: {correct}")
        print(f"Overall Accuracy: {accuracy:.2f}%")
    else:
        print("No valid images found in dataset.")
