#!/usr/bin/env python3
"""Synthetic ISIS export (PostgreSQL pg_dump of the "acervo" and
"ocorrencias" tables) for the ISIS importer tests. Made-up records only.

    isis_dump.py OUT [--inserts] [--gzip] [--latin1] [--cut] [--no-noise]

The file carries the quirks of the real exports: noise before and after the
dump, Windows line ends, "Informação não encontrada" fillers, ª read as Ẃ,
<O> articles, <A><B> subjects and tombo fields such as "-2134 I^f2135 II",
"-3404^3462", "669 a 672", "12730(Baixa)", "2717$" and "d^12452".
"""
import gzip
import sys

COLS = ("mfn, tipo, idioma, centro_cooperante, n_chamada, registro, aut_pes, aut_ent, aut_ev, titulo, edicao, "
        "local_editor, _data, colacao_mon_e_an_mon, colacao_an_per, serie, notas_gerais, nota_de_publ_c, nota_de_tese, "
        "nota_de_cont, nota_de_convenio, aut_pes_todo, aut_ent_todo, aut_ev_todo, titulo_todo, assunto, aut_sec_pes, "
        "aut_sec_ent, aut_sec_ev").split(", ")
NF = "Informação não encontrada "


def rec(mfn, **kw):
    r = {c: None for c in COLS}
    r.update(mfn=str(mfn), tipo="M", idioma="POR")
    r.update(kw)
    return r


ROWS = [
    rec(1, n_chamada="869.3 A994c", registro="-1001", aut_pes="AZEVEDO, ALUISIO", titulo="<O> CORTIÇO",
        edicao="2Ẃ ed", local_editor="Sao Paulo Atica", _data="1990", colacao_mon_e_an_mon="220 p",
        assunto="<ROMANCE BRASILEIRO><LITERATURA BRASILEIRA>", aut_ev=NF, colacao_an_per="  "),
    rec(2, tipo="m ", idioma="ING", n_chamada="823 A95", registro="-2134 I^f2135 II^f2136 III", aut_pes="AUSTEN, JANE",
        titulo="PERSUASAO^CEDICAO ESPECIAL", local_editor="RIO GRANDE DO SUL: L&PM POCKET, 2018", _data="2022-09-13",
        assunto="FICÇÃO INGLESA; ROMANCE"),
    rec(3, n_chamada="310\x02 T58", registro="-3377 - 3404^3462 - 18705^ - d^12452", aut_ent="IBGE",
        titulo="CENSO DEMOGRAFICO", local_editor="Rio de Janeiro IBGE", _data="1991", notas_gerais="<Falta volume 4>"),
    rec(4, registro="-669 a 672", aut_pes="CANSI, BERNARDO <FREI>", titulo="INTRODUçãO A TEOLOGIA",
        local_editor="Petropolis: Vozes, 1985", _data="22/05/2013", aut_sec_pes="SILVA, JOSE; SOUZA, MARIA"),
    rec(5, registro="-148 - 2717$ - 12730(Baixa) - 516 (atrasado)", titulo="MANUAL DE \\\\IDENTIFICAÇÃO\\t ",
        local_editor="Curitiba Fundacao Cultural"),
    rec(6, registro="-1001 - 1655 v1 - 1656 v2 - 1657 v3", titulo="HISTORIA DO PARANA", aut_pes="WACHOWICZ, RUY",
        local_editor="Curitiba", _data="1988"),
    rec(7, registro="-", titulo="SEM TOMBO", local_editor=NF, idioma="\\N"),
    rec(8, registro="-9001", titulo=NF),
    rec(9, registro="- 4475 v2 - 4779 v54495 v6 - 863 M42 - 9010", titulo="ENCICLOPEDIA", idioma="esp"),
]
OCC = [("12730", "O LIVRO FOI EXTRAVIADO PELA LEITORA N°1049.\r\nOBS. SEM REPOSIçãO.", "t", "2021-01-29"),
       ("", "", "f", "2021-01-29"),
       ("1655", "Capa danificada", "f", "2021-02-04")]


def copy_field(v):
    if v is None:
        return "\\N"
    return v.replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


def sql_lit(v):
    if v is None:
        return "NULL"
    return "'" + v.replace("'", "''") + "'"


def main():
    args = sys.argv[1:]
    out = args[0]
    inserts, gz, latin1, cut, noise = "--inserts" in args, "--gzip" in args, "--latin1" in args, "--cut" in args, "--no-noise" not in args
    enc = "LATIN1" if latin1 else "UTF8"
    L = ["--", "-- PostgreSQL database dump", "--", "", "-- Dumped from database version 10.20",
         "-- Dumped by pg_dump version 10.20", "", "SET statement_timeout = 0;", f"SET client_encoding = '{enc}';",
         "SET standard_conforming_strings = on;", "", "CREATE TABLE public.acervo ("]
    L += [f"    {c} {'integer NOT NULL' if c == 'mfn' else 'text'}," for c in COLS[:-1]] + [f"    {COLS[-1]} text", ");", ""]
    L += ["CREATE TABLE public.ocorrencias (", "    cod_livro character varying(60),", "    ocorrencia character varying(100000),",
          "    extraviado boolean,", "    data_registro date", ");", ""]
    if inserts:
        for r in ROWS:
            L.append(f"INSERT INTO public.acervo VALUES ({', '.join(sql_lit(r[c]) for c in COLS)});")
        for o in OCC:
            L.append("INSERT INTO public.ocorrencias (cod_livro, ocorrencia, extraviado, data_registro) VALUES ("
                     + f"{sql_lit(o[0])}, E{sql_lit(o[1]).replace(chr(13), '').replace(chr(10), chr(92) + 'n')}, {'true' if o[2] == 't' else 'false'}, '{o[3]}');")
    else:
        L.append(f"COPY public.acervo ({', '.join(COLS)}) FROM stdin;")
        L += ["\t".join(copy_field(r[c]) for c in COLS) for r in ROWS]
        L += ["\\.", "", "COPY public.ocorrencias (cod_livro, ocorrencia, extraviado, data_registro) FROM stdin;"]
        L += ["\t".join(copy_field(x) for x in o) for o in OCC] + ["\\."]
    L += ["", "SELECT pg_catalog.setval('public.acervo_mfn_seq', 9, true);", "", "--", "-- PostgreSQL database dump complete", "--", ""]
    text = "\r\n".join(L)
    if latin1:
        text = text.replace("Ẃ", "ª")  # the Latin-1 export has the real ª
    data = text.encode("cp1252" if latin1 else "utf-8", errors="replace" if latin1 else "strict")
    if cut:
        data = data[: data.index(b"\\.")]  # ends inside the COPY data of acervo
        data = data[: data.rindex(b"\t")]  # the last row is cut in the middle
    if noise:
        data = b"\x00\x13\xff\xfeJUNK\x07backup-header\x1a\r\n" + data + b"\r\n\x00\x00TRAILER\xff\x1a garbage"
    if gz:
        data = gzip.compress(data)
    with open(out, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
