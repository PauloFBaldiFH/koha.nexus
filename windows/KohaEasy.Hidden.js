// Koha Easy Installer for Windows: KohaEasy.ps1 with no window at all,
// through Windows Script Host. wscript.exe is a Windows program (no console
// of its own), and WScript.Shell.Run with window style 0 starts PowerShell
// hidden from the start, so Windows Terminal never takes over its console.
// Used when KohaEasy.exe and conhost --headless do not work on this PC.
//   wscript.exe //B //Nologo KohaEasy.Hidden.js <command> [arguments]
// Waits for PowerShell and returns its exit code (the scheduled tasks
// read it). JScript: VBScript is being removed from Windows.
var shell = WScript.CreateObject("WScript.Shell");
var fso = WScript.CreateObject("Scripting.FileSystemObject");
var dir = fso.GetParentFolderName(WScript.ScriptFullName);
var ps = shell.ExpandEnvironmentStrings("%SystemRoot%") + "\\System32\\WindowsPowerShell\\v1.0\\powershell.exe";

// Same rules as KohaEasy.Launcher.Quote (how Windows splits arguments).
function quote(a) {
    if (a.length > 0 && !/[\s"]/.test(a)) { return a; }
    var out = '"', slashes = 0;
    for (var i = 0; i < a.length; i++) {
        var c = a.charAt(i);
        if (c === "\\") { slashes++; continue; }
        if (c === '"') { out += new Array(slashes * 2 + 2).join("\\") + '"'; }
        else { out += new Array(slashes + 1).join("\\") + c; }
        slashes = 0;
    }
    return out + new Array(slashes * 2 + 1).join("\\") + '"';
}

var args = [];
for (var i = 0; i < WScript.Arguments.length; i++) { args.push(quote(WScript.Arguments(i))); }
var cmd = '"' + ps + '" -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + dir + '\\KohaEasy.ps1" ' + args.join(" ");
WScript.Quit(shell.Run(cmd, 0, true));
