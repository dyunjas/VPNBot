(()=>{
  const challenge=window.__tgChal;
  if(!challenge?.next||!location.hash)return;
  try{
    const next=new URL(challenge.next,location.href);
    if(next.origin!==location.origin||next.hash)return;
    next.hash=location.hash;
    challenge.next=next.pathname+next.search+next.hash;
  }catch{}
})();
