#!/usr/bin/env python3
"""Synthetic Biblioteca Fácil backup (.bkp) for the tests: the program's
DBISAM 4 tables (same fields, types and layout as the real ones), zlib
compressed in 64 KiB chunks inside its backup container. Every name, CPF
and title here is made up.

    bf_backup.py OUT.bkp            backup file
    bf_backup.py --folder DIR       the .dat files of a data folder
"""
import hashlib
import struct
import sys
import zlib
from datetime import date

SIG = bytes.fromhex("8abe8e592364cb403d71d2e3bc64d001")
S, D, B, SI, I = 1, 2, 4, 5, 6   # string, date, boolean, smallint, integer

SCHEMA = {
    "T01_USUA": ("Tabela de Usuarios", [("NUMUSUARIO", I), ("USUARIO", S, 20), ("SENHA", S, 20), ("NIVEL", SI), ("EXCLUSAO", D)]),
    "T03_CONF": ("Tabela de Configuracao", [("PEDESENHA", B), ("DIAS", SI), ("LIMITEITENSEMPR", SI), ("RODAPE", S, 60)]),
    "T04_LEIT": ("Cadastro de Leitores", [
        ("NUMLEITOR", I), ("LEITOR", S, 40), ("SEXO", SI), ("IDENTIDADE", S, 15), ("CPF", S, 15), ("NOMEPAI", S, 40),
        ("NOMEMAE", S, 40), ("ENDERECO", S, 40), ("BAIRRO", S, 20), ("CIDADE", S, 30), ("ESTADO", S, 2), ("CEP", S, 10),
        ("PONTOREFER", S, 40), ("INTERNET", S, 40), ("OBS1", S, 60), ("OBS2", S, 60), ("ESCOLARIDADE", S, 30),
        ("NATURALIDADE", S, 30), ("TELEFONE1", S, 20), ("TELEFONE2", S, 20), ("FONECONTATO", S, 20), ("NOMECONTATO", S, 20),
        ("DATACADASTRO", D), ("DATANASC", D), ("EXCLUSAO", D), ("DESATIVADO", B), ("MATRICULA", S, 10), ("TURMA", S, 10),
        ("TURNO", SI), ("FOTO", S, 90), ("SEXO2", S, 1), ("TURNO2", S, 10)]),
    "T05_AUTO": ("Cadastro de Autores", [("NUMAUTOR", I), ("AUTOR", S, 40), ("EXCLUSAO", D)]),
    "T06_EDIT": ("Cadastro de Editoras", [("NUMEDITORA", I), ("EDITORA", S, 40), ("EXCLUSAO", D), ("LOCALIZACAO", S, 20)]),
    "T07_CLAS": ("Cadastro de Classificação Literária", [("NUMCLASSIFIC", I), ("CLASSIFICACAO", S, 40), ("EXCLUSAO", D)]),
    "T08_TIPO": ("Cadastro de Tipos de Itens", [("NUMTIPOITEM", I), ("TIPOITEM", S, 40), ("EXCLUSAO", D), ("QTDDIAS", I)]),
    "T09_ACER": ("Cadastro do Acervo", [
        ("NUMACERVO", I), ("TITULO", S, 50), ("NUMEDITORA", I), ("NUMTIPOITEM", I), ("NUMCLASSIFIC", I), ("EXCLUSAO", D),
        ("EXEMPLAR", S, 5), ("VOLUME", S, 5), ("EDICAO", S, 5), ("ANOEDICAO", I), ("LOCAL", S, 5), ("AQUISICAO", D),
        ("BAIXA", D), ("PALAVRAS1", S, 60), ("PALAVRAS2", S, 60), ("OBS1", S, 60), ("OBS2", S, 60), ("EMPRESTADO", B),
        ("NAOEMPRESTAR", B), ("CDD", S, 20), ("ISBN", S, 15), ("TOMBO", I), ("FOTO", S, 90), ("CUTTER", S, 10),
        ("SUBTITULO", S, 50), ("PALAVRAS3", S, 60), ("PALAVRAS4", S, 60), ("PALAVRAS5", S, 60), ("ANOEDICAO2", S, 10),
        ("PAGINAS", I), ("CDU", S, 20), ("RESERVADO", B), ("NUMIDIOMA", I)]),
    "T10_AUAC": ("Cadastro de Autores nas Obras", [("SEQUENCIA", I), ("NUMACERVO", I), ("NUMAUTOR", I)]),
    "T11_MOVI": ("Cadastro da Movimentacao do Acervo", [
        ("NUMMOVIMENTO", I), ("NUMACERVO", I), ("PREVISAO", D), ("DEVOLUCAO", D), ("NUMEMPRESTIMO", I), ("EXCLUSAO", D), ("EXCLUIDOPOR", S, 10)]),
    "T12_INDC": ("Cadastro do Indice do Livro", [("SEQUENCIAL", I), ("NUMACERVO", I), ("INDICE", S, 60), ("PAGINA", I)]),
    "T13_MOVM": ("Tabela mestre de emprestimos", [("NUMEMPRESTIMO", I), ("NUMLEITOR", I), ("DATA", D), ("EXCLUSAO", D)]),
    "T14_IDIO": ("Cadastro dos idiomas", [("NUMIDIOMA", I), ("IDIOMA", S, 20), ("EXCLUSAO", D)]),
    "T15_RESE": ("Tabela de Reservas dos Livros", [
        ("NUMRESERVA", I), ("NUMLEITOR", I), ("NUMACERVO", I), ("DATA", D), ("VALIDADE1", D), ("VALIDADE2", D), ("UTILIZOU", B), ("EXCLUSAO", D)]),
}
ORDER = ["T01_USUA", "T02_ACES", "T03_CONF", "T04_LEIT", "T05_AUTO", "T06_EDIT", "T07_CLAS", "T08_TIPO",
         "T09_ACER", "T10_AUAC", "T11_MOVI", "T12_INDC", "T13_MOVM", "T14_IDIO", "T15_RESE"]
SCHEMA["T02_ACES"] = ("Tabela de Permissoes de Acesso", [("NUMACESSO", I), ("NUMUSUARIO", I), ("ACAO", S, 60), ("ACESSO", S, 1)])


def days(iso):
    return date.fromisoformat(iso).toordinal()   # 1 = 0001-01-01, as DBISAM


def table(name, rows, deleted=(), corrupt=()):
    desc, fields = SCHEMA[name]
    layout, off = [], 25
    for f in fields:
        ln = {S: (f[2] if len(f) > 2 else 0) + 1, D: 4, B: 2, SI: 2, I: 4}[f[1]]
        layout.append((f[0], f[1], ln, off))
        off += 1 + ln
    rs = (off + 7) // 8 * 8
    hdr = bytearray(512)
    active = len([r for r in rows])
    struct.pack_into("<Q", hdr, 0, len(rows) + len(deleted))
    hdr[8] = 6
    hdr[9:25] = SIG
    struct.pack_into("<IIIIIHH", hdr, 25, len(deleted), len(rows) + len(deleted) + 1, active, active, active, rs, len(fields))
    d = desc.encode("cp1252")
    hdr[72] = len(d)
    hdr[73:73 + len(d)] = d
    out = bytearray(hdr)
    for i, (fname, typ, ln, o) in enumerate(layout):
        fd = bytearray(768)
        full = (name[:3] + "_" + fname).encode()
        struct.pack_into("<H", fd, 0, i + 1)
        fd[2] = len(full)
        fd[3:3 + len(full)] = full
        fd[164] = typ
        fd[165] = 29 if i == 0 and typ == I else 0
        struct.pack_into("<H", fd, 166, ln - 1 if typ == S else 0)
        struct.pack_into("<H", fd, 169, ln)
        struct.pack_into("<I", fd, 172, o)
        out += fd
    allrows = [(r, 0) for r in rows] + [(r, 1) for r in deleted]
    for n, (r, status) in enumerate(allrows):
        rec = bytearray(rs)
        rec[0] = status
        struct.pack_into("<I", rec, 5, n + 1)
        for fname, typ, ln, o in layout:
            v = r.get(fname)
            if v is None:
                continue
            rec[o] = 1
            if typ == S:
                b = str(v).encode("cp1252")[:ln - 1]
                rec[o + 1:o + 1 + len(b)] = b
            elif typ == D:
                struct.pack_into("<i", rec, o + 1, days(v))
            elif typ in (B, SI):
                struct.pack_into("<h", rec, o + 1, int(v))
            else:
                struct.pack_into("<i", rec, o + 1, int(v))
        rec[9:25] = hashlib.md5(bytes(rec[25:])).digest()
        if r.get("_corrupt"):
            rec[40] ^= 0xFF
        out += rec
    return bytes(out)


def data():
    t = {k: [] for k in ORDER}
    dl = {k: [] for k in ORDER}
    t["T01_USUA"] = [{"NUMUSUARIO": 1, "USUARIO": "GERENTE", "SENHA": "segredo123", "NIVEL": 0}]
    t["T03_CONF"] = [{"PEDESENHA": 0, "DIAS": 7, "LIMITEITENSEMPR": 3, "RODAPE": "Biblioteca de teste"}]
    t["T05_AUTO"] = [{"NUMAUTOR": 1, "AUTOR": "Azevedo, Aluísio"}, {"NUMAUTOR": 2, "AUTOR": "MONTEIRO LOBATO"},
                     {"NUMAUTOR": 3, "AUTOR": "Autor Apagado", "EXCLUSAO": "2020-01-01"}, {"NUMAUTOR": 4, "AUTOR": "Coautora Teste"}]
    t["T06_EDIT"] = [{"NUMEDITORA": 1, "EDITORA": "Ática", "LOCALIZACAO": "São Paulo"}, {"NUMEDITORA": 2, "EDITORA": "Globo", "LOCALIZACAO": "Rio de Janeiro"}]
    t["T07_CLAS"] = [{"NUMCLASSIFIC": 1, "CLASSIFICACAO": "ROMANCE"}]
    t["T08_TIPO"] = [{"NUMTIPOITEM": 1, "TIPOITEM": "LIVRO", "QTDDIAS": 7}, {"NUMTIPOITEM": 2, "TIPOITEM": "Revista", "QTDDIAS": 3}]
    t["T14_IDIO"] = [{"NUMIDIOMA": 1, "IDIOMA": "PORTUGUES"}, {"NUMIDIOMA": 2, "IDIOMA": "INGLES"}]
    acer = t["T09_ACER"]
    # Two copies of one title (one record, two items), a magazine, a copy removed
    # in the program, a withdrawn copy with a repeated tombo, and filler copies
    # that push the table past one 64 KiB compression chunk.
    acer.append({"NUMACERVO": 1, "TITULO": "O cortiço", "NUMEDITORA": 1, "NUMTIPOITEM": 1, "NUMCLASSIFIC": 1, "EXEMPLAR": "1",
                 "EDICAO": "2", "ANOEDICAO2": "1997", "LOCAL": "EST1", "AQUISICAO": "2020-03-05", "PALAVRAS1": "Romance brasileiro",
                 "PALAVRAS2": "Naturalismo", "CDD": "869.3", "ISBN": "978-85-08-00001-3", "TOMBO": 1001, "CUTTER": "A994c",
                 "PAGINAS": 240, "NUMIDIOMA": 1, "EMPRESTADO": 1})
    acer.append(dict(acer[0], NUMACERVO=2, EXEMPLAR="2", TOMBO=1002, EMPRESTADO=0))
    acer.append({"NUMACERVO": 3, "TITULO": "Revista Ciência Hoje", "SUBTITULO": "n. 300", "NUMEDITORA": 2, "NUMTIPOITEM": 2,
                 "ANOEDICAO": 2013, "TOMBO": 1003, "NAOEMPRESTAR": 1, "NUMIDIOMA": 1, "OBS1": "Doação"})
    acer.append({"NUMACERVO": 4, "TITULO": "Livro apagado", "EXCLUSAO": "2021-05-01", "TOMBO": 1004})
    acer.append({"NUMACERVO": 5, "TITULO": "A menina do narizinho arrebitado", "NUMEDITORA": 2, "NUMTIPOITEM": 1, "TOMBO": 1001,
                 "BAIXA": "2022-02-02", "ANOEDICAO2": "1920", "NUMIDIOMA": 2})
    for n in range(6, 106):
        acer.append({"NUMACERVO": n, "TITULO": f"Obra de enchimento {n}", "NUMEDITORA": 1, "NUMTIPOITEM": 1, "TOMBO": 2000 + n, "ANOEDICAO": 2000})
    dl["T09_ACER"] = [{"NUMACERVO": 900, "TITULO": "Registro excluído no DBISAM", "TOMBO": 9000}]
    t["T10_AUAC"] = [{"SEQUENCIA": 1, "NUMACERVO": 1, "NUMAUTOR": 1}, {"SEQUENCIA": 2, "NUMACERVO": 2, "NUMAUTOR": 1},
                     {"SEQUENCIA": 3, "NUMACERVO": 5, "NUMAUTOR": 2}, {"SEQUENCIA": 4, "NUMACERVO": 5, "NUMAUTOR": 4},
                     {"SEQUENCIA": 5, "NUMACERVO": 5, "NUMAUTOR": 3}, {"SEQUENCIA": 6, "NUMACERVO": 77777, "NUMAUTOR": 1}]
    t["T12_INDC"] = [{"SEQUENCIAL": 1, "NUMACERVO": 1, "INDICE": "Capítulo I", "PAGINA": 9},
                     {"SEQUENCIAL": 2, "NUMACERVO": 1, "INDICE": "Capítulo II", "PAGINA": 21}]
    t["T04_LEIT"] = [
        {"NUMLEITOR": 1, "LEITOR": "Maria da Silva Teste", "SEXO2": "F", "CPF": "529.982.247-25", "IDENTIDADE": "12.345.678-9",
         "ENDERECO": "Rua das Flores, 10", "BAIRRO": "Centro", "CIDADE": "Palotina", "ESTADO": "pr", "CEP": "85950-000",
         "INTERNET": "maria@example.org", "TELEFONE1": "(44) 3649-0000", "TELEFONE2": "(44) 99999-0000", "NOMEMAE": "Ana Teste",
         "DATANASC": "2010-04-15", "DATACADASTRO": "2019-02-01", "MATRICULA": "A123", "TURMA": "5A", "TURNO2": "MANHA"},
        {"NUMLEITOR": 2, "LEITOR": "João Pereira", "SEXO2": "M", "CPF": "111.111.111-11", "DESATIVADO": 1, "INTERNET": "sem email"},
        {"NUMLEITOR": 3, "LEITOR": "Leitor Removido", "EXCLUSAO": "2022-01-01"},
        {"NUMLEITOR": 4, "LEITOR": "Pedro Duplicado", "CPF": "52998224725"},
        {"NUMLEITOR": 5, "LEITOR": "Corrompido Teste", "_corrupt": True},
    ]
    t["T13_MOVM"] = [{"NUMEMPRESTIMO": 1, "NUMLEITOR": 1, "DATA": "2026-09-20"}, {"NUMEMPRESTIMO": 2, "NUMLEITOR": 2, "DATA": "2025-03-01"},
                     {"NUMEMPRESTIMO": 3, "NUMLEITOR": 3, "DATA": "2025-04-01"}, {"NUMEMPRESTIMO": 4, "NUMLEITOR": 1, "DATA": "2025-05-01", "EXCLUSAO": "2025-05-01"}]
    t["T11_MOVI"] = [
        {"NUMMOVIMENTO": 1, "NUMACERVO": 1, "PREVISAO": "2026-09-27", "NUMEMPRESTIMO": 1},                            # open
        {"NUMMOVIMENTO": 2, "NUMACERVO": 2, "PREVISAO": "2025-03-08", "DEVOLUCAO": "2025-03-07", "NUMEMPRESTIMO": 2},  # returned
        {"NUMMOVIMENTO": 3, "NUMACERVO": 2, "PREVISAO": "2025-04-08", "NUMEMPRESTIMO": 3},                            # removed patron
        {"NUMMOVIMENTO": 4, "NUMACERVO": 3, "PREVISAO": "2025-05-08", "NUMEMPRESTIMO": 4},                            # cancelled loan
        {"NUMMOVIMENTO": 5, "NUMACERVO": 3, "PREVISAO": "2025-03-08", "NUMEMPRESTIMO": 2, "EXCLUSAO": "2025-03-02", "EXCLUIDOPOR": "GERENTE"},
    ]
    t["T15_RESE"] = [
        {"NUMRESERVA": 1, "NUMLEITOR": 4, "NUMACERVO": 1, "DATA": "2026-09-25", "VALIDADE1": "2026-09-25", "VALIDADE2": "2099-12-31", "UTILIZOU": 0},
        {"NUMRESERVA": 2, "NUMLEITOR": 1, "NUMACERVO": 5, "DATA": "2026-09-26", "VALIDADE1": "2026-09-26", "VALIDADE2": "2099-12-31", "UTILIZOU": 0},
        {"NUMRESERVA": 3, "NUMLEITOR": 4, "NUMACERVO": 2, "DATA": "2026-09-27", "VALIDADE1": "2026-09-27", "VALIDADE2": "2099-12-31", "UTILIZOU": 0},
        {"NUMRESERVA": 4, "NUMLEITOR": 1, "NUMACERVO": 3, "DATA": "2020-01-01", "VALIDADE1": "2020-01-01", "VALIDADE2": "2020-01-15", "UTILIZOU": 0},
        {"NUMRESERVA": 5, "NUMLEITOR": 1, "NUMACERVO": 3, "DATA": "2026-09-01", "VALIDADE1": "2026-09-01", "VALIDADE2": "2099-12-31", "UTILIZOU": 1},
    ]
    return t, dl


def files():
    t, dl = data()
    out = {}
    for name in ORDER:
        rows = [r for r in t[name] if not r.get("_corrupt")]
        corrupt = [r for r in t[name] if r.get("_corrupt")]
        out[name + ".dat"] = table(name, rows + corrupt, dl[name])
        out[name + ".idx"] = bytes(4096)
    return out


def backup(path):
    f = files()
    desc = "Backup do dia 30/09/2026 08:15:18".encode("cp1252")
    b = bytearray(SIG)
    b += struct.pack("<Qd", 43100, 46295.34396)
    b += bytes([len(desc)]) + desc + struct.pack("<I", len(ORDER))
    for name in ORDER:
        b += bytes([len(name)]) + name.encode()
    for name in (n + e for n in ORDER for e in (".dat", ".idx")):
        data_ = f[name]
        b += bytes([len(name)]) + name.encode()
        if name.endswith(".dat"):
            b += bytes(4)
        b += struct.pack("<Q", len(data_)) + bytes.fromhex("66eb29c23d5d54407f7ce2d94d97645b") + b"\x06"
        for i in range(0, len(data_), 65536):
            z = zlib.compress(data_[i:i + 65536], 6)
            b += struct.pack("<I", len(z)) + z
    with open(path, "wb") as fh:
        fh.write(b)


if __name__ == "__main__":
    if sys.argv[1] == "--folder":
        import os
        os.makedirs(sys.argv[2], exist_ok=True)
        for name, content in files().items():
            with open(os.path.join(sys.argv[2], name), "wb") as fh:
                fh.write(content)
    else:
        backup(sys.argv[1])
