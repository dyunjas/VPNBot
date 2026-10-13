import {RefreshCw} from "lucide-react";
import {LunetLoader} from "../../shared/controls.jsx";

export default function RefreshButton({loading=false,disabled=false,children="Обновить",className="",...props}){
  return <button {...props} type="button" className={`ui-button ui-button-outline ui-refresh-button ${className}`} disabled={loading||disabled} aria-busy={loading||undefined}>
    <span className="ui-refresh-icon" aria-hidden="true">{loading?<LunetLoader size={14}/>:<RefreshCw size={14}/>}</span>
    {children}
  </button>;
}
