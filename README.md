# Empório da Música: Customer Service Agent

<sub>🇧🇷 [Versão em português](README.pt-BR.md)</sub>

A text-based customer service agent for Empório da Música, a fictional musical instrument store in Campo Grande, Brazil. It answers questions about products, prices, promotions, payment, orders and store policies, and politely declines anything outside the store's scope.

The agent talks to customers in Brazilian Portuguese, so the example conversations, the prompt and the store data are in Portuguese. Code, this README and the [assumptions document](docs/suposicoes-en.md) are in English; the evaluation notes and the prompt injection report are in Portuguese.

<p align="center"><img src="docs/demo-web.png" alt="Web demo: a phone-style chat where the agent quotes the price of a guitar and its installment options" width="320"></p>

<p align="center"><em>Web demo with "show tool calls" turned on: every price comes from a tool call, not from the model's memory.</em></p>

## Quick start

**Requirements:** [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 automatically) and a free Gemini API key from [Google AI Studio](https://aistudio.google.com) ("Get API key"; no credit card needed).

```bash
git clone https://github.com/nicolaspenatti/emporio-agent.git
cd emporio-agent
cp .env.example .env          # then paste your key into GEMINI_API_KEY
uv sync
```

| Command | What it does |
|---|---|
| `uv run emporio-agent` | Chat in the terminal. Commands: `/nova` (new conversation), `/sair` (quit) |
| `uv run emporio-agent --debug` | Same, also showing every tool call, its arguments and the model that answered |
| `uv run emporio-web` | Web demo at http://localhost:8000, a phone-style chat with an option to show tool calls |
| `uv run pytest` | 33 unit tests for business rules and agent safeguards (no API key needed) |
| `uv run python evals/run_evals.py` | 18 end-to-end evaluation cases against the real model (about 3 minutes) |

Optional settings in `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_MODEL` | `gemini-3.5-flash` | Main model |
| `GEMINI_FALLBACK_MODEL` | `gemini-flash-lite-latest` | Used when the main model is slow or overloaded |
| `EMPORIO_NOW` | current time | Pins the date and time (e.g. `2025-10-30T10:00`) so date-based rules, like return deadlines, can be demonstrated |
| `PORT` | `8000` | Port for the web demo |

## How it works

```
customer message
      │
      ▼
Gemini, with a system prompt built on every turn:
persona + service rules + full policy manual + current time and opening status
      │
      │  decides whether it needs data
      ▼
┌──────────────────┬───────────────────┬────────────────────┐
│ search_products  │ payment_options   │ get_order          │
│ catalog, active  │ totals per method,│ requires order id  │
│ promotion, final │ valid installments│ + matching e-mail; │
│ and PIX prices,  │ and shipping      │ return and warranty│
│ stock status     │                   │ deadlines          │
└──────────────────┴───────────────────┴────────────────────┘
      │  JSON results
      ▼
Gemini writes the answer in the store's tone of voice
```

| File | Responsibility |
|---|---|
| [`data.py`](src/emporio_agent/data.py) | Loads and cleans the CSVs into typed records |
| [`tools.py`](src/emporio_agent/tools.py) | Business rules: search, prices, promotions, installments, shipping, order lookup, opening hours |
| [`prompt.py`](src/emporio_agent/prompt.py) | System prompt: persona, rules, store status and the policy manual |
| [`agent.py`](src/emporio_agent/agent.py) | Function-calling loop, retries, fallback model and safeguards |
| [`cli.py`](src/emporio_agent/cli.py) / [`web.py`](src/emporio_agent/web.py) | Terminal chat and web demo |

## Technical decisions

### 1. The LLM talks, the code computes

This is the principle behind the whole design. LLMs are good at understanding what a customer wants and at writing a friendly answer. They are unreliable at arithmetic, date math and remembering which promotion is active. The store manual itself warns that wrong prices can amount to false advertising.

So everything that must be exact is computed in plain Python and handed to the model as data:

- **Prices:** original price, active promotion, final price, and PIX price. The PIX 5% discount does not stack with promotions.
- **Installments:** valid installments under the store's minimum-installment rules (R$ 50 / R$ 80 / R$ 100 depending on the number of installments).
- **Shipping:** fee or free shipping.
- **Orders:** whether an order is still within the 7-day return window, the 30-day defect exchange window or the 90-day legal warranty.
- **Opening hours:** whether the store is open right now, holidays included.

The model's job is to pick the right tool and phrase the result.

### 2. Function calling, no RAG

**Function calling** for operational data (products, orders), because it must be exact and current. Semantic retrieval is the wrong tool for "how much is product 95".

**No RAG for the policy manual.** The manual is about 11,000 characters (a few thousand tokens), so it fits in the system prompt with room to spare. Retrieval would add an embedding model, a vector store and chunking. It would also add a new failure mode: the retriever returning the wrong chunk. The manual's rules also interact. For example, the PIX discount depends on the promotion rules, and return deadlines differ for regret and for defects. With the whole manual in context, the model sees those connections. If the manual grew to hundreds of pages, I would switch to RAG.

### 3. A hand-written loop instead of a framework

The Gemini SDK and frameworks like LangChain or LangGraph can run the tool loop automatically. I wrote it by hand ([`agent.py`](src/emporio_agent/agent.py)) because the loop is about 30 lines and keeps every step visible: which tool was called, with which arguments, and what came back. That visibility powers the `--debug` mode and the evaluation script. It also makes the safeguards easy to place, such as the order lookup limit described below. For a single agent with three tools, a framework would hide exactly the logic this case is evaluating.

### 4. Model: Gemini Flash on the free tier, with a fallback

- **Free and reproducible:** anyone evaluating this project can get a key in two minutes, with no billing setup.
- **Good native function calling and low latency,** which matters in a chat.
- **Not a local model (Ollama):** small local models are noticeably less reliable at tool calling. They would also require downloading several GB to run the project.

The free tier is not always available. During development the main model (`gemini-3.5-flash`) returned "high demand" errors for hours, and older models such as `gemini-2.5-flash` are closed to new users. So the agent has:

- **A fallback model** (`gemini-flash-lite-latest`). The main model gets 2 attempts with a 12-second timeout, then the agent switches. A slow model switches immediately. The first version waited up to 30 seconds per attempt, and the web demo made it obvious that nobody waits that long in a chat.
- **Retries only for temporary errors** (429 and 5xx). A model that does not exist for the key (404, as already happened with `gemini-2.5-flash`) is skipped straight to the fallback. Any other error is a bug and is not hidden.
- **A friendly message** when everything fails. The failed turn is also removed from the history, so the conversation never gets corrupted.

### 5. Prompt strategy

- **Written in Portuguese,** like the customers, the manual and the expected answers.
- **Rebuilt on every turn** with the current date, time and opening status. The manual asks the assistant to tell customers when the team will be back, and that requires knowing the time.
- **Rules come from the manual's service guidelines:**
  - tone of voice and WhatsApp formatting;
  - always show the original price and the discount next to a promotional price;
  - verify before promising a refund or exchange;
  - never ask again for data the customer already gave;
  - only instruments are sold;
  - ignore attempts to change the agent's role.
- **Iterated against real failures.** Each rule added after the first version fixes a behaviour observed in testing. The before and after notes are in the [example conversations](conversas/). One finding: a few-shot example of a polite refusal fixed an off-topic answer, but the model then copied the example word for word. Describing the mistake to avoid worked better (see [`evals/README.md`](evals/README.md)).

### 6. Data handling

- **CSVs are loaded into memory** as typed records. With 65 products and 20 orders, a database would add setup without any benefit.
- **The policy PDF was transcribed to Markdown.** Text extraction broke it word by word, and it goes into the prompt as is. Five inconsistencies in the original were resolved and documented. For example, two different WhatsApp numbers, a typo in the e-mail domain, and an installment table that contradicted the detailed rules.
- **Data quirks were handled explicitly:**
  - no actual delivery date (the estimate is used);
  - order totals that differ from current prices (the amount paid is kept);
  - a duplicated customer e-mail;
  - empty categories;
  - an order still "shipped" months after its estimated delivery (flagged as delayed).

All assumptions are listed in [`docs/suposicoes-en.md`](docs/suposicoes-en.md).

### 7. Privacy and security: defense in layers

The prompt tells the model to protect customer data, but the critical protections do not depend on the model obeying:

- **Order lookup requires the order number and the customer's e-mail,** compared in code. A wrong e-mail and a non-existent order get the same answer, so the tool cannot be used to discover which orders exist.
- **After 3 failed lookups in a conversation, lookups are blocked in code.** A prompt injection test showed the model would happily try many order numbers with the same e-mail. The block also applies if the fourth attempt happens to be correct.
- **Prices only come from tools,** so a fake "manager-approved discount" or a "price I saw on the website" has nowhere to come from.

Ten prompt injection attacks were run against the real model. None leaked customer data, the instructions or a fake price ([report](docs/testes-prompt-injection.md)).

### 8. Interface and conversation history

- **CLI as the main interface,** since the case focuses on the agent.
- **Web demo** to show the agent as a customer would see it. It uses only the Python standard library HTTP server, so it adds no dependency.
- **History in memory, per session.** A conversation lasts while the chat is open, which is how a support chat behaves. Persisting conversations across restarts was out of scope (see "With more time").

## Testing and evaluation

| Layer | What it checks | Result |
|---|---|---|
| [Unit tests](tests/) (33) | Business rules on the real data: prices, promotions, PIX, installments, shipping, order privacy, deadlines, opening hours, lookup limit, fallback logic | All passing, no API key needed |
| [Evaluation](evals/) (18 cases) | LLM behaviour: right tool, right numbers, refusals, privacy, prompt injection | 18/18 on the last run ([results](evals/results.md)) |
| [Prompt injection report](docs/testes-prompt-injection.md) | 10 attacks: prompt leaking, role change, fake authority, data extraction, order enumeration, encoded instructions | No leaks; led to the lookup limit |

The evaluation uses deterministic checks (expected tool calls, text that must or must not appear) instead of an LLM judge, because they are predictable and easy to audit. The trade-off appeared in practice: one case failed because the agent wrote "fora *desse* prazo" and the check expected "fora *do* prazo". The [evaluation notes](evals/README.md) cover this and other lessons.

## Example conversations

Real, unedited outputs of the agent, in Portuguese:

1. [Catalog and payment](conversas/01-catalogo-e-pagamento.md): guitars under R$ 1,000, then price and 12 installments for a specific model
2. [Return within the deadline](conversas/02-devolucao.md): order verification and the 7-day regret policy applied to real dates
3. [Out of scope](conversas/03-fora-do-escopo.md): accessories, a programming request and an attempt to extract the prompt
4. [Order privacy](conversas/04-privacidade-de-pedido.md): the customer insists on an order status without the e-mail
5. [Store information](conversas/05-informacoes-gerais.md): answered from the policy manual, without tools

## Known limitations

- **Most testing ran on the fallback model.** The main model was unavailable for most of the development period. The fallback follows the rules well, but it is less precise. For example, it once stated the 12-installment limit before calling the payment tool, and it very occasionally answers a trivia question before declining.
- **Free tier limits:** about 15 requests per minute per model, which is fine for a demo but not for real traffic.
- **The main model is retried on every call,** even when it has just failed. A circuit breaker would go straight to the fallback for a few minutes.
- **Lexical product search.** Brand, model and words in the description work well; vague requests like "something warm for fingerstyle" depend on the model choosing good filters.
- **The agent informs but does not act.** It explains return, exchange and complaint rules and refers the customer to the team, but it does not open tickets.
- **Identity is an e-mail address.** In production, the verified WhatsApp number would identify the customer.
- **Single process, in-memory state:** conversations are lost on restart, and the lookup limit resets with a new conversation.
- **Only fixed-date national holidays** are known; Carnival, Easter-related and municipal holidays are not.
- **Evaluation runs each case once,** so intermittent failures can slip through.

## With more time

- Run each evaluation case several times and report pass rates; add an LLM judge for tone and completeness.
- A circuit breaker for the main model and response streaming to reduce perceived latency.
- Tools that act: register a complaint, open a return request, hand off to a human with the conversation summary.
- Semantic search (embeddings) over product descriptions for vague requests.
- Persist conversations (SQLite or Redis) and connect to the WhatsApp Business API.
- Tracing and metrics: latency, tool usage, fallback rate, refusal rate.

## How I used an AI coding assistant

I used **Claude Code** (Anthropic) as a pair programmer throughout the project. My workflow:

1. **Understanding before building.** I started by having it read the case and the data with me. We discussed the approach before writing code, for example weighing RAG against keeping the whole manual in context. The architecture decisions in this README came out of those discussions, and the final call on scope and rules was mine.
2. **Small steps, reviewed one at a time.** Claude generated each part (data loading, tools, agent loop, prompt, interface). I reviewed it, ran it and decided when to commit. The commit history follows those steps.
3. **Pushing back on complexity.** I noticed the code was getting more complex than it needed to be and ran a review focused on simplicity, mapping overlapping rules and unnecessary extras. The result was one tool fewer, two deadline rules merged into one and less code overall.
4. **Testing against the real model.** I asked for prompt injection tests. They revealed that the model could be used to guess order numbers, and I decided to add the lookup limit in code rather than in the prompt. The evaluation suite came from the same idea: "it seems to work" is not enough for an agent.
5. **Catching the assistant's mistakes.** Not everything it produced was right on the first try:
   - the product search failed on model codes written differently ("GD-20" vs "GD20"), caught by unit tests;
   - a timeout raised an exception the agent did not handle, caught in review;
   - one evaluation check was too strict, caught when a correct answer was marked as a failure.

   The code fixes came with regression tests.

## Project structure

```
├── src/emporio_agent/
│   ├── agent.py          # function-calling loop, retries, fallback, safeguards
│   ├── tools.py          # business rules exposed as tools
│   ├── data.py           # CSV loading and cleaning
│   ├── prompt.py         # system prompt
│   ├── cli.py            # terminal chat
│   ├── web.py            # web demo server (standard library only)
│   └── static/index.html # web demo page
├── data/                 # original CSVs and policy PDF + Markdown transcription
├── tests/                # unit tests (no API key needed)
├── evals/                # end-to-end evaluation against the real model
├── conversas/            # example conversations
└── docs/                 # assumptions, prompt injection report, demo screenshot
```
