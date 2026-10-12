import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import "./Select.css";

// Focus stays on the combobox; arrows browse options, Enter commits, Escape cancels.
export function LunetSelect({value,onChange,options,ariaLabel,disabled=false,placeholder="Выберите вариант",showCheck=true}) {
  const [open,setOpen]=useState(false),[index,setIndex]=useState(0);
  const [position,setPosition]=useState({above:false,height:240});
  const host=useRef(null), trigger=useRef(null), id=useId();
  const selected=options.findIndex(option=>String(option.value)===String(value));
  useLayoutEffect(()=>{
    if(!open)return;
    const measure=()=>{const rect=trigger.current.getBoundingClientRect(),below=innerHeight-rect.bottom-12;const above=below<Math.min(240,options.length*44+10)&&rect.top>below;setPosition({above,height:Math.min(240,Math.max(80,(above?rect.top-12:below)))});};
    measure();window.addEventListener("resize",measure);window.addEventListener("scroll",measure,true);
    return()=>{window.removeEventListener("resize",measure);window.removeEventListener("scroll",measure,true);};
  },[open,options.length]);
  useEffect(()=>{
    if(!open)return;
    const outside=e=>{if(!host.current.contains(e.target))setOpen(false);};
    document.addEventListener("pointerdown",outside);
    return()=>document.removeEventListener("pointerdown",outside);
  },[open]);
  useEffect(()=>{if(disabled)setOpen(false);},[disabled]);
  useEffect(()=>{if(open)document.getElementById(`${id}-${index}`)?.scrollIntoView({block:"nearest"});},[open,index,id]);
  const toggle=()=>{setIndex(Math.max(0,selected));setOpen(!open);};
  const commit=i=>{if(options[i])onChange(options[i].value);setOpen(false);trigger.current.focus();};
  const key=e=>{
    if(["ArrowDown","ArrowUp","Home","End"].includes(e.key)){
      e.preventDefault();
      if(!open){setOpen(true);setIndex(e.key==="End"?options.length-1:Math.max(0,selected));}
      else setIndex(i=>e.key==="Home"?0:e.key==="End"?options.length-1:Math.max(0,Math.min(options.length-1,i+(e.key==="ArrowDown"?1:-1))));
    } else if(e.key==="Enter"||e.key===" "){e.preventDefault();if(open)commit(index);else toggle();}
    else if(e.key==="Escape"){e.preventDefault();e.stopPropagation();setOpen(false);}
    else if(e.key==="Tab")setOpen(false);
  };
  return <div className="lunet-select" ref={host}><button type="button" className="lunet-select-trigger" ref={trigger} role="combobox" aria-label={ariaLabel} aria-haspopup="listbox" aria-expanded={open} aria-controls={`${id}-list`} aria-activedescendant={open?`${id}-${index}`:undefined} disabled={disabled||!options.length} onClick={toggle} onKeyDown={key}><span>{selected>=0?options[selected].label:placeholder}</span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button>{open&&<div className="lunet-select-options" style={{top:position.above?"auto":undefined,bottom:position.above?"calc(100% + 6px)":undefined,maxHeight:position.height}} id={`${id}-list`} role="listbox" aria-label={ariaLabel}>{options.map((option,i)=><div id={`${id}-${i}`} key={option.value} className={`lunet-select-option ${i===index?"highlighted":""}`} role="option" aria-selected={i===selected} onPointerMove={()=>setIndex(i)} onMouseDown={e=>e.preventDefault()} onClick={()=>commit(i)}><span>{option.label}</span>{showCheck&&i===selected&&<span aria-hidden="true">✓</span>}</div>)}</div>}</div>;
}
