import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { ScanFace, Loader2 } from "lucide-react";
import { ApiError } from "@/services/api";
import ThreeCanvas from "@/components/ThreeCanvas";

const LoginPage = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Sign in failed. Try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col md:flex-row bg-background">
      {/* LEFT SIDE - TEACHER LOGIN */}
      <div className="w-full md:w-1/2 flex flex-col justify-center items-center p-8 md:p-16 bg-white dark:bg-zinc-950">
        <div className="w-full max-w-md space-y-8">
          {/* Brand/Logo */}
          <div className="flex items-center gap-2 mb-12">
            <div className="h-10 w-10 rounded-lg bg-teal-500 flex items-center justify-center">
              <ScanFace className="h-6 w-6 text-white" />
            </div>
            <span className="text-2xl font-bold text-zinc-900 dark:text-white">FaceTrack</span>
          </div>

          <div className="text-center space-y-2">
            <h1 className="text-4xl font-bold text-zinc-900 dark:text-white tracking-tight">Login to Your Account</h1>
            <p className="text-muted-foreground text-sm">Teacher Access Portal</p>
          </div>

          <div className="pt-4">
            {error && (
              <p className="text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2 mb-4 text-center" role="alert">
                {error}
              </p>
            )}
            
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-4">
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={loading}
                  className="h-12 bg-zinc-50 dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 rounded-full px-6 placeholder:text-zinc-400"
                />
                
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={loading}
                  className="h-12 bg-zinc-50 dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 rounded-full px-6 placeholder:text-zinc-400"
                />
              </div>

              <div className="flex justify-center pt-2">
                <Button 
                  type="submit" 
                  className="w-48 h-12 bg-teal-500 hover:bg-teal-600 text-white rounded-full font-medium text-base shadow-lg transition-all" 
                  disabled={loading}
                >
                  {loading ? (
                    <><Loader2 className="h-5 w-5 mr-2 animate-spin" /> Signing in…</>
                  ) : (
                    "Sign In"
                  )}
                </Button>
              </div>
            </form>

            <p className="text-center text-sm text-zinc-500 mt-8">
              Don't have a teacher account?{" "}
              <Link to="/signup" className="text-teal-600 hover:underline font-medium">
                Create one
              </Link>
            </p>
          </div>
        </div>
      </div>

      {/* RIGHT SIDE - STUDENT PORTAL */}
      <div className="w-full md:w-1/2 flex flex-col justify-center items-center p-8 md:p-16 bg-gradient-to-br from-teal-400 to-emerald-600 relative overflow-hidden">
        {/* Render the Three.js animated background */}
        <ThreeCanvas />
        
        {/* Decorative Background Elements */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 z-0"></div>
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-white/10 rounded-full blur-3xl translate-y-1/3 -translate-x-1/3 z-0"></div>
        
        <div className="w-full max-w-md text-center space-y-8 relative z-10">
          <h2 className="text-5xl font-bold text-white tracking-tight">New Here?</h2>
          
          <div className="space-y-4">
            <p className="text-teal-50 text-lg leading-relaxed px-4">
              Student Registration Portal
            </p>
            <p className="text-white/80 text-base px-8 pb-4">
              Register your face securely to discover a great amount of new opportunities and seamless daily attendance!
            </p>
          </div>

          <Button 
            onClick={() => navigate("/student-registration")}
            type="button"
            className="w-48 h-12 bg-white text-teal-600 hover:bg-zinc-50 rounded-full font-medium text-base shadow-xl transition-all"
          >
            Register Face
          </Button>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
