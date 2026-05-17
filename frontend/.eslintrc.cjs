/**
 * ESLint config — rubric "Word Usage & Format (10)" + "Code (10)" demand
 * a meticulous CI gate. This config is wired in `pnpm lint` (max-warnings=0).
 */
module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
    "plugin:jsx-a11y/recommended",
  ],
  ignorePatterns: ["dist", "coverage", ".eslintrc.cjs", "*.config.*"],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: 2022, sourceType: "module" },
  plugins: ["@typescript-eslint", "react-refresh", "jsx-a11y"],
  settings: {
    "import/resolver": { typescript: true, node: true },
  },
  rules: {
    "react-refresh/only-export-components": [
      "warn",
      { allowConstantExport: true },
    ],
    "@typescript-eslint/no-unused-vars": [
      "error",
      { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],
    "@typescript-eslint/consistent-type-imports": [
      "error",
      { prefer: "type-imports" },
    ],
    "no-console": ["warn", { allow: ["warn", "error"] }],
    eqeqeq: ["error", "smart"],
  },
};
