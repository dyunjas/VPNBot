import { useEffect } from "react";

function repair(value) {
  value = String(value || "").replace(/\\u([0-9a-f]{4})/gi, (_, code) => String.fromCharCode(parseInt(code, 16)));
  // Only convert recognizable UTF-8 mojibake markers. A generic «Р/С +
  // Cyrillic» check is unsafe because it also matches normal words like
  // «Срок» and «Расход».
  if (!/(?:Р[џѕґїёє°]|С[ЃЊ]|в[‚Ђ]|�)/.test(value)) return value;
  const bytes = [];
  for (const char of value) {
    const code = char.charCodeAt(0);
    if (code >= 0x410 && code <= 0x44f) bytes.push(code - 0x350);
    else if (code === 0x401) bytes.push(0xa8);
    else if (code === 0x451) bytes.push(0xb8);
    else if (code >= 0x402 && code <= 0x40f) bytes.push(0xb0 + code - 0x402);
    else if (code >= 0x452 && code <= 0x45f) bytes.push(0x90 + code - 0x452);
    else if (code === 0x201a) bytes.push(0x82);
    else if (code >= 0x80 && code <= 0xff) bytes.push(code);
    else bytes.push(...new TextEncoder().encode(char));
  }
  try { return new TextDecoder().decode(new Uint8Array(bytes)); } catch { return value; }
}

export function TextRepair() {
  useEffect(() => {
    const scan = () => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach((node) => { const next = repair(node.nodeValue || ""); if (next !== node.nodeValue) node.nodeValue = next; });
      document.querySelectorAll("input[placeholder],button[aria-label],img[alt],option").forEach((node) => {
        ["placeholder", "aria-label", "alt"].forEach((attribute) => { if (node.hasAttribute(attribute)) { const next = repair(node.getAttribute(attribute)); if (next !== node.getAttribute(attribute)) node.setAttribute(attribute, next); } });
        if (node.tagName === "OPTION") { const next = repair(node.textContent || ""); if (next !== node.textContent) node.textContent = next; }
      });
    };
    scan();
    const observer = new MutationObserver(scan);
    observer.observe(document.body, { childList:true, subtree:true, characterData:true });
    return () => observer.disconnect();
  }, []);
  return null;
}
