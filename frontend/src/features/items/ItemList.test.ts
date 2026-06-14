import { describe, expect, it } from "vitest";
import { buildItemListPath } from "./ItemList";

describe("buildItemListPath", () => {
  it("includes topic and search query params for the item list", () => {
    expect(buildItemListPath({ topic: "AI", query: " agents " })).toBe("/api/items?q=agents&topic=AI");
  });

  it("uses the topic filter token when one is supplied", () => {
    expect(buildItemListPath({ topic: "openai.com", topicFilter: "source:openai.com", query: "" })).toBe(
      "/api/items?topic=source%3Aopenai.com",
    );
  });

  it("omits the display-only search results topic", () => {
    expect(buildItemListPath({ topic: "Search results", query: "openai" })).toBe("/api/items?q=openai");
  });
});
