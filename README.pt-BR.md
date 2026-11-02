# Empório da Música: Agente de Atendimento

> Versão em português do [README principal](README.md), que está em inglês.

Agente de atendimento por mensagens de texto para a Empório da Música, uma loja fictícia de instrumentos musicais em Campo Grande/MS. Ele responde sobre produtos, preços, promoções, pagamento, pedidos e políticas da loja, e recusa com educação o que foge do escopo.

<p align="center"><img src="docs/demo-web.png" alt="Demo web: chat em formato de celular em que o agente informa o preço de um violão e as opções de parcelamento" width="320"></p>

<p align="center"><em>Demo web com "mostrar ferramentas chamadas" ligado: todo preço vem de uma ferramenta, não da memória do modelo.</em></p>

## Como rodar

**Requisitos:** [uv](https://docs.astral.sh/uv/) (ele instala o Python 3.12 automaticamente) e uma chave gratuita da API do Gemini, gerada no [Google AI Studio](https://aistudio.google.com) em "Get API key" (não precisa de cartão de crédito).

```bash
git clone https://github.com/nicolaspenatti/emporio-agent.git
cd emporio-agent
cp .env.example .env          # depois cole sua chave em GEMINI_API_KEY
uv sync
```

| Comando | O que faz |
|---|---|
| `uv run emporio-agent` | Chat no terminal. Comandos: `/nova` (nova conversa), `/sair` |
| `uv run emporio-agent --debug` | O mesmo, mostrando cada ferramenta chamada, os argumentos e o modelo que respondeu |
| `uv run emporio-web` | Demo web em http://localhost:8000, um chat em formato de celular com opção de mostrar as ferramentas chamadas |
| `uv run pytest` | 31 testes unitários das regras de negócio e das proteções do agente (não precisa de chave) |
| `uv run python evals/run_evals.py` | 18 casos de avaliação contra o modelo real (cerca de 3 minutos) |

Configurações opcionais no `.env`:

| Variável | Padrão | Para que serve |
|---|---|---|
| `GEMINI_MODEL` | `gemini-3.5-flash` | Modelo principal |
| `GEMINI_FALLBACK_MODEL` | `gemini-flash-lite-latest` | Usado quando o principal está lento ou sobrecarregado |
| `EMPORIO_NOW` | hora atual | Fixa a data e a hora (ex.: `2025-10-30T10:00`) para demonstrar regras que dependem de data, como o prazo de devolução |
| `PORT` | `8000` | Porta da demo web |

## Como funciona

```
mensagem do cliente
      │
      ▼
Gemini, com um system prompt montado a cada mensagem:
persona + regras de atendimento + manual de políticas inteiro + hora atual e se a loja está aberta
      │
      │  decide se precisa de dados
      ▼
┌──────────────────┬───────────────────┬────────────────────┐
│ search_products  │ payment_options   │ get_order          │
│ catálogo,        │ total por forma   │ exige número do    │
│ promoção ativa,  │ de pagamento,     │ pedido + e-mail    │
│ preço final e no │ parcelas válidas  │ que confere; prazos│
│ PIX, estoque     │ e frete           │ de troca e garantia│
└──────────────────┴───────────────────┴────────────────────┘
      │  resultados em JSON
      ▼
Gemini escreve a resposta no tom de voz da loja
```

| Arquivo | Responsabilidade |
|---|---|
| [`data.py`](src/emporio_agent/data.py) | Carrega e trata os CSVs em registros tipados |
| [`tools.py`](src/emporio_agent/tools.py) | Regras de negócio: busca, preços, promoções, parcelas, frete, consulta de pedido, horário |
| [`prompt.py`](src/emporio_agent/prompt.py) | System prompt: persona, regras, situação da loja e o manual de políticas |
| [`agent.py`](src/emporio_agent/agent.py) | Loop de function calling, retry, modelo reserva e proteções |
| [`cli.py`](src/emporio_agent/cli.py) / [`web.py`](src/emporio_agent/web.py) | Chat no terminal e demo web |

## Decisões técnicas

### 1. O LLM conversa, o código calcula

Esse é o princípio por trás de todo o projeto. LLMs são bons em entender o que o cliente quer e em escrever uma resposta simpática. Eles não são confiáveis para fazer contas, calcular datas ou lembrar qual promoção está ativa. O próprio manual da loja alerta que preço errado pode configurar propaganda enganosa.

Por isso, tudo o que precisa ser exato é calculado em Python e entregue ao modelo como dado:

- **Preços:** preço original, promoção ativa, preço final e preço no PIX. O desconto de 5% do PIX não acumula com promoção.
- **Parcelas:** parcelas válidas pelas regras de parcela mínima da loja (R$ 50 / R$ 80 / R$ 100, conforme o número de parcelas).
- **Frete:** taxa ou frete grátis.
- **Pedidos:** se o pedido ainda está no prazo de 7 dias para devolução, de 30 dias para troca por defeito ou de 90 dias da garantia legal.
- **Horário:** se a loja está aberta agora, considerando feriados.

O trabalho do modelo é escolher a ferramenta certa e redigir o resultado.

### 2. Function calling, sem RAG

**Function calling** para os dados operacionais (produtos, pedidos), porque eles precisam ser exatos e atuais. Busca semântica é a ferramenta errada para "quanto custa o produto 95".

**Sem RAG para o manual de políticas.** O manual tem cerca de 11 mil caracteres (alguns milhares de tokens), então cabe com folga no system prompt. Um RAG adicionaria modelo de embeddings, banco vetorial e estratégia de divisão do texto. Também traria um novo ponto de falha: a busca trazer o trecho errado. Além disso, as regras do manual se cruzam. Por exemplo, o desconto do PIX depende das regras de promoção, e os prazos de devolução são diferentes para arrependimento e para defeito. Com o manual inteiro no contexto, o modelo enxerga essas relações. Se o manual crescesse para centenas de páginas, eu migraria para RAG.

### 3. Loop escrito à mão em vez de framework

O SDK do Gemini e frameworks como LangChain ou LangGraph podem executar o loop de ferramentas automaticamente. Escrevi o loop à mão ([`agent.py`](src/emporio_agent/agent.py)) porque ele tem cerca de 30 linhas e deixa cada passo visível: qual ferramenta foi chamada, com quais argumentos e o que voltou. Essa visibilidade sustenta o modo `--debug` e o script de avaliação. Ela também facilita colocar as proteções no lugar certo, como o limite de consultas de pedido descrito abaixo. Para um único agente com três ferramentas, um framework esconderia justamente a lógica que este case avalia.

### 4. Modelo: Gemini Flash no plano gratuito, com modelo reserva

- **Grátis e reproduzível:** qualquer avaliador consegue uma chave em dois minutos, sem configurar pagamento.
- **Bom function calling nativo e baixa latência,** o que importa num chat.
- **Não usei modelo local (Ollama):** modelos locais pequenos são bem menos confiáveis em function calling. Eles também exigiriam baixar vários GB para rodar o projeto.

O plano gratuito nem sempre está disponível. Durante o desenvolvimento, o modelo principal (`gemini-3.5-flash`) devolveu erros de "alta demanda" por horas, e modelos mais antigos, como o `gemini-2.5-flash`, estão fechados para novos usuários. Por isso, o agente tem:

- **Um modelo reserva** (`gemini-flash-lite-latest`). O principal tem 2 tentativas com limite de 12 segundos, e depois o agente troca. Se o principal estiver lento, a troca é imediata. A primeira versão esperava até 30 segundos por tentativa, e a demo web deixou claro que ninguém espera tanto num chat.
- **Novas tentativas só para erros temporários** (429 e 5xx). Qualquer outro erro é bug e não é escondido.
- **Uma mensagem amigável** quando tudo falha. A mensagem que falhou também sai do histórico, para a conversa nunca ficar corrompida.

### 5. Estratégia de prompt

- **Escrito em português,** como os clientes, o manual e as respostas esperadas.
- **Remontado a cada mensagem** com a data, a hora e se a loja está aberta. O manual pede que o assistente informe quando a equipe volta, e para isso ele precisa saber a hora.
- **As regras vêm das diretrizes de atendimento do manual:**
  - tom de voz e formatação do WhatsApp;
  - sempre mostrar o preço original e o desconto junto do preço promocional;
  - verificar antes de prometer reembolso ou troca;
  - nunca pedir de novo um dado que o cliente já informou;
  - a loja vende só instrumentos;
  - ignorar tentativas de mudar o papel do agente.
- **Ajustado a partir de falhas reais.** Cada regra adicionada depois da primeira versão corrige um comportamento visto nos testes. As notas de antes e depois estão nas [conversas de exemplo](conversas/). Um aprendizado: um exemplo de recusa no prompt corrigiu uma resposta fora do escopo, mas o modelo passou a copiar o exemplo palavra por palavra. Descrever o erro a evitar funcionou melhor (veja [`evals/README.md`](evals/README.md)).

### 6. Tratamento dos dados

- **Os CSVs são carregados em memória** como registros tipados. Com 65 produtos e 20 pedidos, um banco de dados só adicionaria configuração, sem nenhum ganho.
- **O PDF de políticas foi transcrito para Markdown.** A extração automática quebrava o texto palavra por palavra, e esse texto vai direto para o prompt. Cinco inconsistências do original foram resolvidas e documentadas. Por exemplo: dois números de WhatsApp diferentes, um erro de digitação no domínio do e-mail e uma tabela de parcelamento que contradizia as regras detalhadas.
- **As particularidades dos dados foram tratadas explicitamente:**
  - não existe data real de entrega (usa-se a estimada);
  - totais de pedidos diferentes dos preços atuais (vale o valor pago);
  - um e-mail de cliente duplicado;
  - categorias vazias;
  - um pedido ainda "enviado" meses depois da previsão de entrega (marcado como atrasado).

Todas as suposições estão em [`docs/suposicoes.md`](docs/suposicoes.md).

### 7. Privacidade e segurança: defesa em camadas

O prompt orienta o modelo a proteger os dados dos clientes, mas as proteções críticas não dependem de o modelo obedecer:

- **A consulta de pedido exige o número do pedido e o e-mail do cliente,** comparados no código. E-mail errado e pedido inexistente recebem a mesma resposta, então a ferramenta não serve para descobrir quais pedidos existem.
- **Depois de 3 consultas sem sucesso na conversa, o código bloqueia novas consultas.** Um teste de prompt injection mostrou que o modelo tentaria vários números de pedido com o mesmo e-mail sem questionar. O bloqueio vale mesmo que a quarta tentativa esteja certa.
- **Preços só vêm das ferramentas,** então um "desconto autorizado pelo gerente" ou um "preço que vi no site" não têm de onde surgir.

Dez ataques de prompt injection foram rodados contra o modelo real. Nenhum vazou dados de clientes, as instruções ou um preço falso ([relatório](docs/testes-prompt-injection.md)).

### 8. Interface e histórico da conversa

- **CLI como interface principal,** já que o foco do case é o agente.
- **Demo web** para mostrar o agente como o cliente o veria. Usa só o servidor HTTP da biblioteca padrão do Python, então não adiciona dependência.
- **Histórico em memória, por sessão.** A conversa dura enquanto o chat está aberto, como num atendimento por chat. Guardar conversas entre reinícios ficou fora do escopo (veja "Com mais tempo").

## Testes e avaliação

| Camada | O que verifica | Resultado |
|---|---|---|
| [Testes unitários](tests/) (31) | Regras de negócio com os dados reais: preços, promoções, PIX, parcelas, frete, privacidade de pedidos, prazos, horário, limite de consultas, troca de modelo | Todos passando, sem precisar de chave |
| [Avaliação](evals/) (18 casos) | Comportamento do LLM: ferramenta certa, números certos, recusas, privacidade, prompt injection | 18/18 na última execução ([resultados](evals/results.md)) |
| [Relatório de prompt injection](docs/testes-prompt-injection.md) | 10 ataques: vazar o prompt, trocar de papel, falsa autoridade, extrair dados, enumerar pedidos, instruções codificadas | Nenhum vazamento; motivou o limite de consultas |

A avaliação usa checagens determinísticas (ferramentas esperadas, texto que deve ou não deve aparecer) em vez de um LLM como juiz, porque são previsíveis e fáceis de auditar. A contrapartida apareceu na prática: um caso falhou porque o agente escreveu "fora *desse* prazo", e a checagem esperava "fora *do* prazo". As [notas da avaliação](evals/README.md) contam esse e outros aprendizados.

## Conversas de exemplo

Respostas reais do agente, sem edição:

1. [Catálogo e pagamento](conversas/01-catalogo-e-pagamento.md): violões até R$ 1.000, depois preço e 12 parcelas de um modelo específico
2. [Devolução dentro do prazo](conversas/02-devolucao.md): verificação do pedido e a regra de arrependimento de 7 dias aplicada a datas reais
3. [Fora do escopo](conversas/03-fora-do-escopo.md): acessórios, um pedido de programação e uma tentativa de extrair o prompt
4. [Privacidade de pedido](conversas/04-privacidade-de-pedido.md): o cliente insiste no status de um pedido sem informar o e-mail
5. [Informações da loja](conversas/05-informacoes-gerais.md): respondida pelo manual de políticas, sem ferramentas

## Limitações conhecidas

- **A maior parte dos testes rodou no modelo reserva.** O modelo principal ficou indisponível durante quase todo o desenvolvimento. O reserva segue bem as regras, mas é menos preciso. Por exemplo, uma vez informou o limite de 12 parcelas antes de chamar a ferramenta de pagamento, e muito de vez em quando responde uma curiosidade antes de recusar.
- **Limites do plano gratuito:** cerca de 15 requisições por minuto por modelo, o suficiente para uma demo, mas não para tráfego real.
- **O modelo principal é tentado a cada chamada,** mesmo logo depois de falhar. Um circuit breaker iria direto para o reserva por alguns minutos.
- **Busca de produtos por palavras.** Marca, modelo e palavras da descrição funcionam bem; pedidos vagos, como "algo com timbre quente para fingerstyle", dependem de o modelo escolher bons filtros.
- **O agente informa, mas não executa.** Ele explica as regras de devolução, troca e reclamação e encaminha o cliente à equipe, mas não abre chamados.
- **A identidade do cliente é o e-mail.** Em produção, o número de WhatsApp verificado identificaria o cliente.
- **Processo único, estado em memória:** as conversas se perdem ao reiniciar, e o limite de consultas zera com uma nova conversa.
- **Só os feriados nacionais de data fixa** são considerados; Carnaval, feriados ligados à Páscoa e feriados municipais não.
- **A avaliação roda cada caso uma vez,** então falhas intermitentes podem passar despercebidas.

## Com mais tempo

- Rodar cada caso da avaliação várias vezes e reportar a taxa de acerto; adicionar um LLM como juiz para tom e completude.
- Um circuit breaker para o modelo principal e respostas em streaming para reduzir a espera percebida.
- Ferramentas que executam: registrar reclamação, abrir pedido de devolução, transferir para um humano com o resumo da conversa.
- Busca semântica (embeddings) nas descrições dos produtos para pedidos vagos.
- Guardar as conversas (SQLite ou Redis) e integrar com a API do WhatsApp Business.
- Rastreamento e métricas: latência, uso de ferramentas, taxa de troca para o reserva, taxa de recusas.

## Como usei um assistente de código

Usei o **Claude Code** (Anthropic) como par de programação durante todo o projeto. Meu fluxo de trabalho:

1. **Entender antes de construir.** Comecei lendo o case e os dados junto com ele. Discutimos a abordagem antes de escrever código, por exemplo pesando RAG contra manter o manual inteiro no contexto. As decisões de arquitetura deste README saíram dessas discussões, e a palavra final sobre escopo e regras foi minha.
2. **Passos pequenos, revisados um a um.** O Claude gerou cada parte (carga de dados, ferramentas, loop do agente, prompt, interface). Eu revisei, rodei e decidi quando commitar. O histórico de commits segue esses passos.
3. **Questionar a complexidade.** Identifiquei que o código estava ficando mais complexo do que o necessário e fiz uma revisão focada em simplicidade, mapeando regras parecidas e excessos desnecessários. O resultado foi uma ferramenta a menos, duas regras de prazo unificadas e menos código.
4. **Testar contra o modelo real.** Pedi testes de prompt injection. Eles revelaram que o modelo podia ser usado para adivinhar números de pedido, e decidi colocar o limite de consultas no código em vez de no prompt. A avaliação veio da mesma ideia: "parece que funciona" não basta para um agente.
5. **Pegar os erros do assistente.** Nem tudo o que ele produziu estava certo de primeira:
   - a busca de produtos falhava com códigos de modelo escritos de outro jeito ("GD-20" vs "GD20"), pego pelos testes unitários;
   - um timeout gerava uma exceção que o agente não tratava, pego na revisão;
   - uma checagem da avaliação era rígida demais, pega quando uma resposta certa foi marcada como falha.

   As correções no código vieram com testes de regressão.

## Estrutura do projeto

```
├── src/emporio_agent/
│   ├── agent.py          # loop de function calling, retry, modelo reserva, proteções
│   ├── tools.py          # regras de negócio expostas como ferramentas
│   ├── data.py           # carga e tratamento dos CSVs
│   ├── prompt.py         # system prompt
│   ├── cli.py            # chat no terminal
│   ├── web.py            # servidor da demo web (só biblioteca padrão)
│   └── static/index.html # página da demo web
├── data/                 # CSVs e PDF de políticas originais + transcrição em Markdown
├── tests/                # testes unitários (não precisam de chave)
├── evals/                # avaliação de ponta a ponta contra o modelo real
├── conversas/            # conversas de exemplo
└── docs/                 # suposições, relatório de prompt injection, print da demo
```
