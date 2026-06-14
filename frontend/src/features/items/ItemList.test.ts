import { describe, expect, it } from "vitest";
import { buildItemListPath } from "./ItemList";

describe("buildItemListPath", () => {
  it("includes topic and search query params for the item list", () => {
    expect(buildItemListPath({ topic: "AI", query: " agents " })).toBe("/api/items?q=agents&topic=AI");
  });

  it("omits the display-only search results topic", () => {
    expect(buildItemListPath({ topic: "Search results", query: "openai" })).toBe("/api/items?q=openai");
  });
});
