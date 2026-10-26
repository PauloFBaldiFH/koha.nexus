import re
import unicodedata
from urllib.parse import unquote
from lxml import etree

# Namespaces padrão para OAI-PMH e MARCXML
NS = {
    'oai': 'http://www.openarchives.org/OAI/2.0/',
    'marc': 'http://www.loc.gov/MARC21/slim'
}

TAGS_ESSENCIAIS = {
    '020', '041', '080', '082', '090', '092', '100', '110', '111',
    '240', '245', '250', '260', '264', '300', '490', '500', '505',
    '520', '600', '610', '650', '651', '700', '710', '856'
}

def limpar_texto(texto: str) -> str:
    if not texto:
        return ""
    texto = unicodedata.normalize('NFKD', texto)
    texto = re.sub(r'[^\w\s]', '', texto)
    return " ".join(texto.lower().split())

def limpar_isbn(isbn_raw: str) -> str:
    if not isbn_raw:
        return ""
    numeros = re.sub(r'[^0-9Xx]', '', isbn_raw)
    return numeros.upper()

# ---------------------------------------------------------
# PROCESSADOR MARCXML (Para OAI-PMH e Web)
# ---------------------------------------------------------
def extrair_e_podar(record_elem) -> dict | None:
    marc_rec = record_elem.xpath('.//marc:record', namespaces=NS)
    if not marc_rec:
        return None
    rec = marc_rec[0]

    # Extrai Título (245)
    titulos = rec.xpath('.//marc:datafield[@tag="245"]//marc:subfield[@code="a"]/text()', namespaces=NS)
    if not titulos:
        return None
    titulo_original = titulos[0].strip()

    # Extrai Autor (100 ou 110)
    autores = rec.xpath('.//marc:datafield[@tag="100" or @tag="110"]//marc:subfield[@code="a"]/text()', namespaces=NS)
    autor_original = autores[0].strip() if autores else ""

    # Extrai ISBN (020)
    isbns = rec.xpath('.//marc:datafield[@tag="020"]//marc:subfield[@code="a"]/text()', namespaces=NS)
    isbn = limpar_isbn(isbns[0]) if isbns else ""

    # Extrai Ano (260/264)
    datas = rec.xpath('.//marc:datafield[@tag="260" or @tag="264"]//marc:subfield[@code="c"]/text()', namespaces=NS)
    ano = None
    if datas:
        m = re.search(r'\b(1[89]\d{2}|20\d{2})\b', datas[0])
        if m:
            ano = m.group(1)

    # Extrai CDD / CDU
    cdd_list = rec.xpath('.//marc:datafield[@tag="082"]//marc:subfield[@code="a"]/text()', namespaces=NS)
    cdu_list = rec.xpath('.//marc:datafield[@tag="080"]//marc:subfield[@code="a"]/text()', namespaces=NS)

    # Poda tags desnecessárias
    for df in rec.xpath('.//marc:datafield', namespaces=NS):
        tag = df.get('tag')
        if tag not in TAGS_ESSENCIAIS:
            rec.remove(df)

    xml_limpo = etree.tostring(rec, encoding='utf-8').decode('utf-8')

    return {
        "isbn": isbn,
        "titulo_busca": limpar_texto(titulo_original),
        "autor_busca": limpar_texto(autor_original),
        "titulo_original": titulo_original,
        "autor_original": autor_original,
        "ano": ano,
        "cdd": cdd_list[0].strip() if cdd_list else None,
        "cdu": cdu_list[0].strip() if cdu_list else None,
        "marcxml_clean": xml_limpo
    }

# ---------------------------------------------------------
# PROCESSADOR ISO-2709 RAW (Para Zeus / Z39.50)
# ---------------------------------------------------------
def extrair_raw_marc(raw_str: str) -> dict | None:
    if not raw_str:
        return None

    if '%' in raw_str:
        raw_str = unquote(raw_str)

    FIELD_SEP = '\x1e'
    SUBFIELD_SEP = '\x1f'

    campos = raw_str.split(FIELD_SEP)
    dados = {'020': [], '080': [], '082': [], '100': [], '110': [], '245': [], '260': [], '264': []}

    for campo in campos:
        subcampos = campo.split(SUBFIELD_SEP)
        cabecalho = subcampos[0]
        tag_match = re.search(r'\b(\d{3})\b', cabecalho)
        if not tag_match:
            continue
        tag = tag_match.group(1)

        if tag in dados:
            conteudo = ' '.join(subcampos[1:]) if len(subcampos) > 1 else cabecalho
            dados[tag].append(conteudo)

    titulo_raw = dados['245'][0] if dados['245'] else ""
    if not titulo_raw.strip():
        return None

    isbn_raw = dados['020'][0] if dados['020'] else ""
    autor_raw = (dados['100'] or dados['110'] or [""])[0]
    ano_raw = (dados['260'] or dados['264'] or [""])[0]
    cdd_raw = dados['082'][0] if dados['082'] else ""
    cdu_raw = dados['080'][0] if dados['080'] else ""

    ano_match = re.search(r'\b(1[89]\d{2}|20\d{2})\b', ano_raw)
    ano = ano_match.group(1) if ano_match else None

    return {
        "isbn": limpar_isbn(isbn_raw),
        "titulo_busca": limpar_texto(titulo_raw),
        "autor_busca": limpar_texto(autor_raw),
        "titulo_original": titulo_raw.strip(),
        "autor_original": autor_raw.strip(),
        "ano": ano,
        "cdd": cdd_raw.strip() if cdd_raw else None,
        "cdu": cdu_raw.strip() if cdu_raw else None,
        "marc_raw": raw_str
    }
