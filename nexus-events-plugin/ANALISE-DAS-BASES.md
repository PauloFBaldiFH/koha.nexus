# Escolha de arquitetura

Foram lidos os três arquivos fornecidos: Events Manager 7.4.13, Event Tickets 5.31.0 e The Events Calendar 6.18.3.

A escolha foi uma extensão sobre Events Manager, com os arquivos originais extraídos incluídos como dependência instalável por confirmação. Não fizemos um fork nem misturamos três modelos de eventos/reservas. Não são necessários os outros dois plugins para executar Nexus Eventos.

## Critérios

- Events Manager já reúne recorrência, locais, capacidade, reservas e administração de participantes. Isso evita implementar novamente persistência e regras de inscrição.
- The Events Calendar tem uma separação clara entre agenda e componentes adicionais. Essa abordagem orientou a separação entre apresentação pública e motor de reservas.
- Event Tickets destaca o fluxo de confirmação, passe e relatórios. A extensão implementa seus próprios passes e presença, sem copiar a implementação do produto nem exigir suas extensões.
- O Tainacan permanece responsável pelo acervo. Eventos apenas referenciam coleções públicas; pessoas inscritas não viram itens públicos do repositório.

## Interfaces efetivamente utilizadas

Na versão Events Manager fornecida:
- classes/em-events.php: EM_Events::get, num_rows_found, argumentos de busca.
- classes/em-bookings.php: EM_Bookings::get; o resultado é Iterator, não Countable.
- classes/em-booking.php: get_event, get_person, get_status, booking_uuid, booking_status e filtro em_booking_email_messages.
- classes/em-event.php: start, end, get_location, get_permalink, get_ical_url e can_manage.
- hooks em_booking_deleted e em_bookings_deleted para anonimização/revogação dos dados próprios.

No Tainacan 1.4.1:
- Tipo de coleção tainacan-collection, confirmado em src/classes/entities/class-tainacan-collection.php.
- URL de coleção pelo mecanismo get_permalink, também utilizado por Collection::get_url.
- Coleções reais criadas pelos repositórios do Tainacan nos testes; não simulamos o tipo de conteúdo.

Na extensão:
- Dados exclusivos em três tabelas com prefixo do site WordPress.
- Vínculos armazenados nos metadados do evento.
- Mutações com nonce, autorização por evento e travas por reserva.
- Documentos públicos não revelam nome/e-mail; documento nominal exige titular, equipe ou credencial de passe.
- Biblioteca QR local MIT, com licença incluída.

## Alternativas recusadas

Fundir as três bases: criaria modelos de dados, rotas e administração concorrentes.

Fork integral: perderia o caminho normal das atualizações da base e aumentaria o esforço de incorporar correções.

Motor próprio de reservas: exigiria reimplementar capacidade, cancelamentos, confirmação, recorrência e migrações sem necessidade nesta entrega.

Ativar funções comerciais por alterações na licença: não é usado. Os recursos novos são código próprio, e a dependência gratuita é preservada.

## Escopo consciente

Não se promete compatibilidade com qualquer tema. Os shortcodes funcionam em páginas WordPress; blocos automáticos dependem de o tema usar the_content. Não foi alterado o instalador do Koha.Nexus nem configurado um servidor de produção.

A versão inicial não inclui espera, pagamentos, scanner de câmera, certificados assinados digitalmente nem identificação nominal de várias pessoas na mesma reserva. É preferível declarar esses limites a emitir documentos com identidade ou presença ambíguas.
