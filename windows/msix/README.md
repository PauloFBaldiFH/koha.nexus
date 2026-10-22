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
O compilador confia nele em `Cert:\LocalMachine\TrustedPeople` e assina com
carimbo de tempo (sem internet, assina sem carimbo e avisa).
O compilador atual também **instala e abre** o aplicativo ao final, não é um
build-only; portanto execute somente numa máquina de testes adequada.

Este arquivo é a versão de teste v17, não um instalador MSIX executado ou
validado ponta a ponta nesta contribuição. Não adicione `dist/`, certificados
privados, dumps do Koha, senhas ou logs ao Git.

## Instalar em outro computador ("Fornecedor: Desconhecido")

O pacote é assinado com um certificado próprio (`CN=PauloFBaldiFH`,
impressão digital `F3B8345A573381F2E71B56A96F5EF3253B80A26C`, válido até
20/10/2027). Nenhum Windows confia nele de fábrica, então o Instalador de
Aplicativos mostra **Fornecedor: Desconhecido** e recusa com "Não foi possível
verificar o certificado de fornecedor deste pacote de aplicativo".

Para instalar, abra o **PowerShell normal** (não precisa ser administrador) e rode:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

O script baixa o MSIX da release `windows-v1.0.25.0`, confere que ele foi
assinado por esse certificado (e por nenhum outro), coloca a parte pública do
certificado em **Computador local > Pessoas Confiáveis** (um pedido de
permissão do Windows, só na primeira vez em cada PC), instala o pacote e abre o
Koha.Nexus. Com um `.msix` já baixado:
`.\windows\msix\instalar_msix.ps1 -MsixPath C:\caminho\KohaNexus.msix`.

Manual, sem script: clique duas vezes em `KohaNexus-Publisher.cer` >
Instalar Certificado > **Máquina Local** > "Colocar todos os certificados no
repositório a seguir" > **Pessoas Confiáveis**. Depois abra o `.msix` de novo.
Não use "Autoridades de Certificação Raiz Confiáveis": não é necessário.

**Ao trocar o certificado** (renovação ou outro PC de compilação), acrescente a
nova impressão digital em `$KnownThumbprints` de `instalar_msix.ps1` e troque
`KohaNexus-Publisher.cer` no mesmo commit. O `compilar_msix.ps1` grava esse
`.cer` em `dist\` ao lado do MSIX; publique os dois na release. Os testes de
`tests/windows_checks.ps1` conferem que o `.msix` versionado, o `.cer` e o
script falam do mesmo certificado.

Para que nenhum PC precise confiar no certificado à mão, o pacote precisa de
uma assinatura que o Windows já reconheça: publicar pela Microsoft Store (a
loja assina o pacote) ou assinar com um certificado de assinatura de código
emitido por uma autoridade (por exemplo Azure Artifact Signing ou SignPath).
Os dois caminhos dependem de uma conta em nome do Paulo e mudam o `Publisher`
do manifesto para o nome que essa conta fornecer.

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
