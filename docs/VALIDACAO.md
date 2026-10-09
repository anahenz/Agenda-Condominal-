# Validação — AgendaCondominial 1.0

09/10/2026 — 13 testes aprovados, saída 0. Um aviso de depreciação do adaptador HTTPX/Starlette, sem falhas.

Testados: cadastro/edição/exclusão, vínculos dos condomínios, histórico e conclusão, filtros, limites de antecedência, etapas de 1 hora / 15 minutos / início, agrupamento de avisos, persistência da deduplicação ao reabrir, cancelamento sem alertas, validação de horários/links, backup/restauração, rejeição de backup incompatível, formulários embutidos, calendário, autenticação, dois usuários, permissões, revogação de sessões, conflito de gravações concorrentes, idempotência, importação inicial e persistência após reiniciar o servidor.

Interface renderizada em PySide6 offscreen e inspecionada. Capturas em visao_geral.png e novo_compromisso.png usam dados de exemplo temporários; o banco instalado começa vazio.

Scripts BAT/PowerShell em ASCII e CRLF. Instalador automático preservado com identidade própria, sem alterar a instalação do ContasPagar.

Ainda não executados neste ambiente: instalador Windows, notificações nativas reais, compilação EXE e publicação no Render. Testes de API usam TestClient ASGI local. É necessário validar o endereço publicado e dois computadores reais antes do uso diário.

Executar na pasta do projeto após instalar requirements-dev.txt: python -m pytest -q.
