#!/usr/bin/env python3
"""Sincroniza alunos de um CSV exportado por ERP académico com o Koha.

O que faz, por linha do CSV:
  * procura o leitor pelo número de matrícula (cardnumber) na API REST oficial;
  * se não existir e o aluno estiver Ativo, cria o leitor;
  * se existir, atualiza nome, e-mail e categoria quando mudaram;
  * se a situação não for Ativo (Trancado, Transferido, Evadido), bloqueia
    empréstimos (restricted = true). Não apaga leitores nem mexe em itens.

Regras de segurança:
  * dry-run é o padrão: sem --apply nada é gravado; o plano é só registrado;
  * toda escrita passa pela API REST (/api/v1/patrons); nenhuma tabela SQL;
  * credenciais vêm de variáveis de ambiente, nunca do repositório;
  * se o plano tiver mais bloqueios do que --max-restrictions, a execução
    aborta antes de gravar qualquer coisa (proteção contra CSV incompleto);
  * cada alteração é gravada no log (um registro por linha do CSV).

Usa apenas a biblioteca padrão do Python 3.8+ (roda em cron sem instalar nada).
"""

import argparse
import base64
import csv
import io
import json
import logging
import os
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

REQUIRED_COLUMNS = ("matricula", "nome", "email", "curso", "situacao")
ACTIVE = "active"
INACTIVE = "inactive"
STATUS_MAP = {
    "ativo": ACTIVE,
    "trancado": INACTIVE,
    "transferido": INACTIVE,
    "evadido": INACTIVE,
}
DEFAULT_MAX_RESTRICTIONS = 50
DEFAULT_LOG = "/var/log/koha-nexus/sync-patrons.log"
DEFAULT_LOCK = "/var/lock/koha-nexus-sync-patrons.lock"

log = logging.getLogger("sync_patrons")


class ConfigError(Exception):
    """Configuração, arquivo ou credenciais inválidos: nada é executado."""


class KohaError(Exception):
    """Erro devolvido pela API do Koha."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- utilidades

def fold(text):
    """Minúsculas, sem acentos e sem espaços nas pontas (para comparar)."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.strip().lower()


def load_config(path):
    """Lê o JSON de configuração e confere os campos obrigatórios."""
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"não consegui ler a configuração {path}: {exc}")
    for key in ("library_id", "default_category_id"):
        if not cfg.get(key):
            raise ConfigError(f"a configuração precisa do campo '{key}'")
    cfg.setdefault("category_map", {})
    cfg["category_map"] = {fold(k): v for k, v in cfg["category_map"].items()}
    cfg.setdefault("max_restrictions", DEFAULT_MAX_RESTRICTIONS)
    cfg.setdefault("log_file", DEFAULT_LOG)
    cfg.setdefault("lock_file", DEFAULT_LOCK)
    return cfg


def koha_settings(cfg):
    """URL e credenciais: variáveis de ambiente têm prioridade sobre o JSON."""
    url = os.environ.get("KOHA_URL") or cfg.get("koha_url")
    user = os.environ.get("KOHA_API_USER")
    password = os.environ.get("KOHA_API_PASSWORD")
    if not url:
        raise ConfigError("defina KOHA_URL ou 'koha_url' na configuração")
    if not user or not password:
        raise ConfigError("defina KOHA_API_USER e KOHA_API_PASSWORD no ambiente")
    return url, user, password


# ------------------------------------------------------------------- CSV

def read_csv(path, errors):
    """Lê o CSV do ERP. Aceita ';', ',' ou TAB e UTF-8 com ou sem BOM.

    Devolve uma lista de dicionários já validados. Linhas inválidas entram
    em `errors` com o número da linha e o motivo, e não são sincronizadas.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    if not text.strip():
        raise ConfigError(f"o arquivo {path} está vazio")

    first_line = text.splitlines()[0]
    delimiter = max(";,\t", key=first_line.count)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = [fold(h).replace(" ", "_") for h in next(reader)]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ConfigError(
            "colunas obrigatórias ausentes no CSV: " + ", ".join(missing)
            + " (cabeçalho encontrado: " + ", ".join(header) + ")"
        )

    rows, seen = [], set()
    for lineno, cells in enumerate(reader, start=2):
        if not any(c.strip() for c in cells):
            continue
        rec = {col: (cells[i].strip() if i < len(cells) else "")
               for i, col in enumerate(header)}
        problem = validate_row(rec, seen)
        if problem:
            errors.append((lineno, rec.get("matricula", ""), problem))
            continue
        seen.add(rec["matricula"])
        rec["status"] = STATUS_MAP[fold(rec["situacao"])]
        rec["line"] = lineno
        rows.append(rec)
    return rows


def validate_row(rec, seen):
    if not rec["matricula"]:
        return "matrícula vazia"
    if rec["matricula"] in seen:
        return "matrícula repetida no arquivo (a primeira ocorrência foi usada)"
    if not rec["nome"]:
        return "nome vazio"
    if rec["email"] and ("@" not in rec["email"] or " " in rec["email"]):
        return f"e-mail inválido: {rec['email']}"
    if fold(rec["situacao"]) not in STATUS_MAP:
        return (f"situação desconhecida '{rec['situacao']}' "
                "(use Ativo, Trancado, Transferido ou Evadido)")
    return None


# ------------------------------------------------------------ cliente REST

class KohaClient:
    """Cliente mínimo da API REST do Koha (Basic auth, /api/v1)."""

    def __init__(self, base_url, user, password, timeout=30):
        self.base = base_url.rstrip("/") + "/api/v1"
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode()
        self.auth_header = "Basic " + token
        self.timeout = timeout

    def _request(self, method, path, params=None, body=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = None
        headers = {"Authorization": self.auth_header, "Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise KohaError(exc.code, f"{method} {path} -> HTTP {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            raise KohaError(0, f"{method} {path} -> sem conexão: {exc.reason}")
        return json.loads(raw.decode("utf-8")) if raw else None

    def check_auth(self):
        self._request("GET", "/patrons", {"_per_page": 1})

    def find_patron(self, cardnumber):
        found = self._request("GET", "/patrons",
                              {"q": json.dumps({"cardnumber": cardnumber})})
        return found[0] if found else None

    def create_patron(self, body):
        return self._request("POST", "/patrons", body=body)

    def update_patron(self, patron_id, body):
        return self._request("PUT", f"/patrons/{patron_id}", body=body)


# ------------------------------------------------------------- reconciliação

def category_for(row, cfg):
    """Categoria do Koha para o curso; cai na padrão se o curso não estiver mapeado."""
    mapped = cfg["category_map"].get(fold(row["curso"]))
    if mapped:
        return mapped, True
    return cfg["default_category_id"], False


def plan_row(row, existing, cfg):
    """Decide o que fazer com uma linha. Função pura: não faz chamadas à API.

    Devolve (ação, corpo, avisos). Ações: create, update, unchanged, skip_inactive.
    """
    category, mapped = category_for(row, cfg)
    notes = []
    if not mapped and row["curso"]:
        notes.append(f"curso '{row['curso']}' sem categoria mapeada; usada a padrão")

    if existing is None:
        if row["status"] == INACTIVE:
            return "skip_inactive", {}, notes
        body = {
            "cardnumber": row["matricula"],
            "surname": row["nome"],
            "category_id": category,
            "library_id": cfg["library_id"],
        }
        if row["email"]:
            body["email"] = row["email"]
        return "create", body, notes

    changes = {}
    if existing.get("surname") != row["nome"]:
        changes["surname"] = row["nome"]
    if row["email"] and existing.get("email") != row["email"]:
        changes["email"] = row["email"]
    # Categoria só muda quando o curso está mapeado: um curso sem mapeamento
    # não rebaixa a categoria que a biblioteca já pôs no leitor.
    if mapped and existing.get("category_id") != category:
        changes["category_id"] = category
    # Só bloqueia; nunca desbloqueia. Um bloqueio posto por bibliotecário
    # não é desfeito pelo sincronismo.
    if row["status"] == INACTIVE and not existing.get("restricted"):
        changes["restricted"] = True
    if not changes:
        return "unchanged", {}, notes
    return "update", changes, notes


def build_plan(rows, client, cfg):
    """Consulta o Koha para cada linha e devolve a lista de planos."""
    plans = []
    for row in rows:
        existing = client.find_patron(row["matricula"])
        action, body, notes = plan_row(row, existing, cfg)
        if action == "update" and "restricted" not in existing:
            notes.append("a API não devolveu o campo 'restricted'; verifique a versão do Koha")
        plans.append({"row": row, "existing": existing, "action": action,
                      "body": body, "notes": notes})
    return plans


def describe(plan):
    row = plan["row"]
    if plan["action"] == "create":
        return f"CRIAR leitor {row['matricula']} ({row['nome']}) {plan['body']}"
    if plan["action"] == "update":
        return f"ATUALIZAR leitor {row['matricula']} {plan['body']}"
    if plan["action"] == "skip_inactive":
        return f"IGNORAR {row['matricula']} ({row['situacao']}): não existe no Koha e não é ativo"
    return f"SEM MUDANÇA {row['matricula']}"


def execute(plans, client, apply):
    """Grava o plano (ou só registra, em dry-run). Devolve contadores."""
    counts = Counter()
    for plan in plans:
        action = plan["action"]
        counts[action] += 1
        for note in plan["notes"]:
            log.warning("linha %s: %s", plan["row"]["line"], note)
        if action in ("unchanged", "skip_inactive"):
            log.info(describe(plan))
            continue
        if not apply:
            log.info("[dry-run] %s", describe(plan))
            continue
        try:
            if action == "create":
                client.create_patron(plan["body"])
            else:
                client.update_patron(plan["existing"]["patron_id"], plan["body"])
            log.info("OK %s", describe(plan))
        except KohaError as exc:
            counts["error"] += 1
            log.error("linha %s: falha ao gravar %s: %s",
                      plan["row"]["line"], plan["row"]["matricula"], exc)
    return counts


# -------------------------------------------------------------- execução

def acquire_lock(path):
    """Impede duas execuções simultâneas (cron que se sobrepõe)."""
    try:
        import fcntl
    except ImportError:  # Windows: sem trava, mas o cron de Linux é o alvo
        return None
    fh = open(path, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        raise ConfigError(f"outra execução está em andamento (trava {path})")
    return fh


def setup_logging(log_file, verbose):
    handlers = [logging.StreamHandler(sys.stderr)]
    try:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"não consegui abrir o log {log_file}: {exc}")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for h in handlers:
        h.setFormatter(fmt)
    log.handlers[:] = handlers
    log.setLevel(logging.DEBUG if verbose else logging.INFO)


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Sincroniza alunos de um CSV de ERP acadêmico com o Koha "
                    "(dry-run por padrão).")
    p.add_argument("csv", help="arquivo CSV exportado pelo ERP")
    p.add_argument("-c", "--config", required=True,
                   help="arquivo JSON de configuração (veja config.example.json)")
    p.add_argument("--apply", action="store_true",
                   help="grava no Koha. Sem esta opção, só mostra o plano.")
    p.add_argument("--max-restrictions", type=int, default=None,
                   help="aborta se o plano bloquear mais leitores que isto "
                        "(padrão: valor da configuração, 50)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def run(argv=None):
    args = parse_args(argv)
    try:
        cfg = load_config(args.config)
        setup_logging(cfg["log_file"], args.verbose)
    except ConfigError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    lock = None
    try:
        lock = acquire_lock(cfg["lock_file"])
        errors = []
        rows = read_csv(args.csv, errors)
        for lineno, matricula, problem in errors:
            log.error("linha %s (%s) ignorada: %s", lineno, matricula, problem)

        url, user, password = koha_settings(cfg)
        client = KohaClient(url, user, password)
        mode = "APLICAR" if args.apply else "DRY-RUN"
        log.info("início: %s, %d linhas válidas, modo %s", args.csv, len(rows), mode)
        client.check_auth()

        plans = build_plan(rows, client, cfg)
        to_block = sum(1 for p in plans if p["action"] == "update"
                       and p["body"].get("restricted") is True)
        limit = args.max_restrictions if args.max_restrictions is not None \
            else cfg["max_restrictions"]
        if args.apply and to_block > limit:
            log.error("abortado: o plano bloquearia %d leitores (limite %d). "
                      "Confira o CSV; se estiver correto, aumente o limite "
                      "com --max-restrictions.", to_block, limit)
            return 1

        counts = execute(plans, client, args.apply)
        log.info("fim (%s): criar=%d atualizar=%d sem mudança=%d ignorados=%d "
                 "bloqueios=%d erros_csv=%d erros_api=%d", mode,
                 counts["create"], counts["update"], counts["unchanged"],
                 counts["skip_inactive"], to_block, len(errors), counts["error"])
        if not args.apply:
            log.info("nada foi gravado. Rode com --apply para aplicar.")
        return 1 if (errors or counts["error"]) else 0
    except ConfigError as exc:
        log.error("erro de configuração: %s", exc)
        return 2
    except KohaError as exc:
        log.error("erro da API do Koha: %s", exc)
        return 3
    finally:
        if lock:
            lock.close()


if __name__ == "__main__":
    sys.exit(run())
