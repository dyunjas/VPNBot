import { DOCUMENT_LINKS } from "./links.js";

export function DocumentLinks({external=false}) {
  return DOCUMENT_LINKS.map(([title,href])=><a key={href} href={href} {...(external?{target:"_blank",rel:"noopener noreferrer"}:{})} onClick={event=>{
    if(external&&window.Telegram?.WebApp?.openLink){event.preventDefault();window.Telegram.WebApp.openLink(href);}
  }}>{title}</a>);
}
