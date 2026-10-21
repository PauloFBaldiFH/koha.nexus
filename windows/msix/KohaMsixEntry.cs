using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

internal static class KohaMsixEntry
{
    private const string PayloadVersion = "1.0.25.0-msix-v17";

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBox(IntPtr hWnd, string text, string caption, uint type);

    private static void ShowError(string text)
    {
        try { MessageBox(IntPtr.Zero, text, "Koha.Nexus", 0x10); } catch { }
    }

    private static bool HasKohaDistro()
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

    private static bool NeedsVisibleSetup()
    {
        string bin = @"C:\Koha\bin";
        string mainScript = Path.Combine(bin, "KohaEasy.ps1");
        string marker = Path.Combine(bin, ".koha-msix-payload-version");

        try
        {
            if (!File.Exists(mainScript) || !File.Exists(marker)) return true;
            string installedVersion = File.ReadAllText(marker).Trim();
            if (!String.Equals(installedVersion, PayloadVersion, StringComparison.Ordinal)) return true;
            return !HasKohaDistro();
        }
        catch { return true; }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string packageDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string bootstrap = Path.Combine(packageDir, "Bootstrap-MSIX.ps1");
        if (!File.Exists(bootstrap))
        {
            ShowError("O arquivo de inicialização não foi encontrado dentro do pacote MSIX:\r\n" + bootstrap);
            return 2;
        }

        string systemDir = Environment.GetFolderPath(Environment.SpecialFolder.System);
        string powershell = Path.Combine(systemDir, @"WindowsPowerShell\v1.0\powershell.exe");
        if (!File.Exists(powershell))
        {
            ShowError("O Windows PowerShell 5.1 não foi encontrado:\r\n" + powershell);
            return 3;
        }

        // Primeira instalação, payload desatualizado ou distribuição WSL ausente:
        // mostrar o terminal para que o progresso e eventuais erros não fiquem ocultos.
        // Quando já está tudo instalado, manter a inicialização silenciosa do painel.
        bool visibleSetup = NeedsVisibleSetup();

        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = powershell;
        psi.Arguments = "-NoProfile -ExecutionPolicy Bypass " +
            (visibleSetup ? "" : "-WindowStyle Hidden ") +
            "-File \"" + bootstrap + "\"";
        psi.WorkingDirectory = packageDir;
        psi.UseShellExecute = false;
        psi.CreateNoWindow = !visibleSetup;
        psi.WindowStyle = visibleSetup ? ProcessWindowStyle.Normal : ProcessWindowStyle.Hidden;

        try
        {
            using (Process child = Process.Start(psi))
            {
                if (child == null)
                {
                    ShowError("O Windows não conseguiu iniciar o processo de inicialização do Koha.Nexus.");
                    return 4;
                }
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch (Exception ex)
        {
            ShowError("Não foi possível iniciar o Koha.Nexus.\r\n\r\n" + ex.Message +
                "\r\n\r\nTente executar novamente. Se o problema continuar, consulte C:\\Koha\\logs\\msix-bootstrap.log.");
            return 1;
        }
    }
}