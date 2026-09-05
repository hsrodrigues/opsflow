# Guia do usuário — OpsFlow

Este guia é para quem **usa** o OpsFlow no dia a dia — administrador da
empresa, supervisor, operador ou visualizador. Para documentação técnica
(arquitetura, banco de dados, segurança), veja a pasta `docs/` e o
[README](../README.md) principal.

## Sumário

- [Como começar a usar (ativação)](#como-começar-a-usar-ativação)
- [Entrando no sistema](#entrando-no-sistema)
- [Papéis de usuário](#papéis-de-usuário)
- [Dashboard](#dashboard)
- [Cadastros](#cadastros)
- [Operação](#operação)
- [Relatórios](#relatórios)
- [Usuários da equipe](#usuários-da-equipe)
- [Licença](#licença)
- [Configurações (meu perfil)](#configurações-meu-perfil)
- [Notificações](#notificações)
- [Perguntas frequentes](#perguntas-frequentes)

## Como começar a usar (ativação)

Se você recebeu uma **chave de ativação** de quem vende o OpsFlow:

1. Abra o OpsFlow (instalado no seu computador).
2. Na tela de login, clique em **"Recebeu uma chave de ativação? Ative
   aqui"**.
3. Digite a chave recebida, os dados da sua empresa (razão social, nome
   fantasia, CNPJ) e os dados do seu usuário administrador (nome, e-mail,
   senha).
4. Clique em **"Ativar e entrar"** — pronto, sua empresa já está criada e
   você já está logado como administrador, sem precisar fazer login de
   novo.

Cada chave de ativação só pode ser usada **uma vez**. Se a chave já tiver
sido usada por outra empresa, o sistema avisa e não deixa continuar.

## Entrando no sistema

Depois de ativado, o login é sempre e-mail + senha, na tela inicial. Marque
**"Lembrar acesso"** para não precisar digitar a senha toda vez que abrir o
programa nesse computador.

Não existe "esqueci minha senha" pelo próprio login — isso é proposital:
se você esqueceu sua senha, peça para o **administrador da sua empresa**
redefinir uma nova para você, na tela Usuários (veja
[Usuários da equipe](#usuários-da-equipe)).

## Papéis de usuário

Cada pessoa da equipe tem um papel, que define o que ela pode ver e fazer:

| Papel | Cadastros (veículos, motoristas, transportadoras, rotas, produtos) | Programação | Status da operação | Ocorrências | Relatórios | Equipe/Licença |
|---|---|---|---|---|---|---|
| **Administrador** | Cria e edita | Cria e edita | Atualiza | Cria e edita | Vê e exporta | Gerencia a equipe e vê a licença |
| **Supervisor** | Só consulta | Cria e edita | Atualiza | Cria e edita | Vê e exporta | Não acessa |
| **Operador** | Só consulta veículos | Só consulta | Atualiza | Cria e edita | Não acessa | Não acessa |
| **Visualizador** | Só consulta | Só consulta | Só consulta | Só consulta | Só vê (não exporta) | Não acessa |

Repare que **Supervisor não cadastra veículo/motorista/transportadora/rota/
produto novo** — só consulta esses cadastros; quem cria e edita cadastros é
sempre o Administrador. Supervisor e Operador cuidam do dia a dia da
operação (programação e ocorrências), não do cadastro base.

Quem define o papel de cada pessoa é o Administrador, na tela Usuários.

## Dashboard

Tela inicial depois do login. Mostra, para o período escolhido (padrão: os
últimos 7 dias):

- **Indicadores** (operações hoje, concluídas, em andamento, atrasadas,
  canceladas, veículos ativos, ocorrências, tempo médio de operação, taxa
  de conclusão);
- **Gráfico de operações por status** e **por transportadora**;
- **Gráfico de ocorrências por severidade**.

Use os campos de data no topo para mudar o período. O ícone de lua/sol no
canto superior direito alterna entre tema claro e escuro.

## Cadastros

Menu lateral, seção "Cadastros" — cada tela segue o mesmo padrão: uma
tabela com busca e filtros, botão **"+ Novo"** para criar, e ações
**Editar**/**Excluir** em cada linha. Criar e editar cadastros é uma ação
exclusiva do **Administrador** — os demais papéis só consultam (veja
[Papéis de usuário](#papéis-de-usuário)).

- **Veículos**: placa, tipo, transportadora responsável, status (Disponível,
  Em operação, Em manutenção, Inativo, **Bloqueado**). Um veículo é bloqueado
  **automaticamente** se for registrada uma ocorrência do tipo "Acidente"
  contra ele — ninguém precisa lembrar de fazer isso na mão.
- **Motoristas**: nome, CPF, CNH (número, categoria, validade — o sistema
  avisa automaticamente quando uma CNH está perto de vencer). Também é
  bloqueado automaticamente se sofrer uma ocorrência marcada como
  **severidade Crítica**.
- **Transportadoras**: as empresas parceiras que executam o transporte.
- **Rotas**: origem, destino e tempo estimado (aceita horas **e** minutos —
  o sistema converte tudo pra minutos por baixo dos panos).
- **Produtos**: o que é transportado, com a própria unidade de medida
  (unidade, kg, tonelada, litro, caixa, palete, m³) — assim a quantidade na
  Programação nunca fica ambígua.

## Operação

- **Programação** *(criar/editar é só Administrador e Supervisor —
  Operador e Visualizador só consultam)*: monte a programação do dia/turno
  — rota, transportadora, veículo, motorista, produto e quantidade,
  horário previsto. Um item programado pode ser **excluído** enquanto
  ainda não começou (status "Programado"); depois disso, o caminho é
  mudar o status para "Cancelado". Botão **"Duplicar programação"** clona
  todos os itens de uma data pra outra — útil pra rotas que se repetem
  toda semana.
- **Centro de Operações**: acompanhamento ao vivo do que está em execução
  agora — contadores por status e a lista de operações do dia, cada uma com
  seu número de operação e o histórico de mudanças de status (quando saiu
  de "Aguardando" pra "Em operação", etc.).
- **Ocorrências**: registre qualquer evento fora do esperado (atraso,
  quebra, acidente, divergência de carga, ...), com severidade (Baixa,
  Média, Alta, Crítica). Duas automações importantes:
  - Ocorrência do tipo **"Acidente"** vinculada a um veículo → bloqueia o
    veículo.
  - Ocorrência de severidade **Crítica** vinculada a um motorista →
    bloqueia o motorista.

  Nos dois casos, quem pode desbloquear é editando o cadastro (Veículos ou
  Motoristas) manualmente, depois de resolver a situação.

## Relatórios

Escolha o tipo (Operações, Ocorrências, Veículos ou Ranking de
transportadoras), o período e os filtros, veja a prévia na tela e exporte
em **Excel**, **CSV** ou **PDF** — o arquivo já sai com cabeçalho, período e
os indicadores relevantes prontos.

## Usuários da equipe

Só para Administradores. Convide alguém pelo e-mail, defina o papel, e a
pessoa já pode entrar. Para desativar alguém (quem sai da empresa, por
exemplo), edite o usuário e mude o status — a conta **nunca é excluída de
verdade** (isso preservaria o nome de quem fez cada coisa no histórico de
auditoria mesmo depois que a pessoa saiu). Você não consegue desativar a
sua própria conta, por segurança.

**Trocar a senha de alguém** (inclusive a sua própria) também é feito
aqui: edite o usuário e preencha "Nova senha" — deixe em branco pra manter
a senha atual.

## Licença

Mostra o plano contratado, o status (Ativa, Em teste, Suspensa, Expirada,
Cancelada), até quando é válida, e quanto você já usa dos limites de
usuários e veículos do seu plano. Só leitura — para mudar de plano ou
renovar, fale com quem vende o OpsFlow para você.

## Configurações (meu perfil)

Qualquer pessoa pode editar o próprio nome e telefone aqui — não precisa
ser Administrador para isso. Como já dito acima, não existe troca de senha
por aqui: isso é sempre com o Administrador da empresa.

## Notificações

O sino no topo da tela avisa sobre: atrasos detectados automaticamente,
CNH próxima do vencimento, veículo/motorista bloqueado automaticamente, e
avisos de licença. Clique no sino para ver a lista e marcar como lida.

## Perguntas frequentes

**Esqueci minha senha, e agora?**
Peça pro administrador da sua empresa redefinir uma nova, na tela Usuários.

**Por que um veículo/motorista ficou bloqueado sozinho?**
Alguém registrou uma ocorrência de acidente (veículo) ou uma ocorrência
crítica (motorista) vinculada a ele — veja a aba Ocorrências para entender
o que aconteceu, resolva a situação e desbloqueie manualmente editando o
cadastro.

**Minha licença está "Em teste", o que acontece quando vencer?**
Fale com quem vende o OpsFlow para você para migrar pro plano pago antes da
data de expiração mostrada na tela Licença.

**Posso usar em mais de um computador?**
Sim — o login é por usuário, não por computador. Cada pessoa da equipe usa
seu próprio e-mail e senha.
