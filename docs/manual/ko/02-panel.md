# 2. 시작하기와 패널 사용

[목차](README.md)

## 패널 열기

설치 프로그램으로 준비한 Debian 또는 Ubuntu에서는 다음을 실행합니다.

```bash
sudo config.sh
```

Windows에서는 설치 프로그램이 만든 **Koha** 아이콘이나 MSIX로 설치한 Koha.Nexus를 여십시오. 첫 실행에 언어 선택이 나올 수 있습니다. Textual 준비에 실패하면 기존 방식의 패널을 제공할 수 있습니다. 이 안내는 주로 Textual 화면을 설명하며, 이전 메뉴의 번호를 현재 카드 위치로 사용하지 않습니다.

## 이동과 종료

사이드바에서 방향키로 항목을 선택한 뒤 Enter를 누르거나 클릭합니다. 선택 표시만 움직여서는 작업이 실행되지 않습니다. 내용 영역에서 해당 작업 카드를 열고 질문을 읽은 후 승인하십시오. Tab은 컨트롤 사이의 초점을 옮깁니다. 글자 단축키를 쓰기 전에 입력란의 편집을 마치거나 입력란 밖으로 이동하십시오.

| 키 | 기본 화면에서의 동작 |
| --- | --- |
| d | Control Dashboard 열기 |
| b | Backup center 열기 |
| c | Debian 터미널 열기 |
| Ctrl+B | 사이드바 표시 또는 숨기기 |
| q | 패널 종료 |

대기 중인 패널에서 나가는 것은 서버 종료 절차가 아닙니다. 진행 중에는 각 화면의 취소 안내를 따르십시오. 설치와 restore에는 취소할 수 없는 단계가 있습니다. 창을 강제 종료하는 것은 해당 작업을 안전하게 취소하는 방법이 아닙니다.

## Control Dashboard 읽기

첫 화면은 Koha 상태와 사용 가능한 메모리, 디스크 여유 공간, 가장 최근 backup의 날짜·경과 시간·파일을 표시합니다. 이 컴퓨터, 로컬 네트워크, 설정된 인터넷의 접속 주소도 볼 수 있습니다. MariaDB, Apache, RabbitMQ, Memcached, Koha 및 HTTP 응답 확인은 진단 자료이며 모든 업무 기능의 동작 시험을 대신하지 않습니다.

최근 파일의 날짜·크기와 마지막 야간 실행 결과는 서로 다른 실행에서 나온 정보일 수 있습니다. 최근 파일이 있어도 야간 작업이 실패했을 수 있으므로 두 표시를 모두 읽으십시오. HTTP 응답이 있다는 것만으로 Koha의 웹 설치 완료나 모든 기능의 정상 작동을 확인할 수는 없습니다.

**Refresh**는 상태를 다시 읽습니다. **Restart Koha**는 서비스 복구·재시작을 요청하므로 이용자에게 미칠 중단을 고려하십시오. **Export diagnostics**는 진단 자료를 준비합니다. 설치된 프로그램이 해당 작업을 지원하지 않으면 일부 버튼을 사용할 수 없습니다. 상태가 좋아 보여도 backup 복구 시험을 생략하지 마십시오.

## OPAC과 staff 접속

주소 카드에서 URL을 열거나 복사할 수 있습니다. 브라우저를 열 수 없는 환경에서는 복사된 주소를 자신의 브라우저에 붙여 넣으십시오. 기본값은 공개 목록에 80, staff에 8080 포트입니다. 서버 자체에서는 `http://localhost/`와 `http://localhost:8080/`를 사용합니다.

다른 컴퓨터의 localhost는 그 컴퓨터 자신입니다. 서버에 접속하려면 패널이 표시하는 네트워크 주소를 쓰십시오. WSL의 NAT 때문에 로컬 네트워크가 연결되지 않는다고 나오면 Windows 네트워크 준비 결과를 확인하고 환경 담당자와 점검합니다.

staff에 Koha 웹 설치 화면이 남아 있으면 먼저 완료하십시오. Koha 버전에 따라 단계가 같지 않을 수 있습니다. 이후 **Koha settings & parameters > Create super librarian**에서 별도 계정 생성 절차를 열 수 있습니다. 개인 정보는 해당 설치 환경에서만 입력하고 강한 관리 권한은 필요한 사람에게만 부여합니다.

## 실제 업무 전 확인

대시보드를 새로 읽고 올바른 주소로 staff와 OPAC을 여십시오. 레코드 검색을 시험하고 3장에 따라 backup을 생성·검증합니다. 서버 밖의 사본 위치와 복구 담당자도 확인하십시오. 외부 사본이 실제로 쓸 수 있는지는 전송과 도착 확인의 완료에 달려 있으며, 대시보드가 자동으로 보장하는 사항은 아닙니다.

## 확인한 소스

- [installer](../../../installer).
- [app.py](../../../panel/kei_panel/app.py).
- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [main.py](../../../panel/kei_panel/screens/main.py).
- [install.py](../../../panel/kei_panel/routines/install.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [dashboard.py](../../../panel/kei_panel/views/dashboard.py).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [menus.py](../../../panel/kei_panel/menus.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
