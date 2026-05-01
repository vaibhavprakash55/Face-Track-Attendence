import { useState, useEffect, useCallback } from "react";
import { CheckCircle2, XCircle, Loader2, RefreshCw, Users, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fetchAttendance, fetchStudents, ApiError, type AttendanceRow, type StudentRow } from "@/services/api";
import { toast } from "sonner";

function todayISO(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const REFRESH_INTERVAL = 30; // seconds

const TodayAttendancePage = () => {
  const today = todayISO();

  const [students, setStudents] = useState<StudentRow[]>([]);
  const [attendance, setAttendance] = useState<AttendanceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL);

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [allStudents, allAttendance] = await Promise.all([
        fetchStudents(),
        fetchAttendance(),
      ]);
      setStudents(allStudents);
      setAttendance(allAttendance);
      setLastRefreshed(new Date());
      setCountdown(REFRESH_INTERVAL);
      if (!silent) toast.success("Attendance refreshed.");
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Could not load data.";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    void loadData(true);
  }, [loadData]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const id = window.setInterval(() => void loadData(true), REFRESH_INTERVAL * 1000);
    return () => clearInterval(id);
  }, [loadData]);

  // Countdown ticker
  useEffect(() => {
    const id = window.setInterval(() => {
      setCountdown((prev) => (prev <= 1 ? REFRESH_INTERVAL : prev - 1));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  // Compute present / absent
  const todayAttendance = attendance.filter((r) => r.date === today);
  const presentNames = new Set(todayAttendance.map((r) => r.name.toLowerCase()));

  const presentStudents = students.filter((s) => presentNames.has(s.name.toLowerCase()));
  const absentStudents = students.filter((s) => !presentNames.has(s.name.toLowerCase()));

  const presentPct = students.length > 0 ? Math.round((presentStudents.length / students.length) * 100) : 0;

  return (
    <div className="space-y-6 animate-fade-in max-w-6xl mx-auto px-1 sm:px-0">
      {/* Header */}
      <div>
        <h1 className="page-header">Today's Attendance</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Live present / absent breakdown for all registered students —{" "}
          <span className="font-medium text-foreground">{today}</span>
        </p>
      </div>

      {/* Refresh bar */}
      <div className="flex flex-wrap items-center gap-3 justify-between rounded-xl border border-border bg-muted/20 px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="h-4 w-4 shrink-0" />
          <span>
            Last refreshed: <span className="text-foreground font-medium">{formatTime(lastRefreshed)}</span>
          </span>
          <span className="text-xs">· Auto-refresh in {countdown}s</span>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void loadData(false)}
          disabled={loading}
          className="gap-2"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh now
        </Button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="stat-card flex items-center gap-4">
          <div className="h-12 w-12 rounded-full bg-accent/20 flex items-center justify-center shrink-0">
            <Users className="h-6 w-6 text-accent" />
          </div>
          <div>
            <p className="text-2xl font-bold text-foreground">{students.length}</p>
            <p className="text-sm text-muted-foreground">Total Registered</p>
          </div>
        </div>

        <div className="stat-card flex items-center gap-4">
          <div className="h-12 w-12 rounded-full bg-success/20 flex items-center justify-center shrink-0">
            <CheckCircle2 className="h-6 w-6 text-success" />
          </div>
          <div>
            <p className="text-2xl font-bold text-success">{presentStudents.length}</p>
            <p className="text-sm text-muted-foreground">Present Today</p>
          </div>
        </div>

        <div className="stat-card flex items-center gap-4">
          <div className="h-12 w-12 rounded-full bg-destructive/20 flex items-center justify-center shrink-0">
            <XCircle className="h-6 w-6 text-destructive" />
          </div>
          <div>
            <p className="text-2xl font-bold text-destructive">{absentStudents.length}</p>
            <p className="text-sm text-muted-foreground">Absent Today</p>
          </div>
        </div>
      </div>

      {/* Attendance progress bar */}
      {students.length > 0 && (
        <div className="stat-card space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground font-medium">Attendance Rate</span>
            <span className="font-bold text-foreground">{presentPct}%</span>
          </div>
          <div className="h-3 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-success transition-all duration-700"
              style={{ width: `${presentPct}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {presentStudents.length} of {students.length} students present
          </p>
        </div>
      )}

      {/* Present / Absent tables */}
      {loading && students.length === 0 ? (
        <div className="flex items-center justify-center gap-3 py-20 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" />
          <span className="text-sm">Loading attendance data…</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Present */}
          <div className="stat-card space-y-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-success shrink-0" />
              <h3 className="section-title text-success">Present ({presentStudents.length})</h3>
            </div>

            {presentStudents.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">
                No students marked present yet for today.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[200px]">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b border-border">
                      <th className="pb-2 pr-2 font-medium">#</th>
                      <th className="pb-2 pr-2 font-medium">Name</th>
                      <th className="pb-2 pr-2 font-medium">Roll No</th>
                      <th className="pb-2 font-medium">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {presentStudents.map((s, i) => {
                      const rec = todayAttendance.find(
                        (r) => r.name.toLowerCase() === s.name.toLowerCase()
                      );
                      return (
                        <tr
                          key={s.roll_no}
                          className="border-b border-border/50 last:border-0 hover:bg-success/5 transition-colors"
                        >
                          <td className="py-2.5 pr-2 text-sm text-muted-foreground">{i + 1}</td>
                          <td className="py-2.5 pr-2 text-sm font-medium text-foreground">
                            <div className="flex items-center gap-1.5">
                              <span className="inline-block h-2 w-2 rounded-full bg-success shrink-0" />
                              {s.name}
                            </div>
                          </td>
                          <td className="py-2.5 pr-2 text-sm text-muted-foreground">{s.roll_no}</td>
                          <td className="py-2.5 text-sm text-muted-foreground whitespace-nowrap">
                            {rec?.time ?? "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Absent */}
          <div className="stat-card space-y-3">
            <div className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-destructive shrink-0" />
              <h3 className="section-title text-destructive">Absent ({absentStudents.length})</h3>
            </div>

            {absentStudents.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">
                🎉 All registered students are present today!
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[200px]">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b border-border">
                      <th className="pb-2 pr-2 font-medium">#</th>
                      <th className="pb-2 pr-2 font-medium">Name</th>
                      <th className="pb-2 font-medium">Roll No</th>
                    </tr>
                  </thead>
                  <tbody>
                    {absentStudents.map((s, i) => (
                      <tr
                        key={s.roll_no}
                        className="border-b border-border/50 last:border-0 hover:bg-destructive/5 transition-colors"
                      >
                        <td className="py-2.5 pr-2 text-sm text-muted-foreground">{i + 1}</td>
                        <td className="py-2.5 pr-2 text-sm font-medium text-foreground">
                          <div className="flex items-center gap-1.5">
                            <span className="inline-block h-2 w-2 rounded-full bg-destructive shrink-0" />
                            {s.name}
                          </div>
                        </td>
                        <td className="py-2.5 text-sm text-muted-foreground">{s.roll_no}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default TodayAttendancePage;
