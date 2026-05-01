import { useAuth } from "@/hooks/use-auth";
import { useTheme } from "@/hooks/use-theme";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

const SettingsPage = () => {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="space-y-6 animate-fade-in max-w-2xl">
      <h1 className="page-header">Settings</h1>

      {/* Profile */}
      <div className="stat-card space-y-4">
        <h3 className="section-title">Profile</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input defaultValue={user?.name || ""} />
          </div>
          <div className="space-y-2">
            <Label>Email</Label>
            <Input defaultValue={user?.email || ""} />
          </div>
        </div>
        <Button
          className="bg-accent text-accent-foreground hover:bg-accent/90"
          onClick={() => toast.success("Profile updated")}
        >
          Save Changes
        </Button>
      </div>

      {/* Appearance */}
      <div className="stat-card space-y-4">
        <h3 className="section-title">Appearance</h3>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Dark Mode</p>
            <p className="text-xs text-muted-foreground">Toggle between light and dark theme</p>
          </div>
          <Switch checked={theme === "dark"} onCheckedChange={toggleTheme} />
        </div>
      </div>

      {/* Notifications */}
      <div className="stat-card space-y-4">
        <h3 className="section-title">Notifications</h3>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Email Notifications</p>
            <p className="text-xs text-muted-foreground">Receive daily attendance summary</p>
          </div>
          <Switch defaultChecked />
        </div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Push Notifications</p>
            <p className="text-xs text-muted-foreground">Get notified on absent students</p>
          </div>
          <Switch defaultChecked />
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
