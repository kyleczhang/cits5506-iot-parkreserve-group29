/**
 * Vitest setup — runs once before every test file.
 *
 * Pulls in `@testing-library/jest-dom` matchers so assertions like
 * `expect(el).toBeInTheDocument()` work out of the box.
 */
import "@testing-library/jest-dom/vitest";
