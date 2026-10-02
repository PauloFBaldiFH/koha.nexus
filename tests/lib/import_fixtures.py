#!/usr/bin/env python3
"""Synthetic files for the Magic Import Tool tests (no real catalogue or
patron data): workbooks (XLSX, ODS, and XLS when python3-xlwt is
installed), a dBase table with its memo file, a Koha backup header and a
spreadsheet without a header row. Written with the standard library only.

    import_fixtures.py DIR
"""
import os
import struct
import sys
import zipfile
from xml.sax.saxutils import escape

BOOKS = [
    ["Tombo", "Título", "Autor", "ISBN", "Editora", "Ano", "Data de aquisição", "Leitor", "CPF do leitor", "E-mail do leitor"],
    ["5001", "Dom Casmurro", "Machado de Assis", "8508040423", "Ática", "1997", 45000, "Ana Maria Souza", "529.982.247-25", "ana@exemplo.br"],
    ["5002", "Dom Casmurro", "Machado de Assis", "8508040423", "Ática", "1997", 45000, "", "", ""],
    ["5003", "Vidas secas", "Graciliano Ramos", "", "Record", "2003", "", "João Lima", "111.444.777-35", ""],
    ["5004", "O alienista", "Machado de Assis", "", "Ática", "2001", "", "Pedro Errado", "123.456.789-00", ""],
]
PATRONS = [
    ["Matrícula", "Nome", "CPF", "E-mail", "Data de nascimento"],
    ["A1", "Bia Rocha", "390.533.447-05", "bia@exemplo.br", "10/04/2010"],
    ["A2", "Caio Reis", "", "caio@exemplo.br", "01/02/2011"],
    ["A3", "Duda Sem Documento", "", "", ""],
]
LOANS = [
    ["Tombo", "Matrícula", "Data do empréstimo", "Data de devolução"],
    ["5001", "A1", "2026-09-01", "2026-09-08"],
]


def col(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def xlsx(path, sheets):
    shared, index = [], {}

    def sidx(s):
        if s not in index:
            index[s] = len(shared)
            shared.append(s)
        return index[s]

    sheet_xml = []
    for name, rows in sheets:
        out = ['<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for r, row in enumerate(rows, 1):
            out.append('<row r="%d">' % r)
            for c, v in enumerate(row):
                ref = "%s%d" % (col(c), r)
                if v == "":
                    continue
                if isinstance(v, int):
                    # Numbers in a date column carry the date style (s="1").
                    out.append('<c r="%s" s="1"><v>%d</v></c>' % (ref, v))
                elif v.isdigit() and c > 0 and rows[0][c] == "Ano":
                    out.append('<c r="%s"><v>%s</v></c>' % (ref, v))
                else:
                    out.append('<c r="%s" t="s"><v>%d</v></c>' % (ref, sidx(v)))
            out.append("</row>")
        out.append("</sheetData></worksheet>")
        sheet_xml.append("".join(out))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (escape(n), i, i) for i, (n, _) in enumerate(sheets, 1))
                   + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join('<Relationship Id="rId%d" Type="worksheet" Target="worksheets/sheet%d.xml"/>' % (i, i) for i in range(1, len(sheets) + 1))
                   + "</Relationships>")
        z.writestr("xl/styles.xml", '<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   '<cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>')
        z.writestr("xl/sharedStrings.xml", '<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   + "".join("<si><t>%s</t></si>" % escape(s) for s in shared) + "</sst>")
        for i, x in enumerate(sheet_xml, 1):
            z.writestr("xl/worksheets/sheet%d.xml" % i, x)


def ods(path, sheets):
    body = []
    for name, rows in sheets:
        body.append('<table:table table:name="%s">' % escape(name))
        for row in rows:
            body.append("<table:table-row>")
            for v in row:
                if isinstance(v, int):
                    body.append('<table:table-cell office:value-type="date" office:date-value="2023-03-15"><text:p>15/03/2023</text:p></table:table-cell>')
                elif v == "":
                    body.append('<table:table-cell table:number-columns-repeated="1"/>')
                else:
                    body.append('<table:table-cell office:value-type="string"><text:p>%s</text:p></table:table-cell>' % escape(v))
            body.append('<table:table-cell table:number-columns-repeated="1000"/></table:table-row>')
        body.append('<table:table-row table:number-rows-repeated="1048000"><table:table-cell table:number-columns-repeated="1024"/></table:table-row>')
        body.append("</table:table>")
    content = ('<?xml version="1.0" encoding="UTF-8"?><office:document-content '
               'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
               'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
               'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:spreadsheet>'
               + "".join(body) + "</office:spreadsheet></office:body></office:document-content>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet", compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)


def dbf(path):
    """dBase III table in code page 850 (DOS, as Clipper programs saved it)
    with a memo file, one deleted record."""
    fields = [("TOMBO", "C", 8), ("TITULO", "C", 40), ("AUTOR", "C", 30), ("EDITORA", "C", 20),
              ("ANO", "N", 4), ("AQUISICAO", "D", 8), ("OBS", "M", 10)]
    rows = [("7001", "Memórias póstumas de Brás Cubas", "Assis, Machado de", "Ática", "1998", "20200305", "1"),
            ("7002", "Memórias póstumas de Brás Cubas", "Assis, Machado de", "Ática", "1998", "20200305", ""),
            ("7003", "Apagado", "Ninguém", "", "", "", ""),
            ("7004", "A hora da estrela", "Lispector, Clarice", "Rocco", "1998", "", "")]
    rlen = 1 + sum(f[2] for f in fields)
    hlen = 32 + 32 * len(fields) + 1
    head = struct.pack("<BBBBIHH20x", 0x83, 126, 9, 30, len(rows), hlen, rlen)
    head = head[:29] + bytes([0x02]) + head[30:]
    desc = b"".join(struct.pack("<11sc4xBB14x", n.encode(), t.encode(), ln, 0) for n, t, ln in fields)
    recs = b""
    for i, r in enumerate(rows):
        rec = b"*" if r[1] == "Apagado" else b" "
        for (n, t, ln), v in zip(fields, r):
            b = v.encode("cp850")
            rec += (b.rjust(ln) if t in "NM" else b.ljust(ln))[:ln]
        recs += rec
    with open(path, "wb") as fh:
        fh.write(head + desc + b"\r" + recs + b"\x1a")
    memo = bytearray(b"\x02\x00\x00\x00" + b"\0" * 508)
    memo += ("Exemplar com dedicatória do autor.".encode("cp850") + b"\x1a\x1a").ljust(512, b"\0")
    with open(os.path.splitext(path)[0] + ".DBT", "wb") as fh:
        fh.write(bytes(memo))


def xls(path, sheets):
    try:
        import xlwt
    except ImportError:
        return False
    wb = xlwt.Workbook()
    date_style = xlwt.easyxf(num_format_str="DD/MM/YYYY")
    for name, rows in sheets:
        ws = wb.add_sheet(name)
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                if isinstance(v, int):
                    ws.write(r, c, v, date_style)
                elif v != "":
                    ws.write(r, c, v)
    wb.save(path)
    return True


def koha_dump(path):
    tables = ["action_logs", "biblio", "biblio_metadata", "borrowers", "items", "systempreferences"]
    with open(path, "w") as fh:
        fh.write("-- MariaDB dump 10.19  Distrib 10.11.6-MariaDB, for debian-linux-gnu (x86_64)\n--\n-- Host: localhost    Database: koha_library\n\n")
        for t in tables:
            fh.write("DROP TABLE IF EXISTS `%s`;\nCREATE TABLE `%s` (\n  `id` int(11) NOT NULL\n) ENGINE=InnoDB;\n\n" % (t, t))
        fh.write("-- Dump completed on 2026-09-30  2:00:01\n")


def main():
    d = sys.argv[1]
    os.makedirs(d, exist_ok=True)
    workbook = [("Livros", BOOKS), ("Leitores", PATRONS), ("Empréstimos", LOANS)]
    xlsx(os.path.join(d, "biblioteca.xlsx"), workbook)
    ods(os.path.join(d, "biblioteca.ods"), workbook)
    xls(os.path.join(d, "biblioteca.xls"), workbook)
    dbf(os.path.join(d, "ACERVO.DBF"))
    koha_dump(os.path.join(d, "koha-backup.sql"))
    with open(os.path.join(d, "sem-cabecalho.csv"), "w", encoding="utf-8") as fh:
        fh.write("9788535914849;A hora da estrela;Lispector, Clarice;8001\n"
                 "9788535914849;A hora da estrela;Lispector, Clarice;8002\n"
                 "9788520935069;Grande sertão: veredas;Rosa, João Guimarães;8003\n")


if __name__ == "__main__":
    main()
