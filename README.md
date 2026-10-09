# AgendaCondominial — assembleias, reuniões e lembretes

Aplicativo desktop Python + PySide6, em vermelho e branco. Banco SQLite organizado com SQLAlchemy. Oferece agenda local e agenda compartilhada através de servidor HTTPS autenticado. **Não contém contas a pagar, valores financeiros ou registro de pagamentos.**

## Instalar com dois cliques

1. Extraia todo o ZIP.
2. Abra a pasta `AgendaCondominial` e dê dois cliques em **INSTALAR.bat**.
3. Aguarde a instalação das dependências e a criação do atalho **AgendaCondominial** na área de trabalho. Requer internet para a instalação.
4. Abra pelo atalho. Não é preciso abrir VS Code nem digitar comandos.
5. Para começar imediatamente sem servidor, escolha **Somente neste computador**. Para trabalhar em equipe, publique primeiro o servidor conforme **docs/HOSPEDAR_RENDER.md**, e entre em **Equipe online** com a URL, e-mail e senha.

O instalador detecta Python 3.11–3.13 de 64 bits. Caso necessário, tenta instalar Python 3.13 pelo winget. Se o Windows não disponibilizar winget, orienta a instalar Python e executar novamente. A pasta de instalação é `%LOCALAPPDATA%\Programs\AgendaCondominial`. O banco local fica em `%LOCALAPPDATA%\AgendaCondominial\agenda.sqlite3`.

É um aplicativo separado: não substitui o ContasPagar nem abre seu banco financeiro. Cada instalação usa uma pasta própria e preserva a instalação anterior. Encerre a Agenda pelo botão **Sair** antes de atualizar, para não reabrir uma instância antiga.

## Usar a agenda

- **Visão geral:** compromissos de hoje, próximos 7 dias, agendados, aguardando conclusão, realizados no mês e condomínios.
- **Compromissos:** cadastre, edite, visualize, duplique, cancele, reabra, marque como realizada ou exclua uma reunião. Os formulários abrem dentro da janela principal.
- **Condomínios:** cadastre nome, CNPJ, endereço, cidade, síndico, telefone, e-mail e observações. Compromissos internos da administradora podem ficar sem condomínio.
- **Calendário:** datas destacadas possuem eventos. Clique em um dia e navegue pelos meses. Eventos de vários dias aparecem em cada data abrangida.
- **Histórico:** realizados, cancelados e eventos cujo horário já terminou e precisam de conclusão. O resultado pode ser registrado ao marcar como realizada.
- **Central de alertas:** eventos na antecedência configurada, incluindo os que estão em andamento. O sino mostra a quantidade.
- **Configurações:** notificações, continuar na bandeja ao fechar e iniciar com Windows.
- **Backup / Equipe e backup:** cópias de segurança e, no modo online, gestão de usuários pelo administrador.

Campos do evento: título, tipo, condomínio, início, término previsto, local, link HTTPS, responsável, participantes, pauta, observações, resultado, antecedência do resumo diário e lembretes de horário. Os tipos incluem assembleia ordinária, extraordinária, conselho, reunião com síndico, reunião interna, vistoria, visita técnica e outros.

Horários sempre são tratados como **horário de Brasília**, inclusive se o servidor estiver em outro fuso. Não há envio de e-mail ou WhatsApp, convocação formal, anexos, videoconferência embutida ou recorrência automática. Cadastre/duplique eventos quando precisar de outra data.

## Como os avisos funcionam

- Padrão: resumo diário a partir de **7 dias antes**. Antecedência configurável por evento entre 0 e 30 dias.
- Com lembretes de horário ativos: aviso em até **1 hora antes**, em até **15 minutos antes** e no início (tolerância de até 15 minutos após o início).
- A verificação acontece a cada 30 segundos. Lembretes que ocorrem juntos são agrupados em uma única notificação. Cada etapa é registrada localmente para evitar repetições.
- Eventos cancelados, realizados ou cujo término já passou não geram novos alertas.
- Se o programa abrir depois de uma etapa, recebe a etapa atual; não dispara uma sequência de lembretes atrasados. Se o horário do evento mudar, o novo horário pode gerar novos lembretes.
- Ao clicar na notificação, a Agenda abre a central de alertas. Os avisos usam `QSystemTrayIcon`, integrados ao Windows. O modo Não perturbe ou configurações do Windows podem silenciá-los.
- O aplicativo precisa estar **aberto ou na bandeja**. No modo online também precisa estar autenticado e conectado; sem internet os dados exibidos podem estar desatualizados e novos avisos são suspensos depois que a desconexão é detectada.
- O login online é solicitado a cada abertura e a sessão dura até 12 horas. Ao iniciar junto com Windows, entre para ativar as notificações online. Não há serviço Windows instalado para notificar com o aplicativo encerrado.

## Banco compartilhado

O arquivo SQLite fica **somente no servidor**, em disco persistente, e é acessado por uma API Python. Os computadores usam HTTPS; não abrem um SQLite em pasta de rede.

Todos os usuários de um servidor acessam a mesma agenda da empresa. Cada usuário tem login individual. Operadores gerenciam compromissos; administradores também gerenciam acessos e backups. A atualização automática ocorre a cada 30 segundos fora dos formulários. Edições desatualizadas são recusadas para evitar sobrescrever outra pessoa.

A versão entregue inclui o servidor e a configuração Render, **mas ainda não está hospedada**. Não existe URL ou senha de produção embutida. Use uma implantação independente da do ContasPagar.

## Backup e transferência

Modo local: backup manual, diário ou semanal; restauração com cópia de segurança prévia. Modo online: backup diário no disco do servidor e download pelo administrador. Guarde cópias externas e monitore o espaço no disco. O backup exportado inclui eventos, condomínios e auditoria, não credenciais.

Para levar a agenda local ao servidor vazio, gere um backup local e use **Equipe e backup → Importar backup local**. O sistema recusa mesclar uma base online que já contém cadastros. Backups do ContasPagar não são compatíveis e não devem ser usados aqui. Modo local e online são independentes, sem sincronização offline posterior.

## Desenvolvimento e EXE

Para executar manualmente, na pasta do projeto:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Para gerar o EXE **no Windows**, execute `instalar_dependencias.bat`, depois `gerar_exe.bat`. O resultado será `dist\AgendaCondominial.exe`. Use `instalar_exe.bat` para criar atalhos para o EXE. O pacote contém o código e a configuração PyInstaller; **não contém um executável Windows já compilado**. Depois de corretamente empacotado, o EXE inclui Python.

Testes: instale `requirements-dev.txt` e execute `python -m pytest -q` na pasta do projeto. A separação de arquivos inclui `app/models`, `database`, `services`, `views`, `widgets`, `utils`, `assets`, e `server`.
