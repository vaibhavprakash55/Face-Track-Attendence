import { createContext, useContext, useState, ReactNode, useEffect, useCallback } from "react";
import { auth } from "@/config/firebase";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  updateProfile,
  User as FirebaseUser,
} from "firebase/auth";
import {
  AUTH_TOKEN_STORAGE_KEY,
  type AuthUserDto,
} from "@/services/api";

export type AuthUser = AuthUserDto;

interface AuthContextType {
  user: AuthUser | null;
  /** False until we finish checking Firebase auth state. */
  authReady: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  authReady: false,
  login: async () => {},
  signup: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser: FirebaseUser | null) => {
      if (firebaseUser) {
        // Get token to store in localStorage for API requests
        const token = await firebaseUser.getIdToken();
        localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
        
        const authUser: AuthUser = {
          name: firebaseUser.displayName || "Teacher",
          email: firebaseUser.email || "",
          role: "Teacher", // Default role for now
        };
        localStorage.setItem("auth_user", JSON.stringify(authUser));
        setUser(authUser);
      } else {
        localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
        localStorage.removeItem("auth_user");
        setUser(null);
      }
      setAuthReady(true);
    });

    return () => unsubscribe();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await signInWithEmailAndPassword(auth, email, password);
  }, []);

  const signup = useCallback(async (name: string, email: string, password: string) => {
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    await updateProfile(userCredential.user, {
      displayName: name,
    });
    
    // The onAuthStateChanged listener will handle the state update
  }, []);

  const logout = useCallback(async () => {
    await signOut(auth);
  }, []);

  return (
    <AuthContext.Provider value={{ user, authReady, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
