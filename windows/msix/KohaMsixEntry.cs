using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

internal static class KohaMsixEntry
{
    private const string PayloadVersion = "1.0.28.0-msix-v20";

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBox(IntPtr hWnd, string text, string caption, uint type);

    private static void ShowError(string text)
    {
        try { MessageBox(IntPtr.Zero, text, "Koha.Nexus", 0x10); } catch { }
    }

    // Portugues para Windows em portugues, ingles nos outros (a Store testa em ingles).
    private static string Text(string pt, string en)
    {
        try
        {
            if (CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "pt") return pt;
        }
        catch { }
        return en;
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
            ShowError(Text("O arquivo de inicialização não foi encontrado dentro do pacote MSIX:\r\n",
                "The startup file was not found inside the MSIX package:\r\n") + bootstrap);
            return 2;
        }

        string systemDir = Environment.GetFolderPath(Environment.SpecialFolder.System);
        string powershell = Path.Combine(systemDir, @"WindowsPowerShell\v1.0\powershell.exe");
        if (!File.Exists(powershell))
        {
            ShowError(Text("O Windows PowerShell 5.1 não foi encontrado:\r\n",
                "Windows PowerShell 5.1 was not found:\r\n") + powershell);
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
                    ShowError(Text("O Windows não conseguiu iniciar o processo de inicialização do Koha.Nexus.",
                        "Windows could not start the Koha.Nexus startup process."));
                    return 4;
                }
                child.WaitForExit();
                int code = child.ExitCode;
                // 0: tudo certo; 10: o bootstrap ja mostrou o erro; 0xC000013A: a
                // pessoa fechou a janela. Outro codigo e uma falha antes ou fora do
                // try do bootstrap (politica de execucao, PowerShell que nao abre):
                // sem este aviso o app so piscaria e fecharia.
                if (code != 0 && code != 10 && code != unchecked((int)0xC000013A))
                {
                    ShowError(Text("O Koha.Nexus fechou de forma inesperada (código " + code + ").\r\n\r\nConsulte C:\\Koha\\logs\\msix-bootstrap.log.",
                        "Koha.Nexus closed unexpectedly (code " + code + ").\r\n\r\nSee C:\\Koha\\logs\\msix-bootstrap.log."));
                }
                return code;
            }
        }
        catch (Exception ex)
        {
            ShowError(Text("Não foi possível iniciar o Koha.Nexus.\r\n\r\n", "Koha.Nexus could not be started.\r\n\r\n") + ex.Message +
                Text("\r\n\r\nTente executar novamente. Se o problema continuar, consulte C:\\Koha\\logs\\msix-bootstrap.log.",
                    "\r\n\r\nTry again. If the problem continues, see C:\\Koha\\logs\\msix-bootstrap.log."));
            return 1;
        }
    }
}