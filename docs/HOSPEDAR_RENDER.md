# Publicar a AgendaCondominial no Render

O pacote inclui o servidor; o compartilhamento só começa depois da publicação. O aplicativo desktop continua instalado nos computadores. Use **outro serviço e outro disco**, separados do ContasPagar.

## Publicação com o arquivo pronto

1. Crie um repositório privado no GitHub, por exemplo `agenda-condominial`.
2. Em **Add file → Upload files**, envie o conteúdo da pasta `AgendaCondominial`, incluindo `app`, `server`, `render.yaml` e os demais arquivos. O `render.yaml` deve aparecer na raiz do repositório. Não envie `.venv`, backups, senhas ou bancos de dados.
3. No Render, escolha **New → Blueprint** e conecte esse repositório.
4. Revise a configuração proposta. Ela usa serviço **Starter** com disco persistente de 1 GB, com cobrança. Confira o valor no painel antes de confirmar; nenhum plano foi contratado nesta entrega.
5. Informe os segredos solicitados, diretamente no Render:
   - `AGENDA_ADMIN_EMAIL`: e-mail do administrador da agenda;
   - `AGENDA_ADMIN_PASSWORD`: senha exclusiva de pelo menos 12 caracteres.
6. Confirme o deploy quando concordar com o custo e aguarde **Live**.
7. Copie a URL HTTPS do serviço. A rota `/health` deve responder `status: ok`. A página raiz pode responder `Not Found`: a interface fica no aplicativo Windows.
8. Instale a Agenda nos PCs via **INSTALAR.bat**. Selecione **Equipe online**, use a mesma URL e entre com seu login. Cadastre as outras pessoas em **Equipe e backup**.

## Se estiver usando New Web Service

| Campo | Valor |
|---|---|
| Language | Python 3 |
| Root Directory | vazio, se app/server estão na raiz |
| Build Command | `pip install -r server/requirements.txt` |
| Start Command | `python -m uvicorn server.api:app --host 0.0.0.0 --port $PORT --workers 1` |
| Health Check Path | `/health` |
| Instance Type | Starter ou plano compatível com disco persistente |
| Disk mount path | `/var/data` |
| Disk size | 1 GB inicial |
| `PYTHON_VERSION` | `3.13.12` |
| `TZ` | `America/Sao_Paulo` |
| `AGENDA_SERVER_DIR` | `/var/data/agenda` |

Adicione também as variáveis de administrador acima. Configure o disco antes de cadastrar dados. Não use filesystem temporário para armazenar a agenda. Consulte as regras atuais do provedor: https://render.com/docs/disks e https://render.com/docs/blueprint-spec .

## Operação

- Uma empresa por servidor. Todos os usuários autorizados veem a mesma agenda.
- Uma instância e um worker. Não escale horizontalmente o serviço SQLite; o processo aplica bloqueio exclusivo no Linux.
- Dados: `/var/data/agenda/agenda.sqlite3`. Usuários/sessões: arquivo separado `acessos.sqlite3`.
- As senhas são armazenadas com hash scrypt e salt. Tokens de sessão são aleatórios, têm validade e seu hash é armazenado no servidor. Não há cadastro público ou envio automático de e-mails.
- O e-mail e a senha de ambiente só criam o primeiro administrador. Alterar essas variáveis posteriormente não redefine usuários existentes. Remova o segredo inicial depois de conferir o primeiro login, se desejar; uma base já inicializada não precisa dele para reiniciar.
- Desativar um usuário ou redefinir sua senha pelo administrador revoga as sessões dele.
- Cada operação tem revisão e recibo transacional, para impedir edições desatualizadas e duplicação por repetição da mesma solicitação.
- A agenda compartilhada depende da internet. O modo local é independente; não envia automaticamente alterações para a equipe.
- Notificações são exibidas no Windows de cada pessoa enquanto a Agenda estiver aberta, autenticada e conectada. O servidor não envia notificações push para computadores desligados.

## Backups e recuperação

Backup diário no disco do servidor, na pasta `backups`; baixe cópias externas regularmente em **Equipe e backup**. Monitore o espaço disponível. As cópias locais do servidor não protegem contra perda de todo o disco. O backup financeiro do ContasPagar é incompatível com esta agenda.

O arquivo `acessos.sqlite3` também precisa fazer parte da política de backup do provedor, por snapshot consistente do volume ou cópia pela API de backup do SQLite. O backup de agenda baixado pela interface não inclui senhas ou sessões.

Importação inicial: apenas quando o servidor não contém eventos nem condomínios; limite 25 MB. A base original do PC é preservada. Não há mesclagem de agendas.

A restauração de uma agenda online já em uso é uma operação de manutenção: pare o processo da API e mantenha o volume montado. No ambiente Linux do servidor, execute:

```bash
python -m server.maintenance restore /caminho/backup.sqlite3
```

Exige confirmação, preserva cópia anterior e altera a revisão. Reinicie o serviço e peça aos usuários que entrem novamente. Se o provedor não permitir shell com o serviço parado, use um procedimento de manutenção assistido pelo responsável pela hospedagem, sem sobrescrever o banco em uso.

Para recuperar acesso de um usuário existente, com a API parada:

```bash
python -m server.maintenance reset-password pessoa@empresa.com.br
```

A senha será solicitada sem exibição. Não coloque a senha no código, em argumentos ou no chat.

## Validação antes do uso da equipe

Depois de publicar, confirme: login em dois PCs; criação/edição aparecendo no outro PC após Atualizar; bloqueio de edição simultânea; lembretes Windows; cancelamento sem aviso; backup e restauração em ambiente de teste. O pacote foi testado localmente; hospedagem e instalação real no Windows ainda precisam dessa validação.
