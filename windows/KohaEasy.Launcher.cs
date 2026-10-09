// koha.nexus for Windows: koha.nexus.exe.
//
// Built on this PC by the installer (KohaEasy.Core.psm1, Install-KohaLauncher)
// with the C# compiler that ships with Windows (.NET Framework 4), so it is
// never downloaded: no SmartScreen question, and this source is what runs.
// C# 5 only (the compiler of .NET Framework 4.x).
//
//   koha.nexus.exe <command> [options]   runs "KohaEasy.ps1 <command> [options]"
//                                       in Windows PowerShell 5.1 with no
//                                       console window at all, waits for it
//                                       and returns its exit code
//   koha.nexus.exe --self-test            exit 0 (the installer checks that
//                                       Windows lets it run)
//
// It is a Windows (GUI) program, so Windows never opens a console or a
// Windows Terminal window for it, and PowerShell is started with
// CREATE_NO_WINDOW. The Koha icon is inside the file.
//
// KohaEasy.Native, in the same file, is loaded by the PowerShell side: the
// Koha identity on the taskbar (AppUserModelID) for the Koha window, and on
// the shortcuts, so the taskbar groups the window as Koha and Windows
// notifications say Koha.

using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

[assembly: AssemblyTitle("Koha")]
[assembly: AssemblyDescription("koha.nexus for Windows")]
[assembly: AssemblyProduct("koha.nexus")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

namespace KohaEasy
{
    public static class Launcher
    {
        [STAThread]
        public static int Main(string[] args)
        {
            if (args.Length == 1 && args[0] == "--self-test") { return 0; }
            string dir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string script = Path.Combine(dir, "KohaEasy.ps1");
            string root = Environment.GetEnvironmentVariable("SystemRoot");
            if (string.IsNullOrEmpty(root)) { root = @"C:\Windows"; }
            string ps = Path.Combine(root, @"System32\WindowsPowerShell\v1.0\powershell.exe");
            ProcessStartInfo psi = new ProcessStartInfo(ps, BuildArguments(script, args));
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.WorkingDirectory = dir;
            // Started from a click (the Koha icon), this program may bring a
            // window to the front; PowerShell, started by it, gets the same
            // right, so an open Koha window comes forward instead of only
            // flashing on the taskbar.
            Native.AllowForeground();
            try
            {
                using (Process p = Process.Start(psi))
                {
                    p.WaitForExit();
                    return p.ExitCode;
                }
            }
            catch (Exception e)
            {
                Log(dir, "koha.nexus.exe could not start PowerShell: " + e.Message);
                return 1;
            }
        }

        // -NoProfile -ExecutionPolicy Bypass -File "<script>" <args...>
        public static string BuildArguments(string script, string[] args)
        {
            StringBuilder sb = new StringBuilder("-NoProfile -ExecutionPolicy Bypass -File ");
            sb.Append(Quote(script));
            foreach (string a in args)
            {
                sb.Append(' ');
                sb.Append(Quote(a));
            }
            return sb.ToString();
        }

        // One argument as Windows programs read it back (CommandLineToArgvW).
        public static string Quote(string a)
        {
            if (a == null) { a = ""; }
            if (a.Length > 0 && a.IndexOfAny(new char[] { ' ', '\t', '"' }) < 0) { return a; }
            StringBuilder sb = new StringBuilder("\"");
            int slashes = 0;
            foreach (char c in a)
            {
                if (c == '\\') { slashes++; continue; }
                if (c == '"')
                {
                    sb.Append('\\', slashes * 2 + 1);
                    sb.Append('"');
                }
                else
                {
                    sb.Append('\\', slashes);
                    sb.Append(c);
                }
                slashes = 0;
            }
            sb.Append('\\', slashes * 2);
            sb.Append('"');
            return sb.ToString();
        }

        // C:\Koha\logs\koha-yyyyMMdd.log, the log of the PowerShell side.
        static void Log(string dir, string message)
        {
            try
            {
                string logs = Path.Combine(Path.GetDirectoryName(dir), "logs");
                Directory.CreateDirectory(logs);
                string file = Path.Combine(logs, "koha-" + DateTime.Now.ToString("yyyyMMdd") + ".log");
                File.AppendAllText(file, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " | " + message + Environment.NewLine, new UTF8Encoding(false));
            }
            catch { }
        }
    }

    public static class Native
    {
        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        static extern int SetCurrentProcessExplicitAppUserModelID(string appId);

        [DllImport("ole32.dll")]
        static extern int PropVariantClear(ref PropVariant pvar);

        [DllImport("shell32.dll")]
        static extern void SHChangeNotify(int eventId, uint flags, IntPtr item1, IntPtr item2);

        [DllImport("user32.dll")]
        static extern bool AllowSetForegroundWindow(int processId);

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        static extern IntPtr FindWindow(string className, string windowName);

        [DllImport("user32.dll")]
        static extern bool IsIconic(IntPtr hwnd);

        [DllImport("user32.dll")]
        static extern bool ShowWindow(IntPtr hwnd, int cmd);

        [DllImport("user32.dll")]
        static extern bool SetForegroundWindow(IntPtr hwnd);

        public static void AllowForeground()
        {
            try { AllowSetForegroundWindow(-1); } catch { } // ASFW_ANY
        }

        // The window titled title restored (when minimized) and in front.
        // False when there is no such window.
        public static bool FocusWindow(string title)
        {
            IntPtr hwnd = FindWindow(null, title);
            if (hwnd == IntPtr.Zero) { return false; }
            if (IsIconic(hwnd)) { ShowWindow(hwnd, 9); } // SW_RESTORE
            SetForegroundWindow(hwnd);
            return true;
        }

        [DllImport("dwmapi.dll")]
        static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);

        // A dark title bar on a window (Windows 10 1809 and later; attribute
        // 20 since 20H1, 19 before). False where Windows has neither.
        public static bool SetDarkTitleBar(IntPtr hwnd)
        {
            int on = 1;
            if (DwmSetWindowAttribute(hwnd, 20, ref on, 4) >= 0) { return true; }
            return DwmSetWindowAttribute(hwnd, 19, ref on, 4) >= 0;
        }

        // This process's windows group on the taskbar under appId.
        public static bool SetProcessAppId(string appId)
        {
            return SetCurrentProcessExplicitAppUserModelID(appId) >= 0;
        }

        // System.AppUserModel.ID of a .lnk file: a pinned Koha window and
        // Koha's notifications are tied to this shortcut (its name and icon).
        public static void SetShortcutAppId(string lnkPath, string appId)
        {
            object link = new CShellLink();
            try
            {
                IPersistFile file = (IPersistFile)link;
                file.Load(lnkPath, 2); // STGM_READWRITE
                IPropertyStore store = (IPropertyStore)link;
                PropertyKey key = new PropertyKey();
                key.fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");
                key.pid = 5;
                PropVariant value = new PropVariant();
                value.vt = 31; // VT_LPWSTR
                value.p1 = Marshal.StringToCoTaskMemUni(appId);
                try
                {
                    Check(store.SetValue(ref key, ref value));
                    Check(store.Commit());
                }
                finally
                {
                    PropVariantClear(ref value);
                }
                file.Save(lnkPath, true);
            }
            finally
            {
                Marshal.ReleaseComObject(link);
            }
        }

        // Tells Explorer and the taskbar that icons changed (SHCNE_ASSOCCHANGED,
        // SHCNF_FLUSH), so new or rewritten Koha shortcuts are drawn again
        // instead of from an icon cache entry made before they existed.
        public static void RefreshShellIcons()
        {
            SHChangeNotify(0x08000000, 0x1000, IntPtr.Zero, IntPtr.Zero);
        }

        // A program shortcut written through the shell's own IShellLink, the
        // second way when WScript.Shell cannot write one on this PC.
        public static void CreateShortcut(string lnkPath, string target, string arguments, string workingDirectory, string icon)
        {
            object link = new CShellLink();
            try
            {
                IShellLinkW l = (IShellLinkW)link;
                l.SetPath(target);
                l.SetArguments(arguments ?? "");
                l.SetWorkingDirectory(workingDirectory ?? "");
                if (!string.IsNullOrEmpty(icon)) { l.SetIconLocation(icon, 0); }
                ((IPersistFile)link).Save(lnkPath, true);
            }
            finally
            {
                Marshal.ReleaseComObject(link);
            }
        }

        static void Check(int hr)
        {
            if (hr < 0) { Marshal.ThrowExceptionForHR(hr); }
        }

        [ComImport, Guid("00021401-0000-0000-C000-000000000046"), ClassInterface(ClassInterfaceType.None)]
        class CShellLink { }

        [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("000214F9-0000-0000-C000-000000000046")]
        interface IShellLinkW
        {
            void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder file, int size, IntPtr findData, uint flags);
            void GetIDList(out IntPtr idList);
            void SetIDList(IntPtr idList);
            void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder name, int size);
            void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string name);
            void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder dir, int size);
            void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string dir);
            void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder args, int size);
            void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string args);
            void GetHotkey(out short hotkey);
            void SetHotkey(short hotkey);
            void GetShowCmd(out int showCmd);
            void SetShowCmd(int showCmd);
            void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder iconPath, int size, out int icon);
            void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string iconPath, int icon);
            void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string relPath, int reserved);
            void Resolve(IntPtr hwnd, int flags);
            void SetPath([MarshalAs(UnmanagedType.LPWStr)] string file);
        }

        [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
        interface IPropertyStore
        {
            [PreserveSig] int GetCount(out uint count);
            [PreserveSig] int GetAt(uint index, out PropertyKey key);
            [PreserveSig] int GetValue(ref PropertyKey key, out PropVariant value);
            [PreserveSig] int SetValue(ref PropertyKey key, ref PropVariant value);
            [PreserveSig] int Commit();
        }

        [StructLayout(LayoutKind.Sequential, Pack = 4)]
        struct PropertyKey
        {
            public Guid fmtid;
            public uint pid;
        }

        // PROPVARIANT: 16 bytes on 32-bit Windows, 24 on 64-bit.
        [StructLayout(LayoutKind.Sequential)]
        struct PropVariant
        {
            public ushort vt;
            public ushort r1;
            public ushort r2;
            public ushort r3;
            public IntPtr p1;
            public IntPtr p2;
        }
    }
}
