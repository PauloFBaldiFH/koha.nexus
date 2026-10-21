#Requires -Version 5.1
param(
    [string]$Branch = 'feature/windows-msix-1.0.25.0',
    [string]$Base = 'main'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Run-Command {
    param([string]$Exe, [string[]]$Args)
    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
        throw ("Comando falhou ({0}): {1} {2}" -f $LASTEXITCODE, $Exe, ($Args -join ' '))
    }
}

try {
    $here = $PSScriptRoot
    $root = (Resolve-Path -LiteralPath (Join-Path $here '..\..')).Path
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Instale o Git for Windows.' }
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Instale o GitHub CLI (gh).' }
    Push-Location $root
    try {
        $actualRoot = (& git rev-parse --show-toplevel 2>$null).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'O diretório não é um repositório Git.' }
        if ([IO.Path]::GetFullPath($actualRoot).TrimEnd('\','/') -ne [IO.Path]::GetFullPath($root).TrimEnd('\','/')) {
            throw 'A pasta windows/msix deve estar diretamente dentro da raiz do repositório.'
        }
        $remote = (& git remote get-url origin).Trim()
        if ($LASTEXITCODE -ne 0 -or $remote -notmatch '(?i)(github\.com[:/])PauloFBaldiFH/koha\.nexus(\.git)?$') {
            throw "O remoto origin não aponta para PauloFBaldiFH/koha.nexus: $remote"
        }
        Run-Command -Exe 'gh' -Args @('auth','status')
        $current = (& git branch --show-current).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Não foi possível ler a branch atual.' }
        if ($current -ne $Base -and $current -ne $Branch) {
            throw "Branch atual é '$current'. Mude para '$Base' antes de publicar."
        }
        # Nunca inclua alterações locais de outras partes do projeto no PR.
        $changes = @(& git status --porcelain=v1 -uall)
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao verificar o estado do Git.' }
        $foreign = @($changes | Where-Object { $_ -notmatch '^...windows/msix(?:/|\\|$)' })
        if ($foreign.Count -gt 0) {
            throw ('Existem alterações fora de windows/msix. Resolva antes para evitar publicar arquivos por engano: ' + ($foreign -join '; '))
        }
        if ($current -eq $Base) {
            # Uma branch local existente deve ser examinada manualmente.
            & git show-ref --verify --quiet ("refs/heads/{0}" -f $Branch)
            if ($LASTEXITCODE -eq 0) { throw "A branch '$Branch' já existe localmente; revise antes de continuar." }
            Run-Command -Exe 'git' -Args @('switch','-c',$Branch)
        }
        Run-Command -Exe 'git' -Args @('add','--','windows/msix/README.md','windows/msix/compilar_msix.ps1','windows/msix/KohaNexusIcon.ico','windows/msix/KohaNexusLogo.png','windows/msix/publicar_pr.ps1')
        & git diff --cached --quiet
        if ($LASTEXITCODE -ne 0) {
            Run-Command -Exe 'git' -Args @('commit','-m','build(windows): add MSIX packaging 1.0.25.0')
        } else {
            Write-Host 'Arquivos já commitados; seguindo para o push.' -ForegroundColor Yellow
        }
        Run-Command -Exe 'git' -Args @('push','-u','origin',$Branch)
        
        $existingPr = & gh pr list --repo 'PauloFBaldiFH/koha.nexus' --head $Branch --state open --json url --jq '.[0].url'
        if ($LASTEXITCODE -ne 0) { throw 'Erro ao consultar PRs no GitHub.' }
        if ($existingPr -and ([string]$existingPr).Trim()) {
            Write-Host ('PR existente: ' + [string]$existingPr) -ForegroundColor Green
        } else {
            $body = 'Adiciona o compilador MSIX 1.0.25.0 (v17), imagens e documentacao em windows/msix/. Preserva o icon original da bandeja e o Inno Setup. Fluxo de dois terminais requer validacao no Windows antes do merge.'
            Run-Command -Exe 'gh' -Args @('pr','create','--draft','--repo','PauloFBaldiFH/koha.nexus','--base',$Base,'--head',$Branch,'--title','build(windows): add MSIX packaging 1.0.25.0','--body',$body)
        }
        Write-Host 'Concluído. Revise o PR no GitHub antes de mesclar.' -ForegroundColor Green
    }
    finally { Pop-Location }
}
catch {
    Write-Host ('FALHA: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
