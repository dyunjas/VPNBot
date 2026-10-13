/* Add to the TurtleGuard challenge template AFTER window.__tgChal is set
 * and BEFORE /.turtleguard/c/*.js is loaded. This runs on the edge challenge,
 * not on the application's page, which is loaded after that challenge.
 * Preserve the fragment for same-origin navigation only.
 */
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
