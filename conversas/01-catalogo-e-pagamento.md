# Conversa 1: catálogo e pagamento

- **Cenário:** busca de violões por faixa de preço, depois preço e parcelamento de um modelo específico.
- **Data e hora simuladas:** 30/10/2025 10:00 (`EMPORIO_NOW=2025-10-30T10:00`)
- **Modelo:** `gemini-flash-lite-latest` (reserva; o modelo principal estava sobrecarregado)
- **O que observar:** o agente filtra só produtos disponíveis, mostra o valor no PIX e calcula as parcelas pela ferramenta, sem fazer conta de cabeça.

---

**Cliente:** Oi! Quais violões vocês têm até R$1000?

> 🔧 `search_products({"only_available": true, "max_price": 1000, "category": "Violões"})`

**Assistente:** Temos várias opções de violões até R$ 1.000,00 disponíveis por aqui. Olha só:

- *Tagima Memphis AC-39 Nylon Natural*: R$ 429,90 (ou R$ 408,40 no PIX)
- *Rozini RC-104 Nylon Estudante*: R$ 459,90 (ou R$ 436,90 no PIX)
- *Shelby SN-100 Folk Aço Preto*: R$ 549,00 (ou R$ 521,55 no PIX)
- *Giannini GF-1R Aço Folk Sunburst*: R$ 579,90 (ou R$ 550,90 no PIX)
- *Yamaha C40 Nylon Natural*: R$ 599,90 (ou R$ 569,90 no PIX)
- *Giannini GN-15 Nylon Cedr Natural*: R$ 689,00 (ou R$ 654,55 no PIX)
- *Yamaha F310 Aço Natural*: R$ 699,90 (ou R$ 664,90 no PIX)
- *Tagima Dallas Tuner Aço Natural*: R$ 749,00 (ou R$ 711,55 no PIX)
- *Shelby SGD-195E Elétrico Aço Sunburst*: R$ 799,00 (ou R$ 759,05 no PIX)
- *Yamaha C70 Nylon Natural*: R$ 849,00 (ou R$ 806,55 no PIX)

Prefere com cordas de nylon ou de aço? 🎸

**Cliente:** E o Takamine GD20, quanto sai? Dá pra parcelar em 12x?

> 🔧 `search_products({"query": "Takamine GD20"})`
> 🔧 `payment_options({"items": [{"product_id": 95, "quantity": 1}]})`

**Assistente:** O *Takamine GD20 Dreadnought Natural* sai por R$ 2.199,00 (ou R$ 2.089,05 no PIX).

E sim, dá para parcelar no cartão de crédito em até 12x sem juros de R$ 183,25! 🎸

---

**Evolução:** na primeira versão do prompt, o agente usava negrito do Markdown (`**texto**`), que não funciona no WhatsApp. Agora usa o formato do WhatsApp (`*texto*`).
