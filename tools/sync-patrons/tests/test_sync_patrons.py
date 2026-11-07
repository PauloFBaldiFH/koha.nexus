"""Testes do sync_patrons.py com mocks. Não precisam de Koha.

Rodar a partir da raiz do repositório:
    python3 -m unittest discover -s tools/sync-patrons/tests -t tools/sync-patrons -v

Cobrem: leitura do CSV, regras de reconciliação, dry-run, trava de bloqueios
em massa, cabeçalho de autenticação e parâmetros enviados à API (com um
servidor HTTP local que imita /api/v1/patrons). O que só um Koha real
confirma está listado no README.md, seção "O que ainda precisa de Koha real".
"""

import base64
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import sync_patrons as sp  # noqa: E402

CFG = {
    "library_id": "CENTRAL",
    "default_category_id": "ALUNO",
    "category_map": {"engenharia civil": "GRAD", "pedagogia": "LIC"},
    "max_restrictions": 50,
    "log_file": os.devnull,
    "lock_file": os.devnull,
}


def csv_file(text):
    fh = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
    fh.write(text.encode("utf-8"))
    fh.close()
    return fh.name


class ReadCsvTests(unittest.TestCase):
    def test_header_with_hyphen_email_is_rejected(self):
        path = csv_file("﻿Matrícula;Nome;E-mail;Curso;Situação\n"
                        "1;Ana;ana@x.br;Direito;Ativo\n")
        # Cabeçalho com acento não bate com as colunas exigidas: deve falhar claro.
        with self.assertRaises(sp.ConfigError):
            sp.read_csv(path, [])

    def test_valid_file_and_status_normalisation(self):
        path = csv_file("matricula;nome;email;curso;situacao\n"
                        "1;Ana;ana@x.br;Direito;Ativo\n"
                        "2;Bruno;;Direito;TRANCADO\n")
        errors = []
        rows = sp.read_csv(path, errors)
        self.assertEqual(errors, [])
        self.assertEqual([r["status"] for r in rows], [sp.ACTIVE, sp.INACTIVE])
        self.assertEqual(rows[0]["line"], 2)

    def test_bad_rows_are_reported_not_synced(self):
        path = csv_file("matricula,nome,email,curso,situacao\n"
                        "1,Ana,ana@x.br,Direito,Ativo\n"
                        ",Sem matrícula,,Direito,Ativo\n"
                        "3,Caio,caio-sem-arroba,Direito,Ativo\n"
                        "4,Dora,dora@x.br,Direito,Formado\n"
                        "1,Repetida,,Direito,Ativo\n")
        errors = []
        rows = sp.read_csv(path, errors)
        self.assertEqual([r["matricula"] for r in rows], ["1"])
        self.assertEqual(len(errors), 4)
        self.assertIn("matrícula vazia", errors[0][2])
        self.assertIn("e-mail inválido", errors[1][2])
        self.assertIn("situação desconhecida", errors[2][2])
        self.assertIn("repetida", errors[3][2])

    def test_missing_column_is_a_config_error(self):
        path = csv_file("matricula;nome;curso;situacao\n1;Ana;Direito;Ativo\n")
        with self.assertRaises(sp.ConfigError) as ctx:
            sp.read_csv(path, [])
        self.assertIn("email", str(ctx.exception))

    def test_sample_file_is_valid(self):
        errors = []
        rows = sp.read_csv(os.path.join(os.path.dirname(HERE), "alunos-exemplo.csv"),
                           errors)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 6)


class PlanRowTests(unittest.TestCase):
    def row(self, **kw):
        base = {"matricula": "1", "nome": "Ana", "email": "ana@x.br",
                "curso": "Engenharia Civil", "status": sp.ACTIVE,
                "situacao": "Ativo", "line": 2}
        base.update(kw)
        return base

    def test_create_active_new_patron(self):
        action, body, notes = sp.plan_row(self.row(), None, CFG)
        self.assertEqual(action, "create")
        self.assertEqual(body, {"cardnumber": "1", "surname": "Ana",
                                "category_id": "GRAD", "library_id": "CENTRAL",
                                "email": "ana@x.br"})
        self.assertEqual(notes, [])

    def test_inactive_new_patron_is_not_created(self):
        action, body, _ = sp.plan_row(self.row(status=sp.INACTIVE), None, CFG)
        self.assertEqual(action, "skip_inactive")
        self.assertEqual(body, {})

    def test_unmapped_course_uses_default_and_warns(self):
        action, body, notes = sp.plan_row(self.row(curso="Filosofia"), None, CFG)
        self.assertEqual(body["category_id"], "ALUNO")
        self.assertTrue(notes and "sem categoria mapeada" in notes[0])

    def test_update_changed_fields_only(self):
        existing = {"patron_id": 7, "surname": "Ana", "email": "velho@x.br",
                    "category_id": "GRAD", "restricted": False}
        action, body, _ = sp.plan_row(self.row(), existing, CFG)
        self.assertEqual(action, "update")
        self.assertEqual(body, {"email": "ana@x.br"})

    def test_unchanged_patron(self):
        existing = {"patron_id": 7, "surname": "Ana", "email": "ana@x.br",
                    "category_id": "GRAD", "restricted": False}
        action, body, _ = sp.plan_row(self.row(), existing, CFG)
        self.assertEqual((action, body), ("unchanged", {}))

    def test_inactive_existing_patron_gets_restricted(self):
        existing = {"patron_id": 7, "surname": "Ana", "email": "ana@x.br",
                    "category_id": "GRAD", "restricted": False}
        action, body, _ = sp.plan_row(self.row(status=sp.INACTIVE), existing, CFG)
        self.assertEqual(action, "update")
        self.assertEqual(body, {"restricted": True})

    def test_already_restricted_is_not_rewritten(self):
        existing = {"patron_id": 7, "surname": "Ana", "email": "ana@x.br",
                    "category_id": "GRAD", "restricted": True}
        action, _, _ = sp.plan_row(self.row(status=sp.INACTIVE), existing, CFG)
        self.assertEqual(action, "unchanged")

    def test_active_patron_is_never_unrestricted(self):
        # Um bloqueio posto pela biblioteca não é desfeito pelo sincronismo.
        existing = {"patron_id": 7, "surname": "Ana", "email": "ana@x.br",
                    "category_id": "GRAD", "restricted": True}
        action, body, _ = sp.plan_row(self.row(), existing, CFG)
        self.assertEqual((action, body), ("unchanged", {}))


class FakeClient:
    def __init__(self, patrons=None, fail_on=None):
        self.patrons = patrons or {}
        self.fail_on = fail_on or set()
        self.writes = []

    def find_patron(self, cardnumber):
        return self.patrons.get(cardnumber)

    def create_patron(self, body):
        if body["cardnumber"] in self.fail_on:
            raise sp.KohaError(400, "boom")
        self.writes.append(("create", body))

    def update_patron(self, patron_id, body):
        self.writes.append(("update", patron_id, body))

    def check_auth(self):
        pass


class RunTests(unittest.TestCase):
    CSV = ("matricula;nome;email;curso;situacao\n"
           "1;Ana;ana@x.br;Engenharia Civil;Ativo\n"
           "2;Bruno;bruno@x.br;Direito;Trancado\n"
           "3;Carla;carla@x.br;Pedagogia;Ativo\n")

    def setUp(self):
        self.cfg_path = tempfile.NamedTemporaryFile("w", suffix=".json",
                                                    delete=False)
        json.dump(dict(CFG, log_file=os.path.join(tempfile.gettempdir(),
                                                  "sp-test.log"),
                       lock_file=os.path.join(tempfile.gettempdir(),
                                              "sp-test.lock")),
                  self.cfg_path)
        self.cfg_path.close()
        self.env = mock.patch.dict(os.environ, {
            "KOHA_URL": "https://koha.test", "KOHA_API_USER": "u",
            "KOHA_API_PASSWORD": "p"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        os.unlink(self.cfg_path.name)

    def run_with(self, client, *extra):
        path = csv_file(self.CSV)
        with mock.patch.object(sp, "KohaClient", return_value=client):
            return sp.run([path, "-c", self.cfg_path.name, *extra])

    def test_dry_run_writes_nothing(self):
        client = FakeClient()
        self.assertEqual(self.run_with(client), 0)
        self.assertEqual(client.writes, [])

    def test_apply_creates_and_restricts(self):
        client = FakeClient(patrons={
            "2": {"patron_id": 22, "surname": "Bruno", "email": "bruno@x.br",
                  "category_id": "GRAD", "restricted": False}})
        self.assertEqual(self.run_with(client, "--apply"), 0)
        # Ana (nova, ativa) e Carla (nova, ativa) são criadas; Bruno é bloqueado.
        kinds = [w[0] for w in client.writes]
        self.assertEqual(kinds, ["create", "update", "create"])
        self.assertEqual(client.writes[1], ("update", 22, {"restricted": True}))

    def test_mass_restriction_guard_aborts_before_writes(self):
        client = FakeClient(patrons={
            "2": {"patron_id": 22, "surname": "Bruno", "email": "bruno@x.br",
                  "category_id": "GRAD", "restricted": False}})
        code = self.run_with(client, "--apply", "--max-restrictions", "0")
        self.assertEqual(code, 1)
        self.assertEqual(client.writes, [])

    def test_api_error_on_one_row_does_not_stop_the_rest(self):
        client = FakeClient(fail_on={"1"})
        self.assertEqual(self.run_with(client, "--apply"), 1)
        self.assertEqual([w[0] for w in client.writes], ["create"])
        self.assertEqual(client.writes[0][1]["cardnumber"], "3")

    def test_missing_credentials_exit_2(self):
        with mock.patch.dict(os.environ, {"KOHA_API_PASSWORD": ""}):
            self.assertEqual(self.run_with(FakeClient()), 2)


class HttpLayerTests(unittest.TestCase):
    """Servidor local que imita /api/v1/patrons para checar o que sai na rede."""

    def setUp(self):
        self.seen = []
        seen = self.seen

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, payload):
                body = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                seen.append(("GET", self.path, self.headers.get("Authorization"), None))
                if self.headers.get("Authorization") != "Basic " + base64.b64encode(
                        b"u:p").decode():
                    return self._send(401, {"error": "Unauthorized"})
                self._send(200, [])

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(n))
                seen.append(("POST", self.path, None, data))
                self._send(201, {"patron_id": 99})

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_lookup_and_create_wire_format(self):
        client = sp.KohaClient(self.base, "u", "p")
        self.assertIsNone(client.find_patron("123"))
        client.create_patron({"cardnumber": "123", "surname": "Ana",
                              "category_id": "GRAD", "library_id": "CENTRAL"})
        get, post = self.seen
        self.assertEqual(get[0], "GET")
        parsed = urllib.parse.urlparse(get[1])
        self.assertEqual(parsed.path, "/api/v1/patrons")
        self.assertEqual(json.loads(urllib.parse.parse_qs(parsed.query)["q"][0]),
                         {"cardnumber": "123"})
        self.assertTrue(get[2].startswith("Basic "))
        self.assertEqual(post[0], "POST")
        self.assertEqual(post[3]["cardnumber"], "123")

    def test_wrong_password_raises_koha_error_with_status(self):
        client = sp.KohaClient(self.base, "u", "errada")
        with self.assertRaises(sp.KohaError) as ctx:
            client.check_auth()
        self.assertEqual(ctx.exception.status, 401)


if __name__ == "__main__":
    unittest.main()
