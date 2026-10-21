# Koha.Nexus — Empacotamento MSIX (Windows)

Pasta de compilação do pacote MSIX **1.0.25.0**, baseada no compilador v17.
Ela fica separada do instalador Inno Setup (`windows/setup/koha-nexus.iss`).

## Arquivos

- `compilar_msix.ps1` — monta, valida, assina, instala e inicia o MSIX.
- `KohaNexusIcon.ico` — ícone personalizado do launcher/desktop e recursos MSIX.
- `KohaNexusLogo.png` — imagem usada nos recursos visuais do pacote.
- `publicar_pr.ps1` — cria a branch, envia toda esta pasta e abre um PR rascunho.

**Importante:** o arquivo original `windows/koha.ico` continua intocado para
preservar o ícone da bandeja. O ícone do próprio arquivo `.msix` no Explorador
é definido pelo Windows, não pelo manifesto do aplicativo.

## Compilar localmente

Abra **PowerShell 5.1 como administrador** na raiz do repositório:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\msix\compilar_msix.ps1
```

O script resolve automaticamente o diretório raiz do Git a partir de sua
localização em `windows/msix`. O MSIX sai em `dist/KohaNexus.msix`.

**Requisitos locais:** Windows + WSL 2, SDK (MakeAppx e SignTool nos caminhos
esperados pelo compilador), compilador C# do .NET Framework e certificado de
assinatura com `CN=PauloFBaldiFH` no repositório pessoal/de máquina esperado.
O compilador atual também **instala e abre** o aplicativo ao final, não é um
build-only; portanto execute somente numa máquina de testes adequada.

Este arquivo é a versão de teste v17, não um instalador MSIX executado ou
validado ponta a ponta nesta contribuição. Não adicione `dist/`, certificados
privados, dumps do Koha, senhas ou logs ao Git.

## Fluxo esperado da primeira execução

1. **Terminal de preparação:** virtualização, WSL 2, Debian, conta Linux,
   `systemd` e dependências do painel (sem instalar o servidor Koha).
2. Após concluir as dependências, abre o painel definitivo em uma segunda
   janela, começando pela **seleção do idioma**.
3. **Painel definitivo:** instalação e administração do servidor Koha.
4. O primeiro terminal encerra a preparação, preservando a segunda janela.

Porta esperada do staff Koha: **8080**. O status real da porta no Apache/WSL
precisa ser confirmado na instalação de testes.

## Publicar por pull request

Com Git e GitHub CLI (`gh`) instalados e autenticados, rode **na raiz**:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\msix\publicar_pr.ps1
```

O script confere o remoto GitHub, cria `feature/windows-msix-1.0.25.0`, adiciona
**apenas `windows/msix/`**, faz o commit, envia para o GitHub e abre um PR
**rascunho** (sem integrar automaticamente ao `main`).
