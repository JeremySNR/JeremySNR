/**
 * snug — fit prioritised content into a token budget.
 */

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface SnugItem {
  /** Unique identifier for this item. */
  id: string;
  /** The text content whose tokens are counted. */
  content: string;
  /** Higher number = higher priority (included first). */
  priority: number;
  /**
   * Pre-computed token count. When provided the token counter is not called
   * for this item, which is useful when you already know the cost.
   */
  tokens?: number;
  /**
   * ID of another item that must be included or excluded together with this
   * one. Both items in a pair must reference each other. This is designed for
   * the tool_use / tool_result pairing required by Anthropic's API — if one
   * half is included the other must be too.
   */
  pair?: string;
}

export interface SnugOptions {
  /** Available token budget (excluding any reserve). */
  budget: number;
  /** Items to consider. */
  items: readonly SnugItem[];
  /**
   * Token counting function. Accepts a string and returns its token count.
   * When omitted a rough character-based approximation (~4 chars per token)
   * is used and a warning is emitted via `console.warn` on the first call.
   */
  countTokens?: (text: string) => number;
  /**
   * Tokens to reserve (e.g. for the model's response). Subtracted from
   * `budget` before packing. Defaults to 0.
   */
  reserve?: number;
}

export interface SnugResult {
  /** Items that fit within the budget, in their original order. */
  included: SnugItem[];
  /** Items that did not fit, in their original order. */
  excluded: SnugItem[];
  /** Total tokens consumed by included items. */
  tokensUsed: number;
  /** Effective budget that was available (budget − reserve). */
  tokensBudget: number;
}

// ---------------------------------------------------------------------------
// Default token approximation
// ---------------------------------------------------------------------------

let warnedAboutDefault = false;

function defaultCountTokens(text: string): number {
  if (!warnedAboutDefault) {
    warnedAboutDefault = true;
    console.warn(
      "[snug] Using default token approximation (~4 chars/token). " +
        "Pass a countTokens function for accurate results."
    );
  }
  return Math.ceil(text.length / 4);
}

/** Reset the one-time warning flag (exported for testing). */
export function _resetDefaultWarning(): void {
  warnedAboutDefault = false;
}

// ---------------------------------------------------------------------------
// Core algorithm
// ---------------------------------------------------------------------------

export function snug(options: SnugOptions): SnugResult {
  const { budget, items, reserve = 0 } = options;
  const countTokens = options.countTokens ?? defaultCountTokens;
  const effectiveBudget = budget - reserve;

  if (effectiveBudget < 0) {
    return {
      included: [],
      excluded: [...items],
      tokensUsed: 0,
      tokensBudget: effectiveBudget,
    };
  }

  // Build an index for fast lookup and compute token costs.
  const indexById = new Map<string, number>();
  const tokenCosts: number[] = new Array(items.length);

  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    if (indexById.has(item.id)) {
      throw new Error(`[snug] Duplicate item id: "${item.id}"`);
    }
    indexById.set(item.id, i);
    tokenCosts[i] = item.tokens ?? countTokens(item.content);
  }

  // Validate pairs — both sides must exist and reference each other.
  for (const item of items) {
    if (item.pair !== undefined) {
      const pairIdx = indexById.get(item.pair);
      if (pairIdx === undefined) {
        throw new Error(
          `[snug] Item "${item.id}" references pair "${item.pair}" which does not exist`
        );
      }
      if (items[pairIdx].pair !== item.id) {
        throw new Error(
          `[snug] Pair mismatch: "${item.id}" references "${item.pair}" ` +
            `but "${item.pair}" does not reference "${item.id}" back`
        );
      }
    }
  }

  // Build packing units. Paired items become a single unit so they are
  // never split. We use the *maximum* priority of the pair (if either half
  // is important, include both) and the combined token cost.
  interface Unit {
    indices: number[];
    priority: number;
    cost: number;
  }

  const visited = new Set<number>();
  const units: Unit[] = [];

  for (let i = 0; i < items.length; i++) {
    if (visited.has(i)) continue;
    visited.add(i);

    const item = items[i];
    if (item.pair !== undefined) {
      const j = indexById.get(item.pair)!;
      visited.add(j);
      units.push({
        indices: [i, j],
        priority: Math.max(item.priority, items[j].priority),
        cost: tokenCosts[i] + tokenCosts[j],
      });
    } else {
      units.push({
        indices: [i],
        priority: item.priority,
        cost: tokenCosts[i],
      });
    }
  }

  // Sort units by priority descending, then by cost ascending (prefer
  // cheaper items at the same priority to maximise inclusion).
  units.sort((a, b) => b.priority - a.priority || a.cost - b.cost);

  // Greedy packing.
  const includedSet = new Set<number>();
  let tokensUsed = 0;

  for (const unit of units) {
    if (tokensUsed + unit.cost <= effectiveBudget) {
      tokensUsed += unit.cost;
      for (const idx of unit.indices) {
        includedSet.add(idx);
      }
    }
  }

  // Partition into included/excluded preserving original order.
  const included: SnugItem[] = [];
  const excluded: SnugItem[] = [];

  for (let i = 0; i < items.length; i++) {
    if (includedSet.has(i)) {
      included.push(items[i]);
    } else {
      excluded.push(items[i]);
    }
  }

  return { included, excluded, tokensUsed, tokensBudget: effectiveBudget };
}

export default snug;
