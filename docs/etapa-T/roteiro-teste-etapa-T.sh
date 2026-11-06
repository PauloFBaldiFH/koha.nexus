#!/usr/bin/env bash
# Roteiro NÃO destrutivo da etapa T (PRs U1 a U6) para o servidor do Paulo.
#
# Para que serve: verificar alterações inesperadas de uma atualização do
# painel (comparação antes/depois) e ler o estado das funções novas. Não
# substitui os testes funcionais de backup, restauração e acesso, que
# continuam separados (CI com Koha e Tainacan reais e, se o Paulo quiser,
# uma máquina de teste dele).
#
# O que ele faz e o que não faz:
#   * Só lê: não instala, não restaura, não faz backup, não troca senha, não
#     publica endereço, não mexe em agendamento nem em firewall.
#   * Só chama tarefas de consulta do painel (lista CONSULTAS abaixo); qualquer
#     outra é recusada pelo próprio roteiro antes de rodar.
#   * Nunca imprime comando de agendamento, senha, token ou conteúdo de arquivo
#     de configuração. Dos arquivos sensíveis guarda só o resumo (sha256); das
#     linhas de agendamento, só arquivo, número da linha e resumo da linha.
#   * Os arquivos que gera ficam numa pasta 700, cada um 600.
#
# Uso (como root):
#   1. Antes de atualizar o painel:   sudo bash roteiro-teste-etapa-T.sh antes
#   2. Atualize o painel pelo caminho de sempre (depois dos merges).
#   3. Depois da atualização:          sudo bash roteiro-teste-etapa-T.sh depois
#
# O relatório fica em /root/koha-nexus-teste-T/. Ele não traz senhas nem
# conteúdo de configuração, mas traz caminhos, nomes de arquivos, o nome do
# servidor e contagens: revise antes de compartilhar.
set -u
umask 077

DIR="${KEI_TESTE_DIR:-/root/koha-nexus-teste-T}"
PANEL="${KEI_PANEL:-/usr/local/bin/config.sh}"
BROKER="${KEI_BROKER_URL:-https://broker.koha.nexus}"
MODE="${1:-}"
case "$MODE" in antes|depois) ;; *) echo "Use: $0 antes|depois"; exit 2 ;; esac
[ "$(id -u)" = 0 ] || { echo "Rode como root (sudo)."; exit 2; }
mkdir -p "$DIR" && chmod 700 "$DIR"
STAMP=$(date +%Y-%m-%d_%Hh%M)
REPORT="$DIR/relatorio-$STAMP-$MODE.txt"
SNAP="$DIR/estado-$MODE.txt"
WORK=$(mktemp -d "$DIR/.tmp.XXXXXX") && chmod 700 "$WORK"
trap 'rm -rf "$WORK"' EXIT
: > "$REPORT" && chmod 600 "$REPORT"

ok()       { printf 'OK        %s\n' "$*" | tee -a "$REPORT"; }
aviso()    { printf 'AVISO     %s\n' "$*" | tee -a "$REPORT"; }
falha()    { printf 'FALHA     %s\n' "$*" | tee -a "$REPORT"; }
pendente() { printf 'PENDENTE  %s\n' "$*" | tee -a "$REPORT"; }
info()     { printf '          %s\n' "$*" | tee -a "$REPORT"; }
titulo()   { printf '\n== %s\n' "$*" | tee -a "$REPORT"; }
h()        { sha256sum | cut -c1-16; }          # resumo curto do que vem na entrada

# ----------------------------------------------------------------------
# Tarefas do painel: só consultas. Conferido no instalador da 1.5.179:
#   platform-backup-status  kei_backup_status, só lê o estado dos backups
#   cloud-status            cloud_status, só lê rclone.conf e o registro
#   cf-status               cf_status, só lê o túnel e o tunnel.conf
#   admin-status            kei_koha_admin_status (SELECT de superbibliotecários)
#                           e kei_tainacan_admin_status (confere a senha
#                           inicial com wp_check_password, sem gravar)
#   setup-status            kei_setup_status, só lê o estado do assistente
#   tainacan-free-status    kei_tainacan_free_status, lê tunnel.conf e faz
#                           GET /v1/capabilities no serviço de endereços
# ----------------------------------------------------------------------
CONSULTAS=" platform-backup-status cloud-status cf-status admin-status setup-status tainacan-free-status "

# task NOME [ARGS]: roda uma consulta e separa o código de saída, o tempo
# esgotado e a resposta. Deixa em T_RC, T_STATE e T_OUT (só as linhas
# @@result). T_STATE: ok | vazio | ausente | tempo | falha.
#   ausente  o painel instalado não conhece a tarefa (recurso ausente)
#   vazio    a tarefa respondeu sem dados (configuração inexistente)
#   tempo    passou de 120 s
#   falha    terminou com erro
task() {
    local name="$1" raw="$WORK/task.raw"
    case "$CONSULTAS" in *" $name "*) ;; *)
        falha "Tarefa '$name' não está na lista de consultas: não foi executada."
        T_RC=99 T_STATE=falha T_OUT=""; return 1 ;;
    esac
    timeout 120 "$PANEL" --task "$@" </dev/null >/dev/null 2>"$raw"
    T_RC=$?
    T_OUT=$(sed -n 's/^@@result //p' "$raw")
    if [ "$T_RC" = 124 ]; then T_STATE=tempo
    elif grep -q 'Unknown panel action\|Ação do painel desconhecida' "$raw"; then T_STATE=ausente
    elif [ "$T_RC" != 0 ]; then T_STATE=falha
    elif [ -z "$T_OUT" ]; then T_STATE=vazio
    else T_STATE=ok; fi
    : > "$raw"
    return 0
}
# Uma linha do relatório para o resultado da última tarefa.
task_line() {   # DESCRIÇÃO
    case "$T_STATE" in
        ok)      ok "$1: respondeu (código 0)." ;;
        vazio)   info "$1: sem dados (configuração inexistente neste servidor)." ;;
        ausente) pendente "$1: o painel instalado ainda não tem esta consulta (recurso ausente)." ;;
        tempo)   falha "$1: não respondeu em 120 s (tempo esgotado)." ;;
        *)       falha "$1: terminou com erro (código $T_RC)." ;;
    esac
}
val() { printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -n1; }

# ----------------------------------------------------------------------
# Estado comparável antes/depois: só nomes e resumos.
# ----------------------------------------------------------------------
cron_lines() {   # arquivo:linha resumo, para cada linha ativa de agendamento
    local f n line
    for f in /etc/cron.d/* /etc/crontab; do
        [ -f "$f" ] || continue
        n=0
        while IFS= read -r line || [ -n "$line" ]; do
            n=$((n + 1))
            [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
            [[ "$line" =~ ^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*= ]] && continue
            printf '%s:%s %s\n' "$f" "$n" "$(printf '%s' "$line" | tr -s ' \t' ' ' | sed 's/^ //; s/ $//' | h)"
        done < "$f"
    done
    if crontab -l >/dev/null 2>&1; then
        n=0
        crontab -l 2>/dev/null | while IFS= read -r line; do
            n=$((n + 1))
            [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
            [[ "$line" =~ ^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*= ]] && continue
            printf 'crontab-root:%s %s\n' "$n" "$(printf '%s' "$line" | tr -s ' \t' ' ' | sed 's/^ //; s/ $//' | h)"
        done
    fi
}
file_hash() { [ -f "$1" ] && printf '%s  %s\n' "$(h < "$1")" "$1"; }

snapshot() {
    local f
    {
        echo "# agendamentos (arquivo:linha resumo)"
        cron_lines
        echo "# timers do systemd"
        systemctl list-timers --all --no-legend 2>/dev/null | awk '{print $(NF-1)}' | sort
        echo "# apache: sites e configurações habilitados (resumo do arquivo real)"
        for f in /etc/apache2/sites-enabled/* /etc/apache2/conf-enabled/*; do
            [ -e "$f" ] && printf '%s -> %s\n' "$f" "$(file_hash "$(readlink -f "$f")" | cut -d' ' -f1)"
        done
        file_hash /etc/apache2/ports.conf
        file_hash /etc/apache2/apache2.conf
        echo "# apache: módulos habilitados"
        ls -1 /etc/apache2/mods-enabled 2>/dev/null
        echo "# túnel e endereços (resumo)"
        for f in /etc/cloudflared/config.yml /etc/koha-easy-install/tunnel.conf; do file_hash "$f"; done
        echo "# firewall: ufw (estado e regras), iptables e nftables (regras, sem contadores)"
        ufw status verbose 2>/dev/null | h
        iptables-save 2>/dev/null | grep -v '^#' | sed 's/\[[0-9]*:[0-9]*\]//g' | h
        ip6tables-save 2>/dev/null | grep -v '^#' | sed 's/\[[0-9]*:[0-9]*\]//g' | h
        nft list ruleset 2>/dev/null | grep -v 'counter packets' | h
        echo "# contas do sistema (resumo de /etc/passwd, /etc/group, /etc/shadow)"
        for f in /etc/passwd /etc/group /etc/shadow; do file_hash "$f"; done
        echo "# contas da equipe do Koha (resumo de id, login, permissões e hash da senha)"
        koha_staff | h
        echo "# contêineres"
        docker ps -a --format '{{.Names}} {{.Image}}' 2>/dev/null | sort
        echo "# .env do Tainacan (resumo)"
        file_hash /var/lib/koha-nexus/platforms/tainacan/.env
        echo "# koha-conf (resumo)"
        for f in /etc/koha/sites/*/koha-conf.xml; do file_hash "$f"; done
    } > "$SNAP"
    chmod 600 "$SNAP"
}
# Contas da equipe do Koha: id, login, permissões e hash da senha, só para
# o resumo (nada disso vai para o relatório).
koha_staff() {
    local inst
    for inst in $(koha-list 2>/dev/null); do
        koha-mysql "$inst" -N -e "SELECT borrowernumber, userid, flags, password FROM borrowers WHERE flags IS NOT NULL AND flags <> 0 ORDER BY borrowernumber" 2>/dev/null
    done
}

# ----------------------------------------------------------------------
titulo "Etapa T: roteiro não destrutivo ($MODE), $(date '+%d/%m/%Y %H:%M')"
[ -x "$PANEL" ] || { falha "Painel não encontrado em $PANEL."; exit 1; }
VERSION=$(sed -n 's/^PANEL_VERSION=" *\([0-9.]*\)".*/\1/p' "$PANEL" | head -n1)
info "Versão do painel: ${VERSION:-desconhecida}"

# A lista de administradores do WordPress entra no resumo; os nomes não vão ao relatório.
TN_ADMINS=""
task admin-status tainacan
[ "$T_STATE" = ok ] && TN_ADMINS=$(printf '%s\n' "$T_OUT" | sed -n 's/^admin=//p' | sort)
TN_ADMIN_STATE=$T_STATE
snapshot
# Comparados à parte: só quando a consulta respondeu antes e depois.
if [ "$TN_ADMIN_STATE" = ok ]; then printf '%s\n' "$TN_ADMINS" | h > "$DIR/wp-admins-$MODE.txt"
else rm -f "$DIR/wp-admins-$MODE.txt"; fi
info "Estado guardado em $SNAP (só nomes e resumos, arquivo 600)."

if [ "$MODE" = antes ]; then
    info "Agora atualize o painel e rode de novo com: depois"
    exit 0
fi

newer() { [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)" = "$1" ]; }
newer 1.5.179 "${VERSION:-0}" || pendente "O painel ainda não é 1.5.179 ou mais novo. Atualize depois dos merges e rode de novo."

titulo "1. A atualização não mudou nada sozinha"
if [ -f "$DIR/estado-antes.txt" ]; then
    if diff -q "$DIR/estado-antes.txt" "$SNAP" >/dev/null; then
        ok "Iguais a antes: linhas de agendamento, timers, arquivos do Apache habilitados, ports.conf, apache2.conf,"
        info "módulos, túnel, regras do ufw/iptables/nftables, /etc/passwd, /etc/group, /etc/shadow, contas da"
        info "equipe do Koha (id, login, permissões, hash da senha), contêineres, .env do Tainacan e koha-conf.xml."
        command -v koha-list >/dev/null 2>&1 || info "Contas do Koha não comparadas: Koha não instalado."
    else
        aviso "Algo mudou entre antes e depois. Só os nomes das seções e dos arquivos, e os resumos:"
        diff "$DIR/estado-antes.txt" "$SNAP" | sed 's/^/          /' | tee -a "$REPORT"
        info "Uma mudança no resumo de 'agendamentos' ou de 'firewall' mostra só onde: confira o arquivo e a linha."
    fi
    if [ -f "$DIR/wp-admins-antes.txt" ] && [ -f "$DIR/wp-admins-depois.txt" ]; then
        if cmp -s "$DIR/wp-admins-antes.txt" "$DIR/wp-admins-depois.txt"; then ok "Lista de administradores do WordPress igual a antes."
        else aviso "A lista de administradores do WordPress mudou (os nomes não são mostrados)."; fi
    else
        info "Administradores do WordPress não comparados: a consulta não respondeu antes e depois (painel antigo ou sem Tainacan)."
    fi
    info "Não comparado: senhas do Tainacan dentro do banco do WordPress (só a lista de administradores),"
    info "contas de nuvem e da Cloudflare (ficam fora do servidor) e regras de firewall do provedor."
else
    pendente "Não há estado de antes. Rode primeiro com: antes"
fi
if ls /var/lib/koha-nexus/setup/*.state >/dev/null 2>&1; then
    aviso "Há configuração pós-instalação em andamento: $(ls /var/lib/koha-nexus/setup/*.state | xargs -n1 basename | tr '\n' ' ')"
    info "Isso só deveria existir depois de uma instalação nova feita pelo painel."
else
    ok "Nenhum assistente pós-instalação foi aberto pela atualização."
fi

titulo "2. Agendamentos repetidos (U3)"
dups=$(cron_lines | awk '{print $2}' | sort | uniq -d)
if [ -z "$dups" ]; then
    ok "Nenhuma linha de agendamento repetida ($(cron_lines | wc -l) linhas ativas comparadas)."
else
    aviso "Linhas de agendamento repetidas (arquivo:linha e resumo; o comando não é mostrado):"
    for d in $dups; do cron_lines | awk -v d="$d" '$2 == d' | sed 's/^/          /' | tee -a "$REPORT"; done
fi

titulo "3. Plataformas e central de backups (U1)"
st=$(timeout 60 "$PANEL" --status-json 2>/dev/null); rc=$?
if [ "$rc" = 124 ]; then falha "Status do painel: tempo esgotado."
elif [ "$rc" != 0 ] || [ -z "$st" ]; then falha "Status do painel: erro (código $rc)."
elif printf '%s' "$st" | python3 -I -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if "platforms" in d else 3)' 2>/dev/null; then
    ok "Status do painel lido; traz as plataformas."
else aviso "Status do painel lido, mas sem as plataformas (JSON inválido ou painel antigo)."; fi
task platform-backup-status; task_line "Backups das plataformas"
if [ "$T_STATE" = ok ]; then
    info "Chave dos backups cifrados: $([ -n "$(val "$T_OUT" key)" ] && echo configurada || echo 'não configurada')"
    info "Agendamento do Tainacan: $(val "$T_OUT" schedule | sed 's/^$/nenhum/')"
fi
task cloud-status; task_line "Nuvem (sem enviar nada)"

titulo "4. Acesso administrativo (U4, sem senhas)"
if command -v koha-list >/dev/null 2>&1 && [ -n "$(koha-list 2>/dev/null)" ]; then
    task admin-status koha; task_line "Koha: acesso administrativo"
    if [ "$T_STATE" = ok ]; then
        case "$(val "$T_OUT" state)" in
            ready) ok "Koha: instalador da web concluído (há superbibliotecário)." ;;
            web-installer) aviso "Koha: ainda sem superbibliotecário." ;;
            *) aviso "Koha: estado '$(val "$T_OUT" state)' não reconhecido." ;;
        esac
        info "Superbibliotecários: $(printf '%s\n' "$T_OUT" | grep -c '^admin=')"
    fi
else
    info "Koha não instalado neste servidor."
fi
task admin-status tainacan; task_line "Tainacan: acesso administrativo"
if [ "$T_STATE" = ok ]; then
    case "$(val "$T_OUT" state)" in
        initial) info "Tainacan: a conta da instalação ainda usa a senha gerada." ;;
        own) ok "Tainacan: a conta da instalação já tem senha própria." ;;
        *) info "Tainacan: estado '$(val "$T_OUT" state)'." ;;
    esac
    info "Administradores do WordPress: $(printf '%s\n' "$T_OUT" | grep -c '^admin=')"
fi
for p in koha tainacan; do
    task setup-status "$p" quick
    [ "$T_STATE" = ok ] && [ "$(val "$T_OUT" setup)" = open ] && info "Configuração pós-instalação de $p: $(val "$T_OUT" pending) etapa(s) pendente(s)."
    [ "$T_STATE" = ok ] || task_line "Assistente de $p"
done

titulo "5. Endereço gratuito do acervo (U5)"
body="$WORK/cap.json"
code=$(curl -s -o "$body" -w '%{http_code}' --max-time 15 "$BROKER/v1/capabilities" 2>/dev/null); crc=$?
if [ "$crc" != 0 ]; then
    falha "Serviço de endereços: sem resposta pela rede (curl $crc). Não dá para dizer se oferece acervos."
elif [ "$code" = 404 ]; then
    pendente "Serviço de endereços no ar, mas sem /v1/capabilities (versão anterior ao U5): publicação e migração 0003 são passo seu."
elif [ "$code" != 200 ]; then
    falha "Serviço de endereços respondeu HTTP $code."
else
    cap=$(python3 -I - "$body" <<'PY' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("invalid"); sys.exit(0)
s = d.get("services") if isinstance(d, dict) else None
if not isinstance(s, list):
    print("invalid"); sys.exit(0)
print(("enabled" if "tainacan" in s else "disabled") + " " + str(d.get("collection_suffix", "")))
PY
)
    case "$cap" in
        enabled*) ok "Serviço de endereços oferece endereços para acervos (sufixo ${cap#enabled })." ;;
        disabled*) pendente "Serviço de endereços no ar, mas com acervos desligados (services sem tainacan)." ;;
        *) falha "Serviço de endereços respondeu 200 com JSON inválido ou sem 'services'." ;;
    esac
fi
task tainacan-free-status; task_line "Endereço gratuito do acervo no painel"
if [ "$T_STATE" = ok ]; then
    info "Em uso: $([ -n "$(val "$T_OUT" host)" ] && echo sim || echo não)"
    [ "$(val "$T_OUT" available)" = yes ] && ok "O painel pode oferecer o endereço gratuito do acervo." \
        || info "O painel mostra como indisponível: $(val "$T_OUT" reason)"
fi
task cf-status; task_line "Túnel do catálogo"
[ "$T_STATE" = ok ] && info "Modo do túnel: $(val "$T_OUT" mode | sed 's/^$/nenhum/')."

titulo "Fim"
info "Relatório: $REPORT (600, pasta 700)."
info "Ele não traz senhas, tokens, comandos de agendamento nem conteúdo de configuração, mas traz caminhos,"
info "nomes de arquivos e contagens: revise antes de compartilhar."
info "Este roteiro verifica alterações inesperadas. Os testes de backup, restauração e acesso são outros."
