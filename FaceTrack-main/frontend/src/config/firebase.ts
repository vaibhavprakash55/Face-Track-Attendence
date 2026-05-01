import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyDKsdQbsyN9d4ZTOeBmEHAoHcRcg2AsEbY",
  authDomain: "face-attendance-b363c.firebaseapp.com",
  projectId: "face-attendance-b363c",
  storageBucket: "face-attendance-b363c.firebasestorage.app",
  messagingSenderId: "970772244024",
  appId: "1:970772244024:web:cbf10c26fbb1594ce228cd",
  measurementId: "G-QLL45WR6ML"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export default app;
