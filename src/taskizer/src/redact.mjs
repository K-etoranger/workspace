// 伏せ字。

export function redactSecretText(value) {
  let text = String(value).replace(/xox[a-z]-[A-Za-z0-9-]+/g, "[REDACTED_SLACK_TOKEN]");
  text = text.replace(/((?:password|pass|パスワード|ログインパスワード)\s*(?:[:：=は(（])\s*)([^\s\n)）]+)/gi, "$1[REDACTED_SECRET]");
  text = text.replace(/([A-Za-z0-9!@#$%^&*._+\-=]{4,})(\s*(?:が|は)\s*(?:ログイン)?パスワード(?:です|だね|だ)?)/gi, "[REDACTED_SECRET]$2");
  text = text.replace(/([A-Za-z0-9!@#$%^&*._+\-=]{4,})(\s+これが(?:ログイン)?パスワード)/gi, "[REDACTED_SECRET]$2");
  text = text.replace(/(\n)([A-Za-z0-9!@#$%^&*._+\-=]{4,})(\n(?=[^\n]{0,160}(?:password|pass|パスワード)))/gi, "$1[REDACTED_SECRET]$3");
  return text;
}

function normalizeWidth(value) {
  return String(value || "")
    .replace(/[０-９]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0))
    .replace(/[＋＠．]/g, (c) => ({ "＋": "+", "＠": "@", "．": "." })[c]);
}

export function redactPii(value) {
  let text = normalizeWidth(value);
  text = text.replace(/https?:\/\/[^\s<>()]+/giu, "[URL省略]");
  text = text.replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/giu, "[メールアドレス省略]");
  text = text.replace(/(?:\+?\d[\d\s().（）\-‐‑‒–—―ー−]{6,}\d|\(\d{2,5}\)[\d\s.\-‐‑‒–—―ー−]{5,}\d)/gu, (match) => {
    const digits = (match.match(/\d/g) || []).length;
    if (digits < 10 || digits > 19) return match;
    if (/^\d{4}-\d{1,2}-\d{1,2}(?:\s+\d{1,2})?$/.test(match.trim().replace(/[‐‑‒–—―ー−]/g, "-"))) return match;
    return "[電話番号・識別番号省略]";
  });
  return text.replace(/〒?\s*\d{3}[\-‐‑‒–—―ー−]\d{4}/gu, "[郵便番号省略]");
}
