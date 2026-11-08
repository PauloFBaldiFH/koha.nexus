# Instalação experimental utilizável (1.5.185)

A instalação anteriormente parava se `/etc/koha-nexus/dspace-images.json` não
existisse. Esse catálogo não era distribuído pelo fluxo normal: o usuário via
um botão de instalação sem conseguir instalar. Esta etapa elimina a dependência
manual do catálogo e da publicação no GHCR.

## Comportamento

O assistente verifica a configuração de imagens. Se ainda não existir catálogo,
instala/inicia as dependências com as confirmações existentes e oferece preparar
as imagens no próprio servidor. Baixa as fontes das versões fixadas, aplica as
mesmas correções da CI, compila backend/interface/Solr, executa os smoke tests e
registra os IDs imutáveis locais. Depois segue o plano normal de instalação,
migração e criação assistida de administrador. Publicar imagens em registro não
é necessário para esse fluxo.

A compilação pode levar 30–90 minutos ou mais e exige espaço e memória adicionais
além do uso normal do DSpace (a interface pode usar até 4 GiB de heap na compilação).
Não é apenas um download de imagens prontas. Saída de compilação fica visível no
log da tarefa. Cancelar a confirmação não inicia a preparação.

Somente imagens ausentes/sem identidade correspondente são reconstruídas numa
nova tentativa. As fontes já preparadas são verificadas antes da reutilização.
O catálogo só aparece depois de todos os smoke tests passarem; um catálogo
preexistente nunca é sobrescrito automaticamente. Os dados das aplicações não
fazem parte do contexto de build. Nenhuma imagem é publicada por esta tarefa.

## Uso

Pelo painel: DSpace → Instalar → confirmar dependências e preparação → informar
endereço → confirmar plano → configurar administrador ou fazer depois.

CLI, depois de disponibilizar Docker/Buildx/Apache conforme o plano de dependências:

```bash
sudo config.sh --task dspace-panel availability
sudo config.sh --task dspace-panel prepare-images --confirm
sudo config.sh --task dspace-panel plan --url http://IP-DO-SERVIDOR:8100
sudo config.sh --task dspace-panel install --url http://IP-DO-SERVIDOR:8100 --confirm
```

A tarefa CLI `install --confirm` também prepara imagens quando não há catálogo.
Status/availability continuam somente leitura. Catálogos publicados e o modo de
laboratório existente continuam compatíveis. Uma configuração inválida existente
produz diagnóstico, em vez de ser silenciosamente substituída.

## Distribuição e continuidade

`platforms/dspace/build-inputs.zip` contém apenas receitas, ferramentas, patches
e licença. É gerado por `python3 tools/dspace_build_bundle.py`; seu SHA-256 fica
fixado no installer. A CI confere sua reprodução byte a byte. Não contém fontes
baixadas do DSpace, imagens compiladas, credenciais ou dados de instâncias.
Ao alterar qualquer entrada do kit, regenerar o ZIP, seu SHA no installer e
`installer.sha256`. O runtime continua com seu checksum próprio.

A aceitação integrada agora chama a preparação real pelo driver do installer,
sem `lab=True` nem catálogo manual, reutilizando as imagens construídas na CI.
Executa os smoke tests reais e segue com aplicação, navegador, backup/restauração
e demais verificações existentes. Isso verifica o caminho normal de ativação;
os builds sem cache continuam sendo executados pelos jobs de imagens quando
as receitas ainda não têm um arquivo idêntico em cache.

O estudo de múltiplas instâncias é independente e não entra nesta alteração.
