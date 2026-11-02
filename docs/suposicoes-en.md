# Assumptions and data handling

> English version of [`suposicoes.md`](suposicoes.md). Store data and policy quotes are kept in Portuguese, as in the original files.

The case asks that ambiguities be resolved with a reasonable, documented interpretation. This file records each one.

## Policy manual (`data/politicas_da_loja.md`)

The original PDF was transcribed to Markdown. The whole manual goes into the agent's system prompt, and the automatically extracted text came out broken word by word. The transcription is faithful to the original, except for the points below. The original PDF is kept in `data/` for reference.

| # | Inconsistency in the original | Decision | Reason |
|---|---|---|---|
| 1 | The phone/WhatsApp number appears as **(67) 3341-4444** (cover and "Dados da Empresa" table) and as **(67) 3321-4500** (section 7, WhatsApp channel). | **(67) 3341-4444** is used in both sections. | It appears twice, including in the official company data table. Giving a customer a wrong number is worse than unifying. |
| 2 | The e-mail appears as `contato@emporiodamusica.com.br` (cover) and `contato@empóriodamusica.com.br` (section 1.2). | **`contato@emporiodamusica.com.br`**, without the accent. | An accent in a domain name is almost certainly a typo. |
| 3 | The payment table says "minimum installment of R$ 100.00" for credit cards, but section 3.1 defines minimums by range (R$ 50 / R$ 80 / R$ 100). | **Section 3.1** applies. The table now refers to it. | The specific rule prevails over the table summary. |
| 4 | Section 3.1, up to 3 installments: "no minimum installment value (except below R$ 50.00)". | Interpreted as a **minimum installment of R$ 50.00**. | It is the only reading that makes sense of the exception. |
| 5 | The manual says the catalog has "more than 300 instruments", but the system has 65 products. | Sentence **removed**. | The agent must not state something the data contradicts. |

## Ambiguous rules kept in the text (handled in code or in the prompt)

- **Local shipping:** the manual covers orders "above R$ 500" (free) and "below R$ 500" (R$ 35), but not exactly R$ 500.00. Assumed: **R$ 500.00 pays the fee**, by the literal reading of "above".
- **Deadlines with different starting points:** the right of withdrawal (7 days) and the legal warranty (90 days) count from **delivery**. Defect exchanges (30 days) count from the **purchase**. The agent respects this difference.
- **Partner stores:** the manual asks to "suggest partner stores when possible", but lists none. The agent **does not make up** stores; it only explains that the store does not sell accessories.
- **Opening hours:** the manual asks the assistant to tell customers when the team will be back when they write outside business hours. For that, the agent receives the current date and time (Campo Grande timezone).
- **Seasonal campaigns (section 6.1):** they describe the store's calendar, but **only promotions active in the system apply**. E.g., in November the agent does not promise a Black Friday discount unless it is active in `promotions.csv`.
- **Holidays:** "is the store open now" only considers fixed-date national holidays. Carnival, Good Friday, Corpus Christi and municipal holidays are left out.

## Operational data (`data/*.csv`)

| # | Observation in the data | Decision |
|---|---|---|
| 1 | There is no actual delivery date, only `estimated_delivery`. | For delivered orders, the estimated date is treated as the delivery date for return and warranty deadlines. |
| 2 | Orders 3 and 20 have a `total_brl` different from the sum of the items' current prices. | `total_brl` prevails, since it is what the customer paid. Prices change over time. |
| 3 | A product can have more than one promotion registered. | Promotions do not stack (policy 6.2), so only the active one with the highest discount applies. Currently no product has two active promotions. |
| 4 | The woodwind, brass and orchestral string categories have no products. | The agent says there are no options at the moment, without making up products. |
| 5 | Customers 11 and 43 share the same e-mail (likely a duplicate record). | Order verification compares the e-mail of the customer who placed the order, so it works for both. |
| 6 | Order 8 is "shipped" with an estimated delivery date already past. | The tool flags the order as delayed, and the agent tells the customer to contact the team. |
| 7 | The `pending` and `confirmed` statuses are not explained. | Interpreted as "awaiting payment confirmation" and "payment confirmed, being prepared". |
| 8 | Products that are `discontinued`, `coming_soon` or out of stock. | They show up in search with their status, so the agent can suggest alternatives (policy 7.3), but are left out of payment calculations. |

## Business rules implemented in code

- **Price filter:** "up to R$ 1,000" uses the final price with any active promotion, which is what the customer pays. The PIX discount is not part of the filter.
- **Order lookup:** requires the order number and the customer's e-mail. If either one does not match, the answer is the same ("not found"), so the tool does not reveal which orders exist. In production, identity would come from the customer's WhatsApp number.
