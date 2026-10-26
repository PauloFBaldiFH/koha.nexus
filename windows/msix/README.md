# Koha.Nexus — Empacotamento MSIX (Windows)

Pasta de compilação do pacote MSIX **1.0.29.0** (payload `1.0.29.0-msix-v21`).
A release publicada é a 1.0.27.0 (`windows-v1.0.27.0`).
Ela fica separada do instalador Inno Setup (`windows/setup/koha-nexus.iss`).

## Arquivos

- `compilar_msix.ps1` — monta, valida, assina, instala e inicia o MSIX.
- `KohaMsixEntry.cs` — o launcher (`KohaMsixEntry.exe`). Com o Koha ainda não
  instalado, abre a janela de instalação: requisitos do PC, botão Instalar e o
  resultado de cada tentativa, sem caixas de erro. Com o Koha instalado, abre
  o painel direto. O compilador troca `__PAYLOAD_VERSION__` e compila.
- `KohaNexusMark.png` — o símbolo próprio do Koha.Nexus (livro aberto e rede
  de três nós), desenhado por `gerar_assets.py`.
- `KohaNexusIcon.ico` — ícone do launcher, da janela e dos atalhos.
- `Assets/` — ícones e blocos do pacote (44x44, 71x71, 150x150, 310x150,
  310x310 e StoreLogo em scale-100/125/150/200/400, mais targetsize-16 a 256).
- `store-listing/` — imagens da página da loja (bloco 300x300, box art
  1080x1080, pôster 720x1080).

`python3 windows/msix/gerar_assets.py` (Pillow) gera o símbolo, o `.ico`, os
`Assets/` e o `store-listing/`. O compilador só copia e confere os tamanhos.

**Nunca use a gota verde do Koha** nos ícones do pacote ou da loja: ela é o
logotipo da comunidade Koha, e a Store recusou o 1.0.28.0 por isso (10.1.1.11,
"imagem de um produto que não é seu"). A bandeja (`windows\koha.ico`) é da
instalação comum e não entra nos blocos.
- `publicar_pr.ps1` — cria a branch, envia toda esta pasta e abre um PR rascunho.

**Importante:** o arquivo original `windows/koha.ico` continua intocado para
preservar o ícone da bandeja. O ícone do próprio arquivo `.msix` no Explorador
é definido pelo Windows, não pelo manifesto do aplicativo.

## Compilar localmente

Abra **PowerShell 5.1 como administrador** na raiz do repositório:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\msix\compilar_msix.ps1
```

O `installer`, o `installer.sha256`, `lang\` e `panel\` vão para o Debian e
precisam estar com LF. O `.gitattributes` garante isso em qualquer clone; se o
compilador acusar CRLF ou SHA-256 diferente numa cópia antiga, regrave esses
arquivos na raiz do repositório:

```powershell
Remove-Item installer, installer.sha256; Remove-Item lang, panel -Recurse -Force
git checkout -- installer installer.sha256 lang panel
```

O script resolve automaticamente o diretório raiz do Git a partir de sua
localização em `windows/msix`. O MSIX sai em `dist/KohaNexus.msix`.

**Requisitos locais:** Windows + WSL 2, SDK (MakeAppx, MakePri e SignTool em
`%TEMP%\MakeAppxSdk`; o `makepri.exe` está na mesma pasta `bin\<versão>\x64`
do pacote NuGet Microsoft.Windows.SDK.BuildTools de onde veio o MakeAppx), compilador C# do .NET Framework e certificado de
assinatura com `CN=PauloFBaldiFH` no repositório pessoal/de máquina esperado.
O compilador confia nele em `Cert:\LocalMachine\TrustedPeople` e assina com
carimbo de tempo (sem internet, assina sem carimbo e avisa).
O compilador atual também **instala e abre** o aplicativo ao final, não é um
build-only; portanto execute somente numa máquina de testes adequada.

Este arquivo é a versão de teste v17, não um instalador MSIX executado ou
validado ponta a ponta nesta contribuição. Não adicione `dist/`, certificados
privados, dumps do Koha, senhas ou logs ao Git.

## Gerar o pacote para a Microsoft Store

1. No Partner Center, abra o app > *Gerenciamento de produto* > *Identidade do
   produto* e copie os três valores para `store-identity.json`:

   ```json
   {
       "Name": "<Package/Identity/Name>",
       "Publisher": "<Package/Identity/Publisher, o CN=... completo>",
       "PublisherDisplayName": "<Package/Properties/PublisherDisplayName>"
   }
   ```

   Esses valores são públicos (aparecem no manifesto de qualquer app da loja).
2. Na raiz do repositório, atualizada (`git pull`):

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\msix\compilar_msix.ps1 -Store
   ```

   Sai `dist\KohaNexus-Store.msix`, **sem assinatura** e sem instalar nada: a
   Store assina o pacote. Não precisa de certificado nem de administrador.
3. Envie esse arquivo numa nova submissão. A versão (`$targetVersion`) precisa
   ser maior que a do último pacote enviado; suba também `$payloadRevision`
   (os testes conferem que os dois andam juntos).
4. Nas *Notas para certificação*, explique que o app pede administrador
   (UAC), instala o WSL 2 e o Debian, pode pedir para reiniciar o Windows e
   precisa da virtualização ligada na BIOS. Justifique `runFullTrust`: é um
   app de desktop que configura o WSL e abre o painel do Koha no terminal.
   Texto pronto (em inglês, a língua dos testadores):

   ```text
   Koha.Nexus is a desktop (full trust) app that sets up and manages the Koha
   library system inside WSL 2 (Debian).
   On first launch it opens a setup window that lists this PC's requirements
   (Windows 10 2004+/11 64-bit, 8 GB RAM, 10 GB free, virtualization on in
   BIOS/UEFI) and an "Install Koha.Nexus" button. Nothing is installed until
   that button is clicked. Then it:
   1. asks for administrator permission (UAC) to turn on WSL 2 and install
      Debian; answering No leaves the window open with an explanation;
   2. opens a console window with the setup progress and asks for a new
      Debian user name and password;
   3. may ask to restart Windows once to finish turning on WSL; open the app
      again after the restart and click Install to continue;
   4. then opens the Koha control panel in Windows Terminal (a text
      interface). If any step stops, the setup window says why and stays open.
   On a PC without virtualization or with less than 8 GB of RAM, the window
   shows which requirement is missing and the Install button stays off.
   The first setup downloads Debian and Koha packages (internet needed) and
   can take a long time. Logs: C:\Koha\logs\msix-bootstrap.log.
   runFullTrust is needed to run wsl.exe and PowerShell for this setup.
   ```

Para testar no seu PC antes de enviar, rode o script **sem** `-Store` (pacote
assinado com o seu certificado). O pacote de teste e o da Store têm
identidades diferentes e aparecem como dois apps; desinstale o de teste antes
de instalar pela Store.

## Instalar em outro computador ("Fornecedor: Desconhecido")

O pacote é assinado com um certificado próprio (`CN=PauloFBaldiFH`). Desde
o 1.0.27.0 é o de impressão digital `B6721986CB46257290395751E429897B6A48FBBB`
(válido até 22/10/2029); o 1.0.25.0 usou o `F3B8345A573381F2E71B56A96F5EF3253B80A26C`,
cuja chave privada se perdeu. Como o nome é o mesmo, o 1.0.27.0 atualiza o
1.0.25.0 já instalado, mas cada PC precisa confiar no certificado novo. Nenhum Windows confia nele de fábrica, então o Instalador de
Aplicativos mostra **Fornecedor: Desconhecido** e recusa com "Não foi possível
verificar o certificado de fornecedor deste pacote de aplicativo".

Para instalar, abra o **PowerShell normal** (não precisa ser administrador) e rode:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

O script baixa o MSIX da release `windows-v1.0.27.0`, confere que ele foi
assinado por um desses certificados (e por nenhum outro), coloca a parte pública do
certificado em **Computador local > Pessoas Confiáveis** (um pedido de
permissão do Windows, só na primeira vez em cada PC), instala o pacote e abre o
Koha.Nexus. Com um `.msix` já baixado:
`.\windows\msix\instalar_msix.ps1 -MsixPath C:\caminho\KohaNexus.msix`.

Manual, sem script: clique duas vezes no `KohaNexus-Publisher.cer` da release
(o desta pasta é o do 1.0.25.0) >
Instalar Certificado > **Máquina Local** > "Colocar todos os certificados no
repositório a seguir" > **Pessoas Confiáveis**. Depois abra o `.msix` de novo.
Não use "Autoridades de Certificação Raiz Confiáveis": não é necessário.

**Ao trocar o certificado** (renovação ou outro PC de compilação), acrescente a
nova impressão digital em `$KnownThumbprints` de `instalar_msix.ps1` e troque
`KohaNexus-Publisher.cer` no mesmo commit. O `compilar_msix.ps1` grava esse
`.cer` em `dist\` ao lado do MSIX; publique os dois na release. Guarde o `.pfx`
do certificado (com senha) fora do repositório: sem ele não dá para assinar
outra versão com a mesma impressão digital. Os testes de
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
