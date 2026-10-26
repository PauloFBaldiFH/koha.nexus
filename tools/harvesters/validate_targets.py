import argparse
import time
import yaml
import httpx
from lxml import etree

OAI_NS = "http://www.openarchives.org/OAI/2.0/"
NS = {"oai": OAI_NS}

HEADERS = {
    "User-Agent": "KohaNexus-Harvester/1.0"
}


def consultar(client, url, verb):
    try:
        response = client.get(url, params={"verb": verb})

        print(f"  {verb}: HTTP {response.status_code}")
        print(f"  URL final: {response.url}")

        try:
            root = etree.fromstring(response.content)
        except etree.XMLSyntaxError:
            print("  ERRO: a resposta não é XML válido.")
            print("  Conteúdo recebido:", response.text[:180].replace("\n", " "))
            return

        erros = root.xpath(
            "/oai:OAI-PMH/oai:error",
            namespaces=NS,
        )

        if erros:
            for erro in erros:
                print(
                    f"  ERRO OAI [{erro.get('code', '?')}]: "
                    f"{(erro.text or '').strip()}"
                )
            return

        if verb == "Identify":
            nome = root.xpath(
                "string(/oai:OAI-PMH/oai:Identify/oai:repositoryName)",
                namespaces=NS,
            )
            base = root.xpath(
                "string(/oai:OAI-PMH/oai:Identify/oai:baseURL)",
                namespaces=NS,
            )
            versao = root.xpath(
                "string(/oai:OAI-PMH/oai:Identify/oai:protocolVersion)",
                namespaces=NS,
            )
            print(f"  Repositório: {nome or '(não informado)'}")
            print(f"  Base OAI: {base or '(não informada)'}")
            print(f"  Versão: {versao or '(não informada)'}")

        elif verb == "ListMetadataFormats":
            formatos = root.xpath(
                "/oai:OAI-PMH/oai:ListMetadataFormats/"
                "oai:metadataFormat/oai:metadataPrefix/text()",
                namespaces=NS,
            )
            print(f"  Formatos: {', '.join(formatos) if formatos else '(nenhum encontrado)'}")
            print(f"  MARC21 disponível: {'SIM' if 'marc21' in formatos else 'NÃO CONFIRMADO'}")

    except httpx.HTTPError as exc:
        print(f"  FALHA DE CONEXÃO: {type(exc).__name__}: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Confere Identify e ListMetadataFormats dos alvos OAI-PMH de um targets.yaml.")
    parser.add_argument("targets", nargs="?", default="targets.yaml", help="arquivo YAML com a lista targets (padrao: ./targets.yaml)")
    caminho = parser.parse_args().targets

    with open(caminho, "r", encoding="utf-8") as arquivo:
        config = yaml.safe_load(arquivo) or {}

    targets = config.get("targets", [])

    if not targets:
        print(f"Nenhum alvo encontrado em {caminho}.")
        return

    with httpx.Client(
        timeout=25.0,
        follow_redirects=True,
        headers=HEADERS,
    ) as client:

        for target in targets:
            print("\n" + "=" * 65)
            print(f"Servidor: {target.get('name', target.get('id', '?'))}")
            print(f"Tipo: {target.get('type', 'não informado')}")

            if target.get("type") != "oai-pmh":
                print("  PULADO: requer um conector específico.")
                continue

            url = target.get("url", "").strip()

            if not url.startswith(("http://", "https://")):
                print(f"  URL inválida: {url!r}")
                continue

            intervalo = float(target.get("rate_limit_seconds", 1.5))

            consultar(client, url, "Identify")
            time.sleep(intervalo)
            consultar(client, url, "ListMetadataFormats")
            time.sleep(intervalo)


if __name__ == "__main__":
    main()
