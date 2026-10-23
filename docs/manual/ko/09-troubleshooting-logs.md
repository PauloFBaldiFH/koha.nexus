# 9. 문제 해결과 로그

[목차](README.md)

## 먼저 증거 수집

수행한 작업, 시간, 전체 오류와 아직 동작하는 부분을 기록하십시오. 페이지가 열리는 것, 서비스가 실행 중인 것, 검색이 되는 것은 서로 다른 확인입니다. 모든 오류에 재설치나 데이터베이스 restore부터 시도하지 마십시오.

**Control Dashboard**를 새로 읽습니다. **Diagnostics & maintenance center**에서 **Detailed server & Koha status**로 서비스·검색·컴퓨터·backup을 보고, **Full system health check**의 요약과 보고서를 읽습니다. 나중에는 **View latest validation report**로 세부 내용을 조회합니다. 지원이 필요하면 대시보드의 **Export diagnostics**를 사용하고 저장 경로를 보관하십시오.

내보내기는 일부 비밀 정보를 가리지만 공유 전에 이용자, 파일명, 시스템 주소를 다시 확인해야 합니다. 설치 폴더 전체를 그대로 공개하지 마십시오. Textual을 열지 못해 기존 방식으로 돌아갔다고 앞서 시작한 작업이 취소된 것은 아닙니다. 메시지와 패널 로그를 남깁니다.

## 로그 위치

| 위치 | 확인할 내용 |
| --- | --- |
| `/var/log/koha-easy-install/` | 설치와 Linux 작업의 기본 디렉터리 |
| 그 안의 `apt.log` | 패키지 설치와 해당 단계 출력 |
| `validacao-*.log` | 날짜·시간별 검증 보고서 |
| `new-panel.log` | Textual 오류와 traceback |
| `backup_sql.log`, `backup_marc.log` | SQL 사본과 MARC 내보내기 |
| `restore.log`, `restore-import.log` | restore 단계와 SQL 가져오기 |
| `zebra-rebuild.log`, `search-engine.log` | 검색 색인과 진단 |
| `/var/log/koha-easy-install/tools/` | 가져오기 등 도구 작업 |
| `C:\Koha\logs`, 이전 설치의 `C:\KohaEasy\logs` | 감지된 Windows 설치의 로그 |

`*`는 날짜가 다른 여러 파일을 뜻하며 그대로 만들 파일명이 아닙니다. 첫 실행 전에는 로그가 없을 수 있습니다. 요약이나 오류가 알려 준 정확한 경로를 우선하십시오. **Library tools > View tool logs**에서 날짜와 작업을 골라 보십시오. 도구 로그에는 개인정보가 들어갈 수 있어 접근이 제한됩니다.

보고서는 맥락, 날짜, 버전과 OK·경고·실패·안내를 함께 읽습니다. 마지막 개수만으로 원인을 알 수 없습니다. **No critical failures**에도 경고가 있을 수 있으며 오래된 backup과 데이터베이스 장애는 대응이 다릅니다. 해결 후 다시 검사해 이전 결과와 비교합니다.

## OPAC과 staff 오류 관찰

**Real-time Apache log auditing**에서 OPAC 또는 staff를 고릅니다. 이전 설치도 대체 경로를 찾아줍니다. Textual의 **Pause** 또는 p는 화면 갱신만 멈추며 Apache를 멈추지 않습니다. **Continue**가 재개하고 **Back** 또는 Esc가 나갑니다. 기존 방식의 Ctrl+C는 이 로그 추적에서 나오는 절차이므로 다른 모든 작업에 적용하지 마십시오.

오류 시간 근처의 문장을 읽습니다. error, fatal, denied, fail이 강조되어도 그 단어 하나가 원인의 증거는 아닙니다. 필요한 앞뒤 문맥을 보관하고 공유 전 개인정보를 제거합니다.

## 증상별 조사

OPAC이나 staff가 열리지 않으면 Apache, MariaDB, Plack, 캐시를 확인하고 주소가 로컬·LAN·VPN·터널 중 어디인지 구분합니다. localhost는 브라우저가 있는 컴퓨터입니다. **Restart / repair Koha services (Memcached, Plack)**는 잠시 접속을 중단할 수 있습니다. 끝났다고 성공으로 단정하지 말고 마지막 메시지와 검증을 다시 읽으십시오.

레코드는 있는데 검색이 안 되면 검색 엔진·대기열·색인과 데이터베이스 관계를 살핍니다. **Search engine & indexing > Repair / rebuild indexing**은 질문을 읽고 확인한 뒤 완료까지 기다립니다. 처음부터 Zebra를 Elasticsearch로 바꾸어야 하는 것은 아닙니다.

backup이 없으면 마지막 실행 시간·결과·디스크·cron 시점의 컴퓨터와 Linux 실행 여부를 확인합니다. `.part`는 완료 파일이 아닙니다. `backup_sql.log`와 센터를 확인해 겹치는 작업을 피하십시오. 기존 파일은 무결성 시험, 현재 사본은 수동 생성으로 확인합니다. 다른 안전한 사본 없이 마지막 유효 backup을 지우지 마십시오.

가져오기가 실패하거나 수가 다르면 입력·준비·실제 등록 수, 모드, 도서관·유형 코드, 바코드, 거부, 중복 정책을 비교합니다. 작은 미리보기가 전체 파일의 유효성을 입증하지 않습니다. 전체 검사를 쓰고, 데이터베이스 쓰기까지 갔다면 이미 끝난 단계를 확인한 뒤 재시도해 중복을 막습니다.

restore 오류는 실패 단계를 구분하십시오. 색인 실패는 데이터베이스 교체 후일 수 있고 rollback 자체도 실패할 수 있습니다. 데이터베이스·검색·검증을 확인하기 전 완전 복구라고 판단하지 마십시오. AI가 느리면 Ollama·저장된 선택·메모리를, 보강이 느리면 작업·서버·제한을 살핍니다. 기다림만을 이유로 큰 작업을 여러 번 실행하지 마십시오. 외부 장애와 로컬 RAM 부족은 다른 문제입니다.

## Windows 아이콘과 트레이

로그인한 사용자의 일반 PowerShell에서, 관리자 권한으로 열지 말고 실행합니다.

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

이 도구는 순수 읽기 전용이 아닙니다. 바로 가기를 다시 만들거나 트레이를 재시작할 수 있습니다. 감지된 설치의 `logs`에 `diagnose-<date>.txt`로 결과를 저장하므로 실제 경로와 전체 오류를 보관하십시오. 관리자 PowerShell을 사용하는 최초 설치와 구별합니다.

## 유지보수와 지원 요청

**Deep database optimization & log cleanup**은 유지보수와 서비스 재시작을 수행하고 조사에 유용한 로그 이력을 지울 수 있습니다. 오류를 숨기려고 실행하지 말고 필요한 진단을 먼저 저장한 뒤 유지보수 시간을 잡습니다.

지원에는 설치 버전, Windows/WSL 또는 Linux 배포판, 작업, 시간, 증상과 전체 메시지를 제공합니다. OPAC·staff·검색의 상태와 직전 가져오기·restore·업데이트도 알리십시오. 진단 일부를 공유하기 전에 개인정보를 확인합니다.

**확인 필요:** 전체 메시지와 실행 로그가 없는 구체적 실패의 원인은 단정할 수 없습니다. 이 장은 조사 순서를 제공하며 모든 문제를 자동으로 네트워크나 설치 탓으로 돌리지 않습니다.

## 확인한 소스

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
