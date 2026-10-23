# 1. 설치

[목차](README.md)

## 실행 환경 선택

Windows에서는 WSL 2의 Debian 안에서 Koha가 실행됩니다. Windows 도구는 환경 준비, 패널 실행 및 컴퓨터와의 통합을 담당합니다. Debian이나 Ubuntu에서는 서버에 직접 설치합니다. 이미 있는 목록을 사용하려면 설치를 다시 하지 말고 2장의 방법으로 패널을 여십시오. 재설치는 별도의 데이터 삭제 확인을 거치는 작업입니다.

| 환경 | 운영체제와 아키텍처 | 메모리 | 여유 공간 |
| --- | --- | --- | --- |
| Windows | Windows 10 버전 2004, build 19041 이상 또는 Windows 11, 64비트, 가상화 활성화 | 최소 8 GB, 권장 12 GB | 설치 드라이브에 최소 10 GB, 권장 20 GB |
| Debian/Ubuntu | Debian 11·12·13, Ubuntu 22.04·24.04, amd64 또는 arm64 | 아래의 확인 사항 참고 | 5 GB 미만은 중단, 5 GB 이상 10 GB 미만은 경고 |

이 수치는 설치 진입 단계의 검사입니다. 목록, 첨부 파일, 검색 색인, backup이 늘어날 공간도 확보하십시오. Windows 메모리 검사는 하드웨어 예약분을 고려해 7.5 GB와 11.5 GB를 기준으로 판단합니다. 따라서 판매 용량이 8 GB인 컴퓨터의 표시값이 조금 작아도 허용될 수 있습니다.

**확인 필요:** 기존 안내는 전용 서버에 최소 4 GB·권장 8 GB, 데스크톱이나 가상 환경에 8 GB·권장 12 GB를 제시합니다. 그러나 Linux 사전 검사는 이 RAM 하한을 숫자 조건으로 강제하지 않습니다. 검사 통과만으로 모든 도서관 업무에 충분한 용량이라고 판단하지 마십시오.

Linux에서는 관리자 권한, Koha 저장소 접속과 80·8080 포트를 확인합니다. 사용 중인 포트의 서비스를 중지하겠다는 질문에는 그 서비스를 중단해도 되는지 아는 경우에만 동의하십시오. WSL 환경은 systemd가 실행되는 WSL 2여야 하며, 이 설치 과정에서는 WSL 1을 거부합니다.

## Windows: PowerShell 설치

Koha를 사용할 관리자 권한이 있는 Windows 계정으로 로그인하고, 같은 계정의 PowerShell을 관리자 권한으로 여십시오. 권한 상승에 다른 사람의 계정이 필요하다고 나오면 취소한 뒤 적절한 관리자 계정으로 로그인하십시오. WSL 구성 요소는 설치에 사용한 계정에 속합니다. 주소와 배포처를 신뢰할 수 있는지 확인한 다음 실행합니다.

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

컴퓨터 검사 결과를 읽고 가상화 등 오류를 먼저 해결하십시오. Debian 계정 생성 질문은 설치 창에서 답합니다. 이 계정은 Koha 도서관 계정과 다릅니다. 재시작이 필요하면 다음 Windows 로그인 때 이어서 실행할 작업이 등록됩니다. 같은 사용자로 돌아와 패널에서 언어와 **Install Koha server**를 선택합니다.

패널 안의 설치가 끝나면 정상적으로 종료하고 Windows 통합이 완료될 때까지 기다리십시오. 기본 도구 폴더는 `C:\Koha`이며, 이전 설치는 `C:\KohaEasy`에 남을 수 있습니다. 중단된 설치를 고치려고 폴더를 직접 옮기지 마십시오. 설치 프로그램을 다시 실행하면 기록된 단계부터 이어갈 수 있지만, 이것이 데이터 삭제 확인을 읽지 않고 재설치해도 된다는 뜻은 아닙니다.

## Windows: MSIX 패키지

이 보조 도구는 관리자 권한으로 열지 않은 일반 PowerShell에서 실행합니다.

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

도구가 지정된 패키지를 내려받고 출처를 검사한 다음 필요한 관리자 승인을 요청합니다. 거부나 오류를 무시하지 마십시오. MSIX 설치 성공은 Koha 서버와 데이터베이스 구성이 끝났다는 뜻이 아닙니다.

첫 실행에서는 준비를 기다리고 패널의 설치를 마치십시오. 패널을 정상 종료한 뒤 바로 가기, 백그라운드 작업, 네트워크의 최종 구성이 끝날 때까지 기다립니다. 설치 전에 창을 닫았다면 응용프로그램을 다시 열어 계속하십시오. 창을 닫은 사실만으로 설치가 완료되지는 않습니다.

**확인 필요:** Microsoft Store의 공개 여부와 주소는 저장소의 패키징 지원만으로 확정되지 않습니다. 임의의 Store 링크를 사용하지 않습니다. 생성된 manifest는 x64입니다. Linux의 arm64 지원을 MSIX의 ARM64 지원으로 해석하지 마십시오. manifest에 더 낮은 Windows 최소 버전이 적혀 있어도 전체 WSL 설치에는 위 표의 조건을 적용합니다.

## Debian 또는 Ubuntu

대상 서버 터미널에서 다음을 실행합니다.

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

저장소 사본과 번역을 함께 보관하려면 다음 방식을 대신 사용할 수 있습니다.

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

언어를 고른 뒤 **Install Koha server**를 여십시오. 시스템, 필수 프로그램, 네트워크, 공간, 포트의 결과를 읽고 심각한 오류를 먼저 해결합니다. 작업 대상 컴퓨터와 감지된 시간대를 확인하거나 지역과 도시를 선택합니다.

기존 인스턴스가 있으면 재설치는 데이터베이스와 설정을 삭제합니다. 추가 확인과 정확한 `REINSTALL` 입력이 필요합니다. 서버 밖에 복구 가능한 backup을 보관한 뒤에만 판단하십시오. 단순히 패널을 열거나 업데이트하려고 재설치를 사용하지 마십시오.

화면의 예상 시간은 10~30분이지만 실제 시간은 장비와 네트워크에 따라 달라집니다. 패널에서 취소할 수 없는 단계이므로 창을 강제로 닫지 마십시오. 끝난 뒤 전체 결과와 실패 항목을 읽습니다. 문제가 있는 상태로 완료되었다고 모든 서비스가 정상인 것은 아닙니다. 결과 화면의 개인 정보를 공개 문서나 지원 요청에 복사하지 마십시오.

## 확인한 소스

- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [installer](../../../installer).
- [README.md](../../../README.md).
- [install.ps1](../../../windows/install.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [instalar_msix.ps1](../../../windows/msix/instalar_msix.ps1).
- [KohaMsixEntry.cs](../../../windows/msix/KohaMsixEntry.cs).
- [KohaMsixPanel.ps1](../../../windows/KohaMsixPanel.ps1).
- [compilar_msix.ps1](../../../windows/msix/compilar_msix.ps1).
- [install.py](../../../panel/kei_panel/routines/install.py).
