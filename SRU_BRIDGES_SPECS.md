# Especificações Técnicas: Ecossistema de Serviços SRU (Zeus & Pergamum)

## 1. Visão Geral
Dois serviços assíncronos em Python (FastAPI/Uvicorn) operando como bridges SRU 1.1 para integração de catálogos bibliográficos ao Koha ILS via MARCXML:

1. **Zeus SRU Gateway (Porta 5001)**
   - Roteador e multiplexador para 55+ catálogos nacionais e internacionais (FBN, USP, UNICAMP, UFMG, Porbase, Harvard, British Library, etc.).
   - Rotas no padrão: `http://<IP>:5001/sru/<identificador>` (ex: `sru/bn`, `sru/usp`).

2. **Pergamum SRU Bridge (Porta 5006)**
   - Bridge dedicada para o catálogo central da Rede Pergamum (PUCPR / site CRP).
   - Traduz consultas CQL para chamadas Sajax e converte o retorno para MARCXML.

---

## 2. Peculiaridades e Regras do Backend Pergamum (PUCPR)
- **Persistência de Sessão:** Requer handshake inicial GET na home (`pesquisa.php`) para registrar o cookie `PHPSESSID`.
- **Falso Erro 500:** Buscas vazias ou termos sem correspondência retornam HTTP 500 com corpo válido Sajax (`+:`). O cliente HTTP **não deve** estourar exceção com `raise_for_status()`; se o corpo começar com `+:`, deve processar normalmente como 0 resultados.
- **Sanitização de ISBN:** Hífens e caracteres não numéricos devem ser removidos (apenas dígitos e `X`).
- **Timeout:** Ajustado para 30 segundos devido à consulta distribuída entre múltiplos campi e consórcios.
- **Binding de Rede:** Deve escutar em `0.0.0.0` para permitir acesso pela rede local e instâncias vizinhas.

---

## 3. Configuração de Rede e Infraestrutura (Oracle Cloud)
- **Portas:** 5001 (Zeus) e 5006 (Pergamum).
- **Binding:** `0.0.0.0` (definido via systemd override com `PERGAMUM_SRU_HOST=0.0.0.0`).
- **Firewall:** Portas liberadas no `ufw`, `iptables` (cadeia INPUT) e Ingress Rules na Security List da VCN na Oracle Cloud.
