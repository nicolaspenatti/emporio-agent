# Conversa 1: catálogo e pagamento

- **Cenário:** busca de violões por faixa de preço, depois preço e parcelamento de um modelo específico.
- **Data e hora simuladas:** 30/10/2025 10:00 (`EMPORIO_NOW=2025-10-30T10:00`)
- **Modelo:** `gemini-3.5-flash`
- **O que observar:** o agente filtra só produtos disponíveis, mostra o valor no PIX e calcula as parcelas pela ferramenta, sem fazer conta de cabeça.

---

**Cliente:** Oi! Quais violões vocês têm até R$1000?

> 🔧 `search_products({"max_price": 1000, "category": "Violões", "only_available": true})`

**Assistente:** Oi! Temos várias opções incríveis de violões até R$ 1.000 disponíveis na loja! 🎸

**Cordas de Nylon (ideais para MPB, clássico e iniciantes):**
- **Tagima Memphis AC-39:** R$ 429,90 (R$ 408,40 no PIX)
- **Rozini RC-104 Estudante:** R$ 459,90 (R$ 436,90 no PIX)
- **Yamaha C40:** R$ 599,90 (R$ 569,90 no PIX)
- **Giannini GN-15 Cedro:** R$ 689,00 (R$ 654,55 no PIX)
- **Yamaha C70:** R$ 849,00 (R$ 806,55 no PIX)

**Cordas de Aço (som mais brilhante, ótimo para pop, rock e sertanejo):**
- **Shelby SN-100 Folk:** R$ 549,00 (R$ 521,55 no PIX)
- **Giannini GF-1R Folk:** R$ 579,90 (R$ 550,90 no PIX)
- **Yamaha F310:** R$ 699,90 (R$ 664,90 no PIX)
- **Tagima Dallas Tuner:** R$ 749,00 (R$ 711,55 no PIX)
- **Shelby SGD-195E Elétrico:** R$ 799,00 (R$ 759,05 no PIX)

Você prefere nylon ou aço, ou busca algum estilo específico?

**Cliente:** E o Takamine GD20, quanto sai? Dá pra parcelar em 12x?

> 🔧 `search_products({"query": "Takamine GD20"})`
> 🔧 `payment_options({"items": [{"product_id": 95, "quantity": 1}]})`

**Assistente:** O **Takamine GD20 Dreadnought Natural** está saindo por **R$ 2.199,00** (ou R$ 2.089,05 no PIX com 5% de desconto).

E dá pra parcelar em 12x sim! Fica em **12x de R$ 183,25 sem juros** no cartão de crédito. 🎸
