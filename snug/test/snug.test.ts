import { describe, it, expect, vi, beforeEach } from "vitest";
import { snug, _resetDefaultWarning } from "../src/index";
import type { SnugItem } from "../src/index";

// Deterministic token counter: 1 char = 1 token.
const charCounter = (s: string) => s.length;

beforeEach(() => {
  _resetDefaultWarning();
});

// ---------------------------------------------------------------------------
// Basic packing
// ---------------------------------------------------------------------------

describe("basic packing", () => {
  it("includes all items when they fit", () => {
    const items: SnugItem[] = [
      { id: "a", content: "hello", priority: 1 },
      { id: "b", content: "world", priority: 2 },
    ];
    const result = snug({ budget: 100, items, countTokens: charCounter });
    expect(result.included.map((i) => i.id)).toEqual(["a", "b"]);
    expect(result.excluded).toEqual([]);
    expect(result.tokensUsed).toBe(10);
  });

  it("excludes low-priority items first", () => {
    const items: SnugItem[] = [
      { id: "low", content: "aaaa", priority: 1 },
      { id: "high", content: "bbbb", priority: 10 },
      { id: "mid", content: "cccc", priority: 5 },
    ];
    const result = snug({ budget: 8, items, countTokens: charCounter });
    expect(result.included.map((i) => i.id)).toEqual(["high", "mid"]);
    expect(result.excluded.map((i) => i.id)).toEqual(["low"]);
    expect(result.tokensUsed).toBe(8);
  });

  it("prefers cheaper items at the same priority", () => {
    const items: SnugItem[] = [
      { id: "big", content: "aaaaaaa", priority: 1 },
      { id: "small", content: "bb", priority: 1 },
    ];
    const result = snug({ budget: 5, items, countTokens: charCounter });
    expect(result.included.map((i) => i.id)).toEqual(["small"]);
  });

  it("preserves original order in output", () => {
    const items: SnugItem[] = [
      { id: "c", content: "xx", priority: 1 },
      { id: "a", content: "xx", priority: 3 },
      { id: "b", content: "xx", priority: 2 },
    ];
    const result = snug({ budget: 4, items, countTokens: charCounter });
    // a and b have higher priority, included in original order
    expect(result.included.map((i) => i.id)).toEqual(["a", "b"]);
    expect(result.excluded.map((i) => i.id)).toEqual(["c"]);
  });
});

// ---------------------------------------------------------------------------
// Reserve
// ---------------------------------------------------------------------------

describe("reserve", () => {
  it("subtracts reserve from budget", () => {
    const items: SnugItem[] = [
      { id: "a", content: "hello", priority: 1 },
    ];
    const result = snug({
      budget: 10,
      reserve: 7,
      items,
      countTokens: charCounter,
    });
    expect(result.tokensBudget).toBe(3);
    expect(result.excluded.map((i) => i.id)).toEqual(["a"]);
  });

  it("returns empty when reserve exceeds budget", () => {
    const items: SnugItem[] = [
      { id: "a", content: "hi", priority: 1 },
    ];
    const result = snug({
      budget: 5,
      reserve: 10,
      items,
      countTokens: charCounter,
    });
    expect(result.included).toEqual([]);
    expect(result.tokensBudget).toBe(-5);
  });
});

// ---------------------------------------------------------------------------
// Pre-computed tokens
// ---------------------------------------------------------------------------

describe("pre-computed tokens", () => {
  it("uses item.tokens when provided", () => {
    const counter = vi.fn(charCounter);
    const items: SnugItem[] = [
      { id: "a", content: "ignored", priority: 1, tokens: 3 },
    ];
    const result = snug({ budget: 10, items, countTokens: counter });
    expect(counter).not.toHaveBeenCalled();
    expect(result.tokensUsed).toBe(3);
  });
});

// ---------------------------------------------------------------------------
// Pair constraints
// ---------------------------------------------------------------------------

describe("pair constraints", () => {
  it("includes both halves of a pair", () => {
    const items: SnugItem[] = [
      { id: "use", content: "call", priority: 10, pair: "result" },
      { id: "result", content: "response", priority: 5, pair: "use" },
      { id: "other", content: "xx", priority: 7 },
    ];
    const result = snug({ budget: 14, items, countTokens: charCounter });
    expect(result.included.map((i) => i.id)).toEqual(["use", "result", "other"]);
  });

  it("excludes both halves when the pair doesn't fit", () => {
    const items: SnugItem[] = [
      { id: "use", content: "aaaaaaa", priority: 10, pair: "result" },
      { id: "result", content: "bbbbbbb", priority: 10, pair: "use" },
      { id: "small", content: "cc", priority: 1 },
    ];
    // pair costs 14, budget is 5 — pair can't fit, small can
    const result = snug({ budget: 5, items, countTokens: charCounter });
    expect(result.included.map((i) => i.id)).toEqual(["small"]);
    expect(result.excluded.map((i) => i.id)).toEqual(["use", "result"]);
  });

  it("uses max priority of paired items", () => {
    const items: SnugItem[] = [
      { id: "use", content: "aa", priority: 1, pair: "result" },
      { id: "result", content: "bb", priority: 100, pair: "use" },
      { id: "solo", content: "cccc", priority: 50 },
    ];
    // budget=6: pair costs 4 (priority 100), solo costs 4 (priority 50)
    // pair wins, solo excluded
    const result = snug({ budget: 6, items, countTokens: charCounter });
    expect(result.included.map((i) => i.id)).toEqual(["use", "result"]);
  });

  it("never splits a pair", () => {
    // Even if one half fits, both must be excluded if the pair doesn't fit
    const items: SnugItem[] = [
      { id: "a", content: "x", priority: 10, pair: "b" },
      { id: "b", content: "yyyyyyyyyy", priority: 10, pair: "a" },
    ];
    const result = snug({ budget: 5, items, countTokens: charCounter });
    expect(result.included).toEqual([]);
    expect(result.excluded.map((i) => i.id)).toEqual(["a", "b"]);
  });

  it("throws on missing pair reference", () => {
    const items: SnugItem[] = [
      { id: "a", content: "x", priority: 1, pair: "nonexistent" },
    ];
    expect(() => snug({ budget: 10, items, countTokens: charCounter })).toThrow(
      /does not exist/
    );
  });

  it("throws on asymmetric pair", () => {
    const items: SnugItem[] = [
      { id: "a", content: "x", priority: 1, pair: "b" },
      { id: "b", content: "y", priority: 1 },
    ];
    expect(() => snug({ budget: 10, items, countTokens: charCounter })).toThrow(
      /does not reference/
    );
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe("edge cases", () => {
  it("handles empty items", () => {
    const result = snug({ budget: 100, items: [], countTokens: charCounter });
    expect(result.included).toEqual([]);
    expect(result.excluded).toEqual([]);
    expect(result.tokensUsed).toBe(0);
  });

  it("handles zero budget", () => {
    const items: SnugItem[] = [
      { id: "a", content: "hello", priority: 1 },
    ];
    const result = snug({ budget: 0, items, countTokens: charCounter });
    expect(result.included).toEqual([]);
  });

  it("handles items with empty content", () => {
    const items: SnugItem[] = [
      { id: "a", content: "", priority: 1 },
      { id: "b", content: "hi", priority: 2 },
    ];
    const result = snug({ budget: 5, items, countTokens: charCounter });
    expect(result.included.map((i) => i.id)).toEqual(["a", "b"]);
  });

  it("throws on duplicate ids", () => {
    const items: SnugItem[] = [
      { id: "a", content: "x", priority: 1 },
      { id: "a", content: "y", priority: 2 },
    ];
    expect(() => snug({ budget: 10, items, countTokens: charCounter })).toThrow(
      /Duplicate item id/
    );
  });

  it("handles single item that exactly fills budget", () => {
    const items: SnugItem[] = [
      { id: "a", content: "12345", priority: 1 },
    ];
    const result = snug({ budget: 5, items, countTokens: charCounter });
    expect(result.included.map((i) => i.id)).toEqual(["a"]);
    expect(result.tokensUsed).toBe(5);
  });

  it("handles single item one token over budget", () => {
    const items: SnugItem[] = [
      { id: "a", content: "123456", priority: 1 },
    ];
    const result = snug({ budget: 5, items, countTokens: charCounter });
    expect(result.included).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Default token counter
// ---------------------------------------------------------------------------

describe("default token counter", () => {
  it("warns once when no counter is provided", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const items: SnugItem[] = [
      { id: "a", content: "hello world!!", priority: 1 },
    ];
    snug({ budget: 100, items });
    snug({ budget: 100, items });
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("[snug]"));
    warn.mockRestore();
  });

  it("approximates ~4 chars per token", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const items: SnugItem[] = [
      { id: "a", content: "abcdefgh", priority: 1 }, // 8 chars = 2 tokens
    ];
    const result = snug({ budget: 2, items });
    expect(result.included.map((i) => i.id)).toEqual(["a"]);
    expect(result.tokensUsed).toBe(2);
    warn.mockRestore();
  });
});
