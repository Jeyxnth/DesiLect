// A small Python/JavaScript tokenizer for colouring code. It only splits text into typed pieces that are
// drawn as SVG text: the code is never executed or injected as HTML (H4).

export type TokenKind = "kw" | "str" | "num" | "com" | "plain";
export interface Token {
  kind: TokenKind;
  text: string;
}
export type CodeLang = "python" | "js";

const PYTHON_KW = new Set(
  ("False None True and as assert async await break class continue def del elif else except finally for from " +
    "global if import in is lambda nonlocal not or pass raise return try while with yield").split(" "),
);
const JS_KW = new Set(
  ("async await break case catch class const continue default delete do else export extends false finally for " +
    "function if import in instanceof let new null of return super switch this throw true try typeof undefined var void while yield").split(" "),
);

export function codeLang(hint: string | undefined, code: string): CodeLang {
  const h = (hint ?? "").toLowerCase();
  if (/\b(js|javascript|ts|typescript|node)\b/.test(h)) return "js";
  if (/\b(py|python)\b/.test(h)) return "python";
  return /\b(const|let|function)\b|=>|;\s*$/m.test(code) ? "js" : "python";
}

const PATTERNS: Record<CodeLang, RegExp> = {
  python: /(#.*$)|("(?:\\.|[^"\\])*"?|'(?:\\.|[^'\\])*'?)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)/g,
  js: /(\/\/.*$|\/\*.*?\*\/)|("(?:\\.|[^"\\])*"?|'(?:\\.|[^'\\])*'?|`(?:\\.|[^`\\])*`?)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_$][\w$]*)/g,
};

/** Tokens for one line; plain runs are merged. */
export function tokenizeLine(line: string, lang: CodeLang): Token[] {
  const keywords = lang === "js" ? JS_KW : PYTHON_KW;
  const re = new RegExp(PATTERNS[lang].source, "g");
  const out: Token[] = [];
  const push = (kind: TokenKind, text: string) => {
    if (!text) return;
    const last = out[out.length - 1];
    if (last && last.kind === kind && kind === "plain") last.text += text;
    else out.push({ kind, text });
  };
  let pos = 0;
  for (let m = re.exec(line); m; m = re.exec(line)) {
    push("plain", line.slice(pos, m.index));
    if (m[1]) push("com", m[0]);
    else if (m[2]) push("str", m[0]);
    else if (m[3]) push("num", m[0]);
    else push(keywords.has(m[0]) ? "kw" : "plain", m[0]);
    pos = m.index + m[0].length;
    if (m[0].length === 0) re.lastIndex++;
  }
  push("plain", line.slice(pos));
  return out;
}

const NOT_TERMS = new Set("a an the is it in to of and or i x".split(" "));

/** Identifiers and keywords in the code that could be a caption's key term. */
export function codeTerms(code: string): Set<string> {
  const terms = new Set<string>();
  for (const m of code.matchAll(/[A-Za-z_][\w]*/g)) if (m[0].length >= 2 && !NOT_TERMS.has(m[0].toLowerCase())) terms.add(m[0]);
  return terms;
}

/** The longest code term the caption mentions (whole word), or null. */
export function keyTerm(caption: string, terms: Set<string>): string | null {
  const words = new Set(caption.match(/[A-Za-z_][\w]*/g) ?? []);
  let best: string | null = null;
  for (const t of terms) if (words.has(t) && (!best || t.length > best.length)) best = t;
  return best;
}
