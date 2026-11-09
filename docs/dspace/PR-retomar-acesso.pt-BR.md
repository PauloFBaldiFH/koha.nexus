# Restaurar a rota web ao iniciar o DSpace — 1.5.191

Depois de remover o DSpace com a opção de preservar dados, iniciar novamente
subia os contêineres, mas não recriava o site Apache removido. A validação de
acesso introduzida na versão 1.5.190 passou a detectar esse erro real no ciclo
integrado da CI. Contêineres ativos não bastam para declarar a instalação pronta.

A inicialização agora reaplica a configuração do proxy antes de verificar o
acesso público. Instalação e inicialização usam a mesma rotina, que aceita
apenas os resultados conhecidos do driver. Proxy externo continua marcado como
configuração externa necessária. Falha de configuração mantém o estado degradado.

Não há novas imagens nem migração de banco. Iniciar conserva arquivos privados,
credenciais e volumes, e não repete a migração concluída. A remoção continua
preservando os dados quando essa opção é escolhida.

Validação: 183 testes DSpace aprovados em Debian descartável como root,
validação do catálogo/bundle e checksum; regressões de retomar com dados preservados, falha do proxy e retorno
desconhecido. O ciclo integrado
existente da CI remove com dados preservados e inicia novamente com o DSpace
real. Conferir seu resultado no PR antes de mesclar.
