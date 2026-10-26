// Launcher do MSIX (KohaMsixEntry.exe). O compilar_msix.ps1 troca
// __PAYLOAD_VERSION__ pela $payloadRevision e compila com o csc do .NET
// Framework (C# 5: sem interpolação de strings nem operador ?.).
//
// Store 10.1.2.10 ("crashes at launch", 1.0.27.0 e 1.0.28.0): o testador abria
// o app, a preparação parava em algum ponto e só aparecia a nossa caixa de
// erro, lida como travamento. Agora, enquanto o Koha não está instalado, o app abre
// uma janela própria: confere os requisitos, explica o que vai acontecer e só
// instala quando a pessoa clica em Instalar. Qualquer parada aparece dentro
// dessa janela, que continua aberta. Nenhuma caixa de erro na abertura.
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Management;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

internal static class KohaMsixEntry
{
    internal const string PayloadVersion = "__PAYLOAD_VERSION__";
    internal const string KohaRoot = @"C:\Koha";
    internal const string LogDir = @"C:\Koha\logs";
    internal const string ResultFile = @"C:\Koha\logs\msix-result.txt";
    internal const string HelpUrl = "https://koha.nexus/";

    // Códigos do Bootstrap-MSIX.ps1: 0 pronto, 3 reiniciar o Windows,
    // 10 parou (motivo em ResultFile), 11 virtualização desligada.
    internal const int CodeRestart = 3;
    internal const int CodeStopped = 10;
    internal const int CodeNoVirtualization = 11;
    internal const int CodeWindowClosed = unchecked((int)0xC000013A);

    [DllImport("user32.dll")]
    private static extern bool SetProcessDPIAware();

    // Português para Windows em português, inglês nos outros (a Store testa em inglês).
    internal static string Text(string pt, string en)
    {
        try
        {
            if (CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "pt") return pt;
        }
        catch { }
        return en;
    }

    internal static string PackageDir
    {
        get { return Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location); }
    }

    internal static string Bootstrap
    {
        get { return Path.Combine(PackageDir, "Bootstrap-MSIX.ps1"); }
    }

    internal static string PowerShell
    {
        get
        {
            string systemDir = Environment.GetFolderPath(Environment.SpecialFolder.System);
            return Path.Combine(systemDir, @"WindowsPowerShell\v1.0\powershell.exe");
        }
    }

    internal static bool HasKohaDistro()
    {
        string wsl = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "wsl.exe");
        if (!File.Exists(wsl)) return false;

        try
        {
            ProcessStartInfo check = new ProcessStartInfo();
            check.FileName = wsl;
            check.Arguments = "--list --quiet";
            check.UseShellExecute = false;
            check.CreateNoWindow = true;
            check.RedirectStandardOutput = true;

            using (Process process = Process.Start(check))
            {
                if (process == null) return false;
                if (!process.WaitForExit(10000))
                {
                    try { process.Kill(); } catch { }
                    try { process.WaitForExit(); } catch { }
                    return false;
                }
                string output = process.StandardOutput.ReadToEnd();
                if (process.ExitCode != 0) return false;

                output = output.Replace("\0", "");
                string[] lines = output.Split(new char[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
                foreach (string line in lines)
                {
                    string name = line.Trim().TrimStart('*').Trim();
                    if (String.Equals(name, "koha", StringComparison.OrdinalIgnoreCase)) return true;
                }
            }
        }
        catch { }
        return false;
    }

    internal static bool IsInstalled()
    {
        string bin = Path.Combine(KohaRoot, "bin");
        string mainScript = Path.Combine(bin, "KohaEasy.ps1");
        string marker = Path.Combine(bin, ".koha-msix-payload-version");

        try
        {
            if (!File.Exists(mainScript) || !File.Exists(marker)) return false;
            string installedVersion = File.ReadAllText(marker).Trim();
            if (!String.Equals(installedVersion, PayloadVersion, StringComparison.Ordinal)) return false;
            return HasKohaDistro();
        }
        catch { return false; }
    }

    internal static string BootstrapArguments(bool hidden)
    {
        return "-NoProfile -ExecutionPolicy Bypass " + (hidden ? "-WindowStyle Hidden " : "") +
            "-File \"" + Bootstrap + "\" -ResultFile \"" + ResultFile + "\"";
    }

    internal static string ReadResult()
    {
        try
        {
            if (File.Exists(ResultFile)) return File.ReadAllText(ResultFile).Trim();
        }
        catch { }
        return "";
    }

    internal static void ClearResult()
    {
        try
        {
            Directory.CreateDirectory(LogDir);
            if (File.Exists(ResultFile)) File.Delete(ResultFile);
        }
        catch { }
    }

    // Koha já instalado: abre o painel sem janela extra, como antes. Devolve
    // null quando deu certo, senão o texto que a janela mostra.
    private static string OpenPanel()
    {
        ClearResult();
        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = PowerShell;
        psi.Arguments = BootstrapArguments(true);
        psi.WorkingDirectory = PackageDir;
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        psi.WindowStyle = ProcessWindowStyle.Hidden;
        try
        {
            using (Process child = Process.Start(psi))
            {
                if (child == null) return Text("O Windows não abriu o PowerShell.", "Windows did not start PowerShell.");
                child.WaitForExit();
                int code = child.ExitCode;
                if (code == 0 || code == CodeWindowClosed) return null;
                string reason = ReadResult();
                if (reason.Length > 0) return reason;
                return Text("O painel fechou com o código ", "The control panel closed with code ") + code + ".";
            }
        }
        catch (Exception ex)
        {
            return ex.Message;
        }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        try { SetProcessDPIAware(); } catch { }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        string problem = null;
        if (File.Exists(Bootstrap) && File.Exists(PowerShell) && IsInstalled())
        {
            problem = OpenPanel();
            if (problem == null) return 0;
        }

        try
        {
            Application.Run(new SetupForm(problem));
        }
        catch (Exception ex)
        {
            // Última rede: a janela não abriu. Mesmo assim, uma explicação, não um "crash".
            MessageBox.Show(Text("A janela do Koha.Nexus não abriu: ", "The Koha.Nexus window did not open: ") + ex.Message +
                "\r\n\r\n" + Text("Registros: ", "Logs: ") + LogDir, "Koha.Nexus", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        return 0;
    }
}

// Um requisito conferido na janela. Level: 0 ok, 1 aviso, 2 impede a instalação.
internal sealed class Check
{
    public int Level;
    public string Text;

    public Check(int level, string text)
    {
        Level = level;
        Text = text;
    }
}

internal static class Requirements
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    private class MemoryStatus
    {
        public uint Length = (uint)Marshal.SizeOf(typeof(MemoryStatus));
        public uint MemoryLoad;
        public ulong TotalPhys;
        public ulong AvailPhys;
        public ulong TotalPageFile;
        public ulong AvailPageFile;
        public ulong TotalVirtual;
        public ulong AvailVirtual;
        public ulong AvailExtendedVirtual;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx([In, Out] MemoryStatus buffer);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct OsVersionInfo
    {
        public int Size;
        public int Major;
        public int Minor;
        public int Build;
        public int Platform;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
        public string ServicePack;
    }

    [DllImport("ntdll.dll", CharSet = CharSet.Unicode)]
    private static extern int RtlGetVersion(ref OsVersionInfo info);

    // Environment.OSVersion diz 6.2 build 9200 (Windows 8) a um programa sem
    // manifesto de compatibilidade, mesmo no Windows 11. RtlGetVersion não mente.
    public static int WindowsBuild()
    {
        try
        {
            OsVersionInfo info = new OsVersionInfo();
            info.Size = Marshal.SizeOf(typeof(OsVersionInfo));
            if (RtlGetVersion(ref info) == 0 && info.Build > 0) return info.Build;
        }
        catch { }
        try
        {
            object value = Microsoft.Win32.Registry.GetValue(@"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion", "CurrentBuildNumber", null);
            int build;
            if (value != null && Int32.TryParse(value.ToString(), out build)) return build;
        }
        catch { }
        return Environment.OSVersion.Version.Build;
    }

    private static string T(string pt, string en)
    {
        return KohaMsixEntry.Text(pt, en);
    }

    // true: ligada; false: todos os processadores dizem desligada no firmware;
    // null: não deu para saber (não bloqueia: o instalador confere de novo).
    public static bool? Virtualization()
    {
        try
        {
            using (ManagementObjectSearcher cs = new ManagementObjectSearcher("SELECT HypervisorPresent FROM Win32_ComputerSystem"))
            {
                foreach (ManagementBaseObject o in cs.Get())
                {
                    object value = o["HypervisorPresent"];
                    if (value is bool && (bool)value) return true;
                }
            }
            bool any = false;
            bool on = false;
            using (ManagementObjectSearcher cpu = new ManagementObjectSearcher("SELECT VirtualizationFirmwareEnabled FROM Win32_Processor"))
            {
                foreach (ManagementBaseObject o in cpu.Get())
                {
                    object value = o["VirtualizationFirmwareEnabled"];
                    if (value is bool)
                    {
                        any = true;
                        if ((bool)value) on = true;
                    }
                }
            }
            if (!any) return null;
            return on;
        }
        catch { return null; }
    }

    // Os mesmos limites do Get-KohaPreflight (windows\KohaEasy.Install.psm1).
    public static Check[] Run(out bool? virtualization)
    {
        Check[] rows = new Check[6];
        int build = WindowsBuild();
        rows[0] = new Check(build >= 19041 ? 0 : 2,
            T("Windows 10 versão 2004 ou mais nova, ou Windows 11 (este PC: build ", "Windows 10 version 2004 or later, or Windows 11 (this PC: build ") + build + ")");
        rows[1] = new Check(Environment.Is64BitOperatingSystem ? 0 : 2, T("Windows de 64 bits", "64-bit Windows"));

        double memGB = 0;
        try
        {
            MemoryStatus status = new MemoryStatus();
            if (GlobalMemoryStatusEx(status)) memGB = Math.Round(status.TotalPhys / 1073741824.0, 1);
        }
        catch { }
        string mem = T("Memória: pelo menos 8 GB, 12 GB recomendado (este PC: ", "Memory: at least 8 GB, 12 GB recommended (this PC: ") +
            memGB.ToString("0.#", CultureInfo.CurrentCulture) + " GB)";
        rows[2] = new Check(memGB == 0 ? 1 : (memGB < 7.5 ? 2 : (memGB < 11.5 ? 1 : 0)), mem);

        double freeGB = 0;
        try { freeGB = Math.Round(new DriveInfo("C").AvailableFreeSpace / 1073741824.0, 1); }
        catch { }
        string disk = T("Espaço livre no disco C: pelo menos 10 GB, 20 GB recomendado (livre: ", "Free space on drive C: at least 10 GB, 20 GB recommended (free: ") +
            freeGB.ToString("0.#", CultureInfo.CurrentCulture) + " GB)";
        rows[3] = new Check(freeGB < 10 ? 2 : (freeGB < 20 ? 1 : 0), disk);

        virtualization = Virtualization();
        if (virtualization == true)
            rows[4] = new Check(0, T("Virtualização ligada na BIOS/UEFI", "Virtualization turned on in BIOS/UEFI"));
        else if (virtualization == false)
            rows[4] = new Check(2, T("Virtualização desligada na BIOS/UEFI (Intel VT-x ou AMD-V/SVM): ligue-a para usar o WSL 2", "Virtualization is off in BIOS/UEFI (Intel VT-x or AMD-V/SVM): turn it on to use WSL 2"));
        else
            rows[4] = new Check(1, T("Não deu para ler o estado da virtualização; a instalação confere de novo", "Could not read the virtualization state; setup checks it again"));

        string wsl = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "wsl.exe");
        rows[5] = new Check(0, File.Exists(wsl)
            ? T("WSL presente; a instalação cria o Debian do Koha", "WSL is present; setup creates the Koha Debian")
            : T("WSL 2 ainda não instalado; a instalação liga o WSL 2 (pode pedir para reiniciar o Windows)", "WSL 2 is not installed yet; setup turns it on (it may ask you to restart Windows)"));
        return rows;
    }
}

internal sealed class SetupForm : Form
{
    private readonly FlowLayoutPanel checksPanel = new FlowLayoutPanel();
    private readonly Label status = new Label();
    private readonly Button install = new Button();
    private readonly Button firmware = new Button();
    private readonly Button logs = new Button();
    private readonly Button close = new Button();
    private bool canInstall;
    private bool installed;
    private bool running;

    private static string T(string pt, string en)
    {
        return KohaMsixEntry.Text(pt, en);
    }

    public SetupForm(string problem)
    {
        Text = "Koha.Nexus";
        Font = new Font("Segoe UI", 10f);
        AutoScaleMode = AutoScaleMode.Dpi;
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;
        AutoSize = true;
        AutoSizeMode = AutoSizeMode.GrowAndShrink;
        BackColor = Color.White;
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }

        TableLayoutPanel root = new TableLayoutPanel();
        root.ColumnCount = 1;
        root.AutoSize = true;
        root.AutoSizeMode = AutoSizeMode.GrowAndShrink;
        root.Padding = new Padding(24, 20, 24, 16);
        root.MaximumSize = new Size(720, 0);
        Controls.Add(root);

        Label title = new Label();
        title.Text = "Koha.Nexus";
        title.Font = new Font("Segoe UI Semibold", 18f);
        title.AutoSize = true;
        root.Controls.Add(title);

        Label intro = new Label();
        intro.AutoSize = true;
        intro.MaximumSize = new Size(660, 0);
        intro.Margin = new Padding(3, 4, 3, 12);
        intro.Text = T("Instala e administra o Koha, sistema de gestão de bibliotecas, neste computador, dentro do WSL 2 (Debian). " +
            "A instalação pede permissão de administrador uma vez, baixa o Debian e o Koha da internet e pode levar de 30 a 60 minutos. " +
            "O progresso aparece numa janela de console; depois o painel do Koha abre no Terminal do Windows.",
            "Installs and manages Koha, the library management system, on this computer inside WSL 2 (Debian). " +
            "Setup asks for administrator permission once, downloads Debian and Koha from the internet, and can take 30 to 60 minutes. " +
            "Progress shows in a console window; then the Koha control panel opens in Windows Terminal.");
        root.Controls.Add(intro);

        Label reqTitle = new Label();
        reqTitle.Text = T("Requisitos deste computador", "This computer's requirements");
        reqTitle.Font = new Font("Segoe UI Semibold", 11f);
        reqTitle.AutoSize = true;
        root.Controls.Add(reqTitle);

        checksPanel.FlowDirection = FlowDirection.TopDown;
        checksPanel.WrapContents = false;
        checksPanel.AutoSize = true;
        checksPanel.AutoSizeMode = AutoSizeMode.GrowAndShrink;
        checksPanel.Margin = new Padding(3, 4, 3, 8);
        root.Controls.Add(checksPanel);

        status.AutoSize = true;
        status.MaximumSize = new Size(660, 0);
        status.Margin = new Padding(3, 8, 3, 12);
        root.Controls.Add(status);

        FlowLayoutPanel buttons = new FlowLayoutPanel();
        buttons.AutoSize = true;
        buttons.AutoSizeMode = AutoSizeMode.GrowAndShrink;
        buttons.WrapContents = true;
        buttons.MaximumSize = new Size(680, 0);
        foreach (Button b in new Button[] { install, firmware, logs, close })
        {
            b.AutoSize = true;
            b.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            b.Padding = new Padding(10, 4, 10, 4);
            b.Margin = new Padding(0, 0, 8, 0);
            b.UseVisualStyleBackColor = true;
            buttons.Controls.Add(b);
        }
        install.Font = new Font("Segoe UI Semibold", 10f);
        firmware.Text = T("Abrir a BIOS/UEFI", "Open BIOS/UEFI settings");
        logs.Text = T("Abrir os registros", "Open logs");
        close.Text = T("Fechar", "Close");
        install.Click += OnInstall;
        firmware.Click += OnFirmware;
        logs.Click += delegate { OpenLogs(); };
        close.Click += delegate { Close(); };
        root.Controls.Add(buttons);

        LinkLabel help = new LinkLabel();
        help.Text = T("Manual e ajuda: ", "Manual and help: ") + KohaMsixEntry.HelpUrl;
        help.AutoSize = true;
        help.Margin = new Padding(3, 12, 3, 0);
        help.LinkClicked += delegate { Open(KohaMsixEntry.HelpUrl); };
        root.Controls.Add(help);

        AcceptButton = install;
        CancelButton = close;
        UpdateView(problem);
    }

    private void UpdateView(string problem)
    {
        bool? virtualization;
        Check[] rows = Requirements.Run(out virtualization);
        checksPanel.SuspendLayout();
        checksPanel.Controls.Clear();
        canInstall = true;
        foreach (Check row in rows)
        {
            Label line = new Label();
            line.AutoSize = true;
            line.MaximumSize = new Size(640, 0);
            line.Margin = new Padding(0, 2, 0, 2);
            string mark = row.Level == 0 ? "\u2714" : (row.Level == 1 ? "!" : "\u2716");
            line.Text = mark + "  " + row.Text;
            line.ForeColor = row.Level == 0 ? Color.FromArgb(16, 112, 64) : (row.Level == 1 ? Color.FromArgb(150, 90, 0) : Color.FromArgb(180, 30, 30));
            checksPanel.Controls.Add(line);
            if (row.Level == 2) canInstall = false;
        }
        checksPanel.ResumeLayout();

        firmware.Visible = virtualization == false;
        installed = File.Exists(KohaMsixEntry.Bootstrap) && KohaMsixEntry.IsInstalled();
        install.Text = installed ? T("Abrir o painel do Koha", "Open the Koha control panel") : T("Instalar o Koha.Nexus", "Install Koha.Nexus");
        install.Enabled = canInstall && !running;

        if (!File.Exists(KohaMsixEntry.Bootstrap) || !File.Exists(KohaMsixEntry.PowerShell))
        {
            install.Enabled = false;
            SetStatus(T("Falta um arquivo do aplicativo. Reinstale o Koha.Nexus pela Microsoft Store.", "A file of the app is missing. Reinstall Koha.Nexus from the Microsoft Store."), 2);
        }
        else if (problem != null)
            SetStatus(T("A última tentativa parou: ", "The last attempt stopped: ") + problem + "\r\n" +
                T("Corrija o que a mensagem diz e clique no botão de novo. Registros em ", "Fix what the message says and click the button again. Logs are in ") + KohaMsixEntry.LogDir + ".", 1);
        else if (!canInstall)
            SetStatus(T("Este computador ainda não atende aos requisitos marcados com \u2716. Nada foi instalado.", "This computer does not meet the requirements marked \u2716 yet. Nothing was installed."), 1);
        else if (installed)
            SetStatus(T("O Koha.Nexus está instalado.", "Koha.Nexus is installed."), 0);
        else
            SetStatus(T("Pronto para instalar. Clique em Instalar para começar.", "Ready to install. Click Install to begin."), 0);
    }

    private void SetStatus(string text, int level)
    {
        status.Text = text;
        status.ForeColor = level == 0 ? Color.FromArgb(32, 32, 32) : (level == 1 ? Color.FromArgb(150, 90, 0) : Color.FromArgb(180, 30, 30));
    }

    private void OnInstall(object sender, EventArgs e)
    {
        if (running) return;
        if (installed)
        {
            RunBootstrap(false);
            return;
        }
        RunBootstrap(true);
    }

    // Instalar: o Bootstrap roda elevado (um pedido do UAC) numa janela de
    // console visível; esta janela espera numa thread e mostra o resultado.
    private void RunBootstrap(bool elevated)
    {
        KohaMsixEntry.ClearResult();
        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = KohaMsixEntry.PowerShell;
        psi.Arguments = KohaMsixEntry.BootstrapArguments(!elevated);
        psi.WorkingDirectory = KohaMsixEntry.PackageDir;
        if (elevated)
        {
            psi.UseShellExecute = true;
            psi.Verb = "runas";
            psi.WindowStyle = ProcessWindowStyle.Normal;
        }
        else
        {
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
        }

        Process child;
        try
        {
            child = Process.Start(psi);
        }
        catch (Win32Exception ex)
        {
            if (ex.NativeErrorCode == 1223)
                SetStatus(T("A permissão de administrador foi recusada, ou esta conta não é de administrador. Nada foi alterado. " +
                    "Clique em Instalar de novo e responda Sim no aviso do Windows (ou entre com uma conta de administrador).",
                    "Administrator permission was declined, or this account is not an administrator. Nothing was changed. " +
                    "Click Install again and answer Yes in the Windows prompt (or sign in with an administrator account)."), 1);
            else
                SetStatus(T("O Windows não abriu a instalação: ", "Windows did not start setup: ") + ex.Message, 1);
            return;
        }
        catch (Exception ex)
        {
            SetStatus(T("O Windows não abriu a instalação: ", "Windows did not start setup: ") + ex.Message, 1);
            return;
        }
        if (child == null)
        {
            SetStatus(T("O Windows não abriu a instalação.", "Windows did not start setup."), 1);
            return;
        }

        running = true;
        install.Enabled = false;
        SetStatus(elevated
            ? T("Instalando... Acompanhe e responda as perguntas na janela de console. Esta janela mostra o resultado no fim.",
                "Installing... Follow and answer the questions in the console window. This window shows the result at the end.")
            : T("Abrindo o painel do Koha...", "Opening the Koha control panel..."), 0);

        Thread wait = new Thread(delegate()
        {
            int code;
            try
            {
                child.WaitForExit();
                code = child.ExitCode;
            }
            catch { code = -1; }
            finally { child.Dispose(); }
            try { BeginInvoke(new Action<int, bool>(Finished), code, elevated); } catch { }
        });
        wait.IsBackground = true;
        wait.Start();
    }

    private void Finished(int code, bool elevated)
    {
        running = false;
        string reason = KohaMsixEntry.ReadResult();
        if (code == 0)
        {
            UpdateView(null);
            SetStatus(elevated
                ? T("A preparação do Windows terminou. O painel do Koha continua a instalação do servidor no Terminal do Windows.",
                    "Windows preparation is complete. The Koha control panel continues the server setup in Windows Terminal.")
                : T("O painel do Koha foi aberto.", "The Koha control panel is open."), 0);
            return;
        }
        if (code == KohaMsixEntry.CodeRestart)
        {
            UpdateView(null);
            SetStatus(T("Reinicie o Windows para terminar de ligar o WSL 2. Depois abra o Koha.Nexus de novo e clique em Instalar para continuar.",
                "Restart Windows to finish turning on WSL 2. Then open Koha.Nexus again and click Install to continue."), 1);
            return;
        }
        if (code == KohaMsixEntry.CodeWindowClosed)
        {
            UpdateView(T("a janela de console foi fechada antes do fim.", "the console window was closed before the end."));
            return;
        }
        if (code == KohaMsixEntry.CodeNoVirtualization && reason.Length == 0)
            reason = T("a virtualização está desligada na BIOS/UEFI.", "virtualization is off in BIOS/UEFI.");
        if (reason.Length == 0)
            reason = T("código ", "code ") + code + ".";
        UpdateView(reason);
    }

    private void OnFirmware(object sender, EventArgs e)
    {
        DialogResult answer = MessageBox.Show(this,
            T("O Windows vai reiniciar e abrir as configurações da BIOS/UEFI. Salve seus arquivos antes. Procure Intel Virtualization Technology (VT-x) ou SVM/AMD-V, ative e salve (geralmente F10). Continuar?",
                "Windows will restart into the BIOS/UEFI settings. Save your work first. Look for Intel Virtualization Technology (VT-x) or SVM/AMD-V, turn it on and save (usually F10). Continue?"),
            "Koha.Nexus", MessageBoxButtons.YesNo, MessageBoxIcon.Question);
        if (answer != DialogResult.Yes) return;
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "shutdown.exe");
            psi.Arguments = "/r /fw /t 0";
            psi.UseShellExecute = true;
            psi.Verb = "runas";
            psi.WindowStyle = ProcessWindowStyle.Hidden;
            Process.Start(psi);
        }
        catch (Exception)
        {
            SetStatus(T("Não deu para abrir a BIOS/UEFI daqui. Use Configurações > Sistema > Recuperação > Inicialização avançada > Reiniciar agora > Solução de problemas > Opções avançadas > Configurações de Firmware UEFI.",
                "Could not open BIOS/UEFI from here. Use Settings > System > Recovery > Advanced startup > Restart now > Troubleshoot > Advanced options > UEFI Firmware Settings."), 1);
        }
    }

    private void OpenLogs()
    {
        try { Directory.CreateDirectory(KohaMsixEntry.LogDir); } catch { }
        Open(KohaMsixEntry.LogDir);
    }

    private static void Open(string target)
    {
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = target;
            psi.UseShellExecute = true;
            Process.Start(psi);
        }
        catch { }
    }
}
