# snug

Fit prioritised content into a token budget.

Every LLM application has to cram competing content — system prompts, conversation history, retrieved documents, tool definitions, a response reserve — into a fixed context window. `snug` solves this: give it a list of items with priorities and a token budget, and it returns the subset that fits.

- **Zero runtime dependencies**
- **Pluggable token counting** — bring your own tokeniser or use the built-in approximation
- **Pair constraints** — tool_use/tool_result pairs are never split
- **Dual ESM/CJS** — works in Node, Deno, Bun, and edge runtimes

## Install

```bash
npm install snug
```

## Usage

```ts
import { snug } from "snug";

const result = snug({
  budget: 4096,
  reserve: 1024, // tokens reserved for the model's response
  items: [
    { id: "system", content: "You are a helpful assistant.", priority: 100 },
    { id: "doc-1", content: retrievedDoc, priority: 10 },
    { id: "doc-2", content: anotherDoc, priority: 8 },
    { id: "history", content: conversationHistory, priority: 50 },
  ],
  countTokens: myTokenCounter, // (text: string) => number
});

// result.included  — items that fit, in original order
// result.excluded  — items that didn't fit, in original order
// result.tokensUsed
// result.tokensBudget  (= budget - reserve)
```

### Pair constraints

Anthropic's API requires every `tool_use` to have a matching `tool_result`. If you include one, you must include the other. Mark paired items with the `pair` field:

```ts
const items = [
  { id: "call-1", content: toolUseBlock, priority: 20, pair: "result-1" },
  { id: "result-1", content: toolResultBlock, priority: 20, pair: "call-1" },
  { id: "call-2", content: olderToolUse, priority: 5, pair: "result-2" },
  { id: "result-2", content: olderToolResult, priority: 5, pair: "call-2" },
];
```

Paired items are always included or excluded together. Their combined token cost is considered as a unit, and the higher priority of the two is used for ranking.

### Pre-computed token counts

If you already know an item's token cost, pass it directly to skip counting:

```ts
{ id: "system", content: systemPrompt, priority: 100, tokens: 342 }
```

### Token counting

Pass any `(text: string) => number` function. For example, with `tiktoken`:

```ts
import { encoding_for_model } from "tiktoken";

const enc = encoding_for_model("gpt-4o");
const countTokens = (text: string) => enc.encode(text).length;

snug({ budget: 128000, items, countTokens });
```

If no counter is provided, `snug` uses a rough approximation (~4 characters per token) and warns once via `console.warn`. This is fine for prototyping but not production — the approximation can be off by up to ~37% on real payloads.

## API

### `snug(options): SnugResult`

#### Options

| Field | Type | Required | Description |
|---|---|---|---|
| `budget` | `number` | Yes | Total token budget |
| `items` | `SnugItem[]` | Yes | Items to consider |
| `countTokens` | `(text: string) => number` | No | Token counting function |
| `reserve` | `number` | No | Tokens to reserve (subtracted from budget) |

#### SnugItem

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | Yes | Unique identifier |
| `content` | `string` | Yes | Text content |
| `priority` | `number` | Yes | Higher = more important |
| `tokens` | `number` | No | Pre-computed token count |
| `pair` | `string` | No | ID of paired item (both must reference each other) |

#### SnugResult

| Field | Type | Description |
|---|---|---|
| `included` | `SnugItem[]` | Items that fit, in original order |
| `excluded` | `SnugItem[]` | Items that didn't fit, in original order |
| `tokensUsed` | `number` | Total tokens of included items |
| `tokensBudget` | `number` | Effective budget (budget − reserve) |

## Algorithm

Items are sorted by priority (descending), with ties broken by token cost (ascending, to maximise inclusion). Paired items are merged into a single unit with combined cost and the higher priority of the two. Units are greedily packed until the budget is exhausted.

This is intentionally simple. A greedy approach is O(n log n), predictable, and easy to reason about. It avoids the complexity of knapsack optimisation or binary search over priority levels, which matter less in practice than clear, debuggable behaviour.

## License

MIT
