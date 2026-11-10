# Espera pelo reinício real do Docker na CI

A execução 42715346852 falhou no ciclo integrado ao exceder os 120 segundos
reservados ao comando síncrono `systemctl restart docker`. Isso aconteceu antes
das verificações finais de idiomas. A anotação disponível não identifica por
que o serviço demorou; não prova defeito nem sucesso da aplicação.

O teste agora solicita o reinício sem bloquear o cliente systemctl e acompanha
por até seis minutos uma nova `InvocationID` do serviço, estado ativo/running
e resposta real do daemon. Continuar vendo a instância anterior ativa não passa.
Depois continuam as verificações existentes de PostgreSQL, Solr, API, UI e dados
persistidos. Em falha, informa os campos seguros do estado systemd observado.

Não pula o reinício nem declara reboot de máquina. Não altera o instalador ou os
serviços do servidor de Paulo. Onze testes dos auxiliares de aceitação passaram,
incluindo a recusa de invocação antiga, serviço falho e ausência de identidade.
O ciclo real deve ser conferido na nova execução da CI.
