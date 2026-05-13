import { describe, expect, it } from "vitest";
import { normalisePlate, plateAddRequest } from "./plate";

describe("normalisePlate", () => {
  it("uppercases and removes spaces", () => {
    expect(normalisePlate(" abc 123 ")).toBe("ABC123");
    expect(normalisePlate("Aa Bb")).toBe("AABB");
  });
});

describe("plateAddRequest schema", () => {
  it("normalises the plate via the transform", () => {
    const parsed = plateAddRequest.parse({ plate: "abc 123", label: null });
    expect(parsed.plate).toBe("ABC123");
  });
  it("rejects an empty plate", () => {
    expect(() => plateAddRequest.parse({ plate: "" })).toThrow();
  });
  it("rejects a plate longer than 16 chars", () => {
    expect(() =>
      plateAddRequest.parse({ plate: "A".repeat(17) }),
    ).toThrow();
  });
});
