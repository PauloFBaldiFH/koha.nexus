# Validação da entrega 0.1.0

Data: 5 de novembro de 2026.

## Ambiente executado

WordPress 6.8.3, PHP 8.3.28, MariaDB 11.4, Events Manager 7.4.13 original fornecido pelo usuário e Tainacan 1.4.1. Ambiente local descartável, publicado apenas em loopback, sem acesso ao servidor de produção.

O Tainacan usado foi reconstruído a partir da tag 1.4.1 do repositório oficial: dependências PHP do lock, dependências JavaScript via npm ci, webpack de produção e Sass. As URLs de distribuição dos pacotes PHP foram ajustadas apenas no ambiente de teste para o host público codeload.github.com, preservando os commits do lock, porque api.github.com foi bloqueado pela rede. Tainacan não é incluído no diretório entregue.

Não usamos um plugin Tainacan simulado. Não instalamos nem dependemos dos outros dois plugins de eventos para executar a extensão. O tema de teste foi Twenty Twenty-Five, não um tema específico do Tainacan.

## Resultado dos testes

- 54 verificações de integração PHP/WordPress passaram nesta PR, incluindo o manifesto da base descompactada e a recusa de arquivo adicional.
- 25 verificações HTTP/navegador Chromium passaram.
- Preparação incluída: instalação/ativação por confirmação e preservação de arquivos em preparação repetida passaram.
- Agenda sem Tainacan ativo passou.
- Desativação e reativação preservando comprovantes passaram.
- Lint de todos os seis arquivos PHP passou.
- Catálogo POT gerado pelo WP-CLI.
- A entrega anterior em ZIP foi reconhecida pelo WordPress. Nesta PR, o plugin e sua base estão descompactados; a preparação da base foi adaptada para cópia verificada dos arquivos.

## Integração funcional

Verificados: criação de esquema idempotente; uso de reservas reais da base; presença com chave única; repetição sem duplicação; bloqueio de presença prematura; bloqueio de emissão futura; emissão e snapshot; acentos; confirmação com passe; autorização do titular e da equipe; negação ao visitante sem token; reservas de grupo inelegíveis; cancelamento; CSV sem fórmula; coleções reais públicas e privadas; item do Tainacan com anexo e verificação de integridade do arquivo original; vínculos no editor; agenda com filtro de coleção; privacidade de eventos; exportação e apagamento de dados próprios; revogação; convidados sem conta; desfazimento serializado.

Os testes criam reservas como administrador usando as classes da base. Não são uma auditoria de concorrência ou de todos os fluxos de reserva do Events Manager.

## Navegador

Verificados: passe válido; cache privado/no-store; Referrer-Policy; QR local e leitura do QR exibido; ausência de confirmação de presença para visitante; resposta 404 a token errado ou ausente; verificação pública sem nome; documento nominal com acentos; agenda em 1280 e 390 pixels sem transbordamento horizontal; página de inscrições sem cache; rejeição de mutação com nonce inválido; dashboard administrativo; exportação CSV; metabox no editor real de evento; desfazimento por formulário; revogação refletida na consulta pública; ausência de erros JavaScript nas páginas percorridas.

## Instalação da dependência

Events Manager foi desativado e retirado do diretório de plugins do site descartável. A preparação pelo aviso administrativo instalou e ativou a base incluída. Uma segunda preparação preservou um arquivo de controle da instalação preexistente. A preparação descompactada foi executada nesta PR com cópia para área temporária, trava de instalação e publicação no diretório final, sem ZIP. Não foi substituída a base por um fork.

## Não validado nesta entrega

- Tema Tainacan Interface, Tainá, Blocksy ou temas personalizados. Alguns não renderizam coleções pelo filtro the_content; o shortcode é o ponto de integração alternativo documentado.
- Instalação conjunta com Koha, proxy, broker ou painel Textual do servidor de produção.
- SMTP real e entrega de mensagens. Os testes PHP interceptam wp_mail.
- Carga alta, concorrência de inscrições na base, milhares de eventos ou grandes acervos.
- Pagamentos, Pro, lista de espera e outros complementos, que não são requisitos da extensão.
- Multisite com ativação em rede ou tabelas globais, explicitamente não suportados.
- Todas as versões de WordPress/PHP e versões futuras dos plugins.
- Restauração completa de backup do site pelo instalador Koha.Nexus.
- Auditoria independente de segurança, acessibilidade completa ou homologação institucional de comprovantes.

## Uso recomendado

Piloto em cópia de teste do site, com backup e validação do tema, das permissões e do envio de confirmações. Esta entrega não altera automaticamente a instalação do Tainacan já administrada pelo Koha.Nexus. O manual inclui os arquivos e dados que precisam entrar no backup do WordPress.

## Verificações do repositório nesta PR

45 testes existentes passaram: panel/tests/test_platforms.py, panel/tests/test_docs_preview.py e panel/tests/test_site_languages.py. A suíte completa do projeto não foi executada. As alterações são restritas à nova pasta nexus-events-plugin; instalador, painel, site e scripts de produção não foram modificados.

Os arquivos da base são preservados byte a byte. Os atributos Git marcam esse diretório como código de terceiros e preservam finais de linha. Um README upstream usa um título Markdown com sete sinais de igualdade; esse arquivo usa marcadores de merge mais longos para evitar falso positivo de conflito, sem alterar seu conteúdo.
