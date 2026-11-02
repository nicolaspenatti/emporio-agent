# Suposições e tratamento de dados

O enunciado pede que ambiguidades sejam resolvidas com uma interpretação razoável e documentada. Este arquivo registra cada uma delas.

## Manual de políticas (`data/politicas_da_loja.md`)

O PDF original foi transcrito para Markdown. Ele vai inteiro no system prompt do agente, e o texto extraído automaticamente saía quebrado palavra por palavra. A transcrição é fiel ao original, com as exceções abaixo. O PDF original continua em `data/` para referência.

| # | Inconsistência no original | Decisão | Motivo |
|---|---|---|---|
| 1 | Telefone/WhatsApp aparece como **(67) 3341-4444** (capa e tabela "Dados da Empresa") e como **(67) 3321-4500** (seção 7, canal de WhatsApp). | Adotado **(67) 3341-4444** nas duas seções. | Aparece duas vezes, inclusive na tabela oficial de dados da empresa. Passar um número errado ao cliente é pior que unificar. |
| 2 | E-mail aparece como `contato@emporiodamusica.com.br` (capa) e `contato@empóriodamusica.com.br` (seção 1.2). | Adotado **`contato@emporiodamusica.com.br`**, sem acento. | Acento em domínio é quase certamente erro de digitação. |
| 3 | A tabela de pagamento diz "parcela mínima de R$ 100,00" para o crédito, mas a seção 3.1 define mínimos por faixa (R$ 50 / R$ 80 / R$ 100). | Vale a **seção 3.1**. A tabela passa a remeter a ela. | A regra específica prevalece sobre o resumo da tabela. |
| 4 | Seção 3.1, até 3x: "sem valor mínimo de parcela (exceto abaixo de R$ 50,00)". | Interpretado como **parcela mínima de R$ 50,00**. | É a única leitura que dá sentido à exceção. |
| 5 | O manual diz que o catálogo tem "mais de 300 instrumentos", mas o sistema tem 64 produtos. | Frase **removida**. | O agente não deve afirmar algo que os dados contradizem. |

## Regras ambíguas mantidas no texto (tratadas no código ou no prompt)

- **Frete na região metropolitana:** o manual cobre "acima de R$ 500" (grátis) e "abaixo de R$ 500" (R$ 35), mas não o valor exato de R$ 500,00. Assumido: **R$ 500,00 paga a taxa**, pela leitura literal de "acima de".
- **Prazos com referências diferentes:** o arrependimento (7 dias) e a garantia legal (90 dias) contam do **recebimento**. A troca por defeito (30 dias) conta da **compra**. O agente respeita essa diferença.
- **Lojas parceiras:** o manual pede para "sugerir lojas parceiras quando possível", mas não lista nenhuma. O agente **não inventa** lojas; apenas explica que a loja não vende acessórios.
- **Horário de atendimento:** o manual pede que, fora do expediente, o assistente informe o horário de retorno. Para isso, o agente recebe a data e a hora atuais (fuso de Campo Grande).
- **Campanhas sazonais (seção 6.1):** descrevem o calendário da loja, mas **só valem as promoções ativas no sistema**. Ex.: em novembro, o agente não promete o desconto de Black Friday se ele não estiver ativo em `promotions.csv`.
- **Feriados:** o cálculo de "loja aberta agora" considera só os feriados nacionais de data fixa. Carnaval, Sexta-feira Santa, Corpus Christi e feriados municipais ficam de fora.

## Dados operacionais (`data/*.csv`)

| # | Observação nos dados | Decisão |
|---|---|---|
| 1 | Não existe data real de entrega, só `estimated_delivery`. | Para pedidos entregues, a data estimada é tratada como data de recebimento nos prazos de devolução e garantia. |
| 2 | Os pedidos 3 e 20 têm `total_brl` diferente da soma dos preços atuais dos itens. | Vale o `total_brl`, que é o que o cliente pagou. Preços mudam com o tempo. |
| 3 | Um produto pode ter mais de uma promoção cadastrada. | Promoções não acumulam (política 6.2), então vale só a ativa de maior desconto. Hoje nenhum produto tem duas ativas. |
| 4 | As categorias de sopro e de cordas orquestrais não têm nenhum produto. | O agente informa que no momento não há opções, sem inventar produtos. |
| 5 | Os clientes 11 e 43 têm o mesmo e-mail (provável cadastro duplicado). | A verificação de pedido compara o e-mail do cliente dono do pedido, então funciona para os dois. |
| 6 | O pedido 8 está "enviado" com entrega estimada já vencida. | A ferramenta marca o pedido como atrasado, e o agente orienta o cliente a falar com a equipe. |
| 7 | Os status `pending` e `confirmed` não são explicados. | Interpretados como "aguardando confirmação do pagamento" e "pagamento confirmado, em preparação". |
| 8 | Produtos `discontinued`, `coming_soon` ou com estoque zero. | Aparecem na busca com a situação indicada, para o agente sugerir alternativas (política 7.3), mas ficam fora do cálculo de pagamento. |

## Regras de negócio implementadas no código

- **Filtro de preço:** "até R$ 1.000" considera o preço final com promoção ativa, que é o que o cliente paga. O desconto do PIX não entra no filtro.
- **Consulta de pedido:** exige o número do pedido e o e-mail do cliente. Se algum dos dois não bater, a resposta é a mesma ("não encontrado"), para não revelar quais pedidos existem. Em produção, a identidade viria do próprio número de WhatsApp.
