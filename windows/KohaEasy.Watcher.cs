// koha.nexus for Windows: the shutdown watcher's window (KohaEasy.Watcher.ps1
// loads it with Add-Type; tests/windows_checks.ps1 sends it the messages).
// C# 5 only (the compiler of .NET Framework 4.x).
//
// A hidden top-level window, never shown. Not a message-only window
// (HWND_MESSAGE): those get no broadcast messages, and Windows sends
// WM_QUERYENDSESSION and WM_ENDSESSION to the top-level windows only.
//
//   WM_QUERYENDSESSION  while Koha runs (Armed), the shutdown block reason
//                       is set (ShutdownBlockReasonCreate), and TRUE is
//                       returned at once: the watcher never vetoes a
//                       shutdown, it only asks Windows to wait for it
//   WM_ENDSESSION       wParam TRUE (the session really ends; a shutdown
//                       another program cancelled never gets it):
//                       SessionEnding runs the clean stop, then the block
//                       reason is released (ShutdownBlockReasonDestroy) and
//                       Windows carries on. wParam FALSE: released at once.
//
// Windows shows the reason on its shutdown screen only when the stop takes
// longer than a few seconds, with "Shut down anyway" beside it.

using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

public class KohaShutdownWatcher : NativeWindow, IDisposable
{
    public const int WM_QUERYENDSESSION = 0x11;
    public const int WM_ENDSESSION = 0x16;

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern bool ShutdownBlockReasonCreate(IntPtr hWnd, string reason);
    [DllImport("user32.dll")]
    static extern bool ShutdownBlockReasonDestroy(IntPtr hWnd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern bool ShutdownBlockReasonQuery(IntPtr hWnd, StringBuilder buff, ref uint size);
    [DllImport("kernel32.dll")]
    static extern bool SetProcessShutdownParameters(uint level, uint flags);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CreateProcess(string app, StringBuilder cmd, IntPtr pa, IntPtr ta, bool inherit,
        uint flags, IntPtr env, string dir, ref STARTUPINFO si, out PROCESS_INFORMATION pi);
    [DllImport("kernel32.dll")]
    static extern uint WaitForSingleObject(IntPtr h, uint ms);
    [DllImport("kernel32.dll")]
    static extern bool GetExitCodeProcess(IntPtr h, out uint code);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr h);
    [DllImport("user32.dll")]
    static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct STARTUPINFO {
        public int cb; public string lpReserved; public string lpDesktop; public string lpTitle;
        public int dwX; public int dwY; public int dwXSize; public int dwYSize;
        public int dwXCountChars; public int dwYCountChars; public int dwFillAttribute; public int dwFlags;
        public short wShowWindow; public short cbReserved2; public IntPtr lpReserved2;
        public IntPtr hStdInput; public IntPtr hStdOutput; public IntPtr hStdError;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct PROCESS_INFORMATION { public IntPtr hProcess; public IntPtr hThread; public int pid; public int tid; }

    readonly string reason;
    bool armed;
    bool blocking;
    // Raised on WM_ENDSESSION with wParam TRUE, on the window's thread; the
    // block reason stays until it returns.
    public event EventHandler SessionEnding;
    // Raised on WM_QUERYENDSESSION, after the reason is set (for the log).
    public event EventHandler SessionQuery;

    public KohaShutdownWatcher(string reason) {
        this.reason = reason;
        CreateParams cp = new CreateParams();
        cp.Caption = "Koha shutdown watcher";
        cp.Style = 0;          // no WS_VISIBLE: never on screen
        cp.ExStyle = 0x80;     // WS_EX_TOOLWINDOW: never on the taskbar
        CreateHandle(cp);
    }

    // Asked before the other programs of the session when Windows ends it
    // (the highest level an application may use), so Koha is stopped while
    // WSL and its wsl.exe processes are still there.
    public static bool ShutDownFirst() { return SetProcessShutdownParameters(0x3FF, 0); }

    // Koha runs: the reason is held now, so it is already there when Windows
    // asks; not running: nothing to wait for.
    public bool Armed {
        get { return armed; }
        set { armed = value; if (armed) { Block(); } else { Unblock(); } }
    }
    public bool Blocking { get { return blocking; } }

    public void Block() {
        if (!blocking) { blocking = ShutdownBlockReasonCreate(Handle, reason); }
    }
    public void Unblock() {
        if (blocking) { ShutdownBlockReasonDestroy(Handle); blocking = false; }
    }

    // The reason Windows holds for this window ("" when none).
    public string QueryReason() {
        uint size = 0;
        if (!ShutdownBlockReasonQuery(Handle, null, ref size) || size == 0) { return ""; }
        StringBuilder sb = new StringBuilder((int)size);
        if (!ShutdownBlockReasonQuery(Handle, sb, ref size)) { return ""; }
        return sb.ToString();
    }

    // For the tests: a message to this window, as Windows sends it.
    public int Send(int msg, bool wParam) {
        return (int)SendMessage(Handle, msg, wParam ? (IntPtr)1 : IntPtr.Zero, IntPtr.Zero);
    }

    protected override void WndProc(ref Message m) {
        if (m.Msg == WM_QUERYENDSESSION) {
            if (armed) { Block(); }
            if (SessionQuery != null) { try { SessionQuery(this, EventArgs.Empty); } catch { } }
            m.Result = (IntPtr)1;
            return;
        }
        if (m.Msg == WM_ENDSESSION) {
            // A stop that failed must not keep Windows waiting: the reason
            // is released whatever happened.
            try {
                if (m.WParam != IntPtr.Zero && blocking && SessionEnding != null) { SessionEnding(this, EventArgs.Empty); }
            } catch {
            } finally {
                Unblock();
            }
            m.Result = IntPtr.Zero;
            return;
        }
        base.WndProc(ref m);
    }

    // Runs a program with no console at all (DETACHED_PROCESS), so Windows
    // does not close it with the console programs when the session ends.
    // Returns its exit code, -1 when it is still running after timeoutMs,
    // -2 when it could not be started.
    public static int RunDetached(string commandLine, int timeoutMs) {
        STARTUPINFO si = new STARTUPINFO();
        si.cb = Marshal.SizeOf(typeof(STARTUPINFO));
        PROCESS_INFORMATION pi;
        const uint DETACHED_PROCESS = 0x8, CREATE_NEW_PROCESS_GROUP = 0x200;
        if (!CreateProcess(null, new StringBuilder(commandLine), IntPtr.Zero, IntPtr.Zero, false,
                DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP, IntPtr.Zero, null, ref si, out pi)) { return -2; }
        try {
            if (WaitForSingleObject(pi.hProcess, (uint)timeoutMs) != 0) { return -1; }
            uint code;
            if (!GetExitCodeProcess(pi.hProcess, out code)) { return -2; }
            return (int)code;
        } finally { CloseHandle(pi.hThread); CloseHandle(pi.hProcess); }
    }

    public void Dispose() {
        Unblock();
        DestroyHandle();
    }
}
