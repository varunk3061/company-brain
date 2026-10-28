// Fails when a component or page defines styling values itself.
// All colours, fonts, radii, shadows and type sizes live in src/app/globals.css.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOTS = ["src/components", "src/app"];
const SKIP = new Set(["globals.css"]);

const PALETTE =
  "slate|gray|zinc|neutral|stone|indigo|blue|emerald|green|teal|cyan|sky|violet|purple|fuchsia|pink|rose|red|orange|amber|yellow|lime";

const RULES = [
  {
    name: "raw Tailwind palette colour (use a semantic token such as bg-surface, text-ink, border-line, bg-brand)",
    test: new RegExp(`(?<![\\w-])(?:text|bg|border|ring|divide|from|via|to|fill|stroke|shadow|outline|placeholder|accent|decoration|caret)-(?:(?:${PALETTE})-\\d{2,3}|white|black)(?![\\w-])`),
  },
  { name: "colour literal (#hex, rgb(), hsl())", test: /#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b(?![\w-])|\b(?:rgba?|hsla?|oklch)\(/ },
  { name: "arbitrary value in a class (add a token to globals.css instead)", test: /(?<![\w-])(?:[a-z0-9-]+:)*-?[a-z]+(?:-[a-z]+)*-\[[^\]\s]+\]/ },
  { name: "inline style prop", test: /\bstyle=\{/ },
  { name: "font-family literal", test: /font-family\s*:|fontFamily\s*:/ },
];

// Lines that legitimately contain '#': hrefs to fragments and the [[citation]] syntax are not colours.
const IGNORE_LINE = /href=["']#|\[\[|\]\]/;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* walk(path);
    else if (/\.(js|jsx|ts|tsx|css)$/.test(name) && !SKIP.has(name)) yield path;
  }
}

let failures = 0;

for (const root of ROOTS) {
  for (const file of walk(root)) {
    readFileSync(file, "utf8")
      .split("\n")
      .forEach((line, index) => {
        if (IGNORE_LINE.test(line) || /^\s*(\/\/|\*|\{\/\*)/.test(line)) return;
        for (const rule of RULES) {
          if (rule.test.test(line)) {
            failures += 1;
            console.error(`${file}:${index + 1}  ${rule.name}\n    ${line.trim()}`);
          }
        }
      });
  }
}

if (failures) {
  console.error(`\n${failures} style violation(s). Define the value in src/app/globals.css and use its utility.`);
  process.exit(1);
}
console.log("style check passed: no colours, fonts or inline styles outside globals.css");
