# Avaliação do agente

Os testes em `tests/` verificam as regras de negócio no código (preços, parcelas, prazos) sem chamar o modelo. Este diretório verifica o que depende do LLM: se ele chama a ferramenta certa, cita os números certos e recusa o que deve recusar.

```bash
uv run python evals/run_evals.py             # todos os casos
uv run python evals/run_evals.py devolucao   # só os casos com "devolucao" no nome
```

O resultado da última execução fica em [`results.md`](results.md).

## Como os casos são checados

Cada caso tem uma ou mais mensagens do cliente e checagens determinísticas:

- ferramentas que **devem** ou **não podem** ser chamadas;
- textos que **devem** aparecer (ex.: o valor da parcela, `183,25`);
- textos que **não podem** aparecer (ex.: o preço com desconto falso, ou o e-mail de outro cliente).

Escolhi checagens por texto em vez de um segundo LLM como juiz porque são previsíveis, baratas e fáceis de auditar. A contrapartida aparece abaixo.

São 18 casos, em quatro grupos: catálogo e promoções, políticas e escopo, pedidos e privacidade, e prompt injection.

## O que a avaliação ensinou

1. **Falso negativo da checagem.** O caso `devolucao_fora_do_prazo` falhou porque o agente escreveu "fora *desse* prazo", e a checagem só aceitava "fora *do* prazo". A resposta estava certa; o teste é que estava rígido. Esse é o custo das checagens por texto: um juiz LLM toleraria variações, mas custaria mais e seria menos previsível.
2. **Limite do plano gratuito.** Uma execução falhou com erro 429 (15 requisições por minuto). O script agora pausa entre os casos e marca erros de API como ⚠️, separados das falhas reais do agente.
3. **Falha intermitente.** No caso `fora_do_escopo` ("Qual é a capital da França?"), o modelo reserva às vezes respondia "Paris!" antes de redirecionar. As tentativas de correção no prompt:

| Tentativa | Resultado em 10 rodadas |
|---|---|
| Regra original: "recuse com simpatia em uma frase" | ~1 falha a cada 6 |
| Regra + exemplo de recusa (com outra pergunta, para não "ensinar para a prova") | 10/10, mas o modelo **copiava o exemplo palavra por palavra** |
| Mesmo exemplo + "use suas próprias palavras" | Continuou copiando |
| Sem exemplo, descrevendo o erro: "não responda primeiro para depois redirecionar" | 9/10, com respostas variadas e naturais |

Fiquei com a última versão: a falha que sobra é inofensiva (uma curiosidade geral) e acontece no modelo reserva. Um caso que às vezes passa e às vezes falha só aparece rodando várias vezes. Com mais tempo, o script rodaria cada caso N vezes e reportaria a taxa de acerto.

## Limitações

- Durante o desenvolvimento, o modelo principal (`gemini-3.5-flash`) ficou indisponível por horas, então quase todas as execuções usaram o modelo reserva (`gemini-flash-lite-latest`).
- Cada execução custa cerca de 40 chamadas à API e leva por volta de 3 minutos, por causa das pausas do plano gratuito.
