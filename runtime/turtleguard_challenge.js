
(function(){
  window.__tgPowStarted = true;
  var cfg = window.__tgChal || {};
  var next = cfg.next, verifyURL = cfg.verify, powSeed = cfg.seed, powDiff = cfg.diff;
  var step = 0, done = false;
  var stages = [
    {label:"Проверяем соединение",detail:"Устанавливаем защищённый канал",value:12},
    {label:"Проверяем браузер",detail:"Браузер выполняет короткую проверку",value:38},
    {label:"Подтверждаем доступ",detail:"Проверяем результат",value:88},
    {label:"Готово",detail:"Перенаправляем на сайт",value:100}
  ];
  var barEl = document.getElementById("bar");
  var progressRoot = document.getElementById("progressRoot");
  var progressValue = document.getElementById("progressValue");
  var phaseLabel = document.getElementById("phaseLabel");
  var progressDetail = document.getElementById("progressDetail");
  var hostname = document.getElementById("hostname");
  if(hostname) hostname.textContent = location.hostname;
  var techToggle = document.getElementById("techToggle");
  var techBlock = document.getElementById("techBlock");
  var techData = document.getElementById("technical-data");
  if(techToggle && techBlock && techData){
    techToggle.addEventListener("click",function(){
      var open = techBlock.classList.toggle("is-open");
      techToggle.setAttribute("aria-expanded",open ? "true" : "false");
      techData.setAttribute("aria-hidden",open ? "false" : "true");
    });
  }
  function setStep(i){
    var state = stages[Math.max(0,Math.min(stages.length-1,i))];
    if(barEl) barEl.style.width = state.value + "%";
    if(progressValue) progressValue.textContent = state.value + " %";
    if(phaseLabel) phaseLabel.textContent = state.label;
    if(progressDetail) progressDetail.textContent = state.detail;
    if(progressRoot) progressRoot.setAttribute("aria-valuenow",String(state.value));
  }
  function swapText(el,text){
    if(!el) return;
    el.classList.add("is-changing");
    setTimeout(function(){el.textContent=text;el.classList.remove("is-changing");},180);
  }
  function sha256hex(ascii){
    function rr(x,n){return (x>>>n)|(x<<(32-n));}
    var K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    var H=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    var b=[],i,j;
    for(i=0;i<ascii.length;i++){var c=ascii.charCodeAt(i);if(c<128)b.push(c);else if(c<2048){b.push(192|(c>>6),128|(c&63));}else{b.push(224|(c>>12),128|((c>>6)&63),128|(c&63));}}
    var bl=b.length*8;b.push(0x80);while(b.length%64!=56)b.push(0);
    for(i=7;i>=0;i--)b.push((bl/Math.pow(2,i*8))&0xff);
    var w=new Array(64);
    for(i=0;i<b.length;i+=64){
      for(j=0;j<16;j++)w[j]=(b[i+j*4]<<24)|(b[i+j*4+1]<<16)|(b[i+j*4+2]<<8)|(b[i+j*4+3]);
      for(j=16;j<64;j++){var s0=rr(w[j-15],7)^rr(w[j-15],18)^(w[j-15]>>>3);var s1=rr(w[j-2],17)^rr(w[j-2],19)^(w[j-2]>>>10);w[j]=(w[j-16]+s0+w[j-7]+s1)|0;}
      var a=H[0],e2=H[1],f2=H[2],g2=H[3],h2=H[4],x=H[5],y=H[6],z=H[7];
      for(j=0;j<64;j++){var S1=rr(h2,6)^rr(h2,11)^rr(h2,25);var ch=(h2&x)^(~h2&y);var t1=(z+S1+ch+K[j]+w[j])|0;var S0=rr(a,2)^rr(a,13)^rr(a,22);var mj=(a&e2)^(a&f2)^(e2&f2);var t2=(S0+mj)|0;z=y;y=x;x=h2;h2=(g2+t1)|0;g2=f2;f2=e2;e2=a;a=(t1+t2)|0;}
      H[0]=(H[0]+a)|0;H[1]=(H[1]+e2)|0;H[2]=(H[2]+f2)|0;H[3]=(H[3]+g2)|0;H[4]=(H[4]+h2)|0;H[5]=(H[5]+x)|0;H[6]=(H[6]+y)|0;H[7]=(H[7]+z)|0;
    }
    var o="";for(i=0;i<8;i++)o+=("00000000"+(H[i]>>>0).toString(16)).slice(-8);return o;
  }
  function solvePowAsync(cb){
    if(!powDiff){cb("");return;}
    var body = sha256hex.toString() +
      ";self.onmessage=function(e){var s=e.data.s,d=e.data.d,t='';for(var k=0;k<d;k++)t+='0';" +
      "var n=0;while(n<50000000){if(sha256hex(s+':'+n).slice(0,d)===t){self.postMessage({n:''+n});return;}" +
      "n++;if((n%25000)===0)self.postMessage({p:n});}self.postMessage({n:''+n});};";
    try{
      var w = new Worker(URL.createObjectURL(new Blob([body],{type:"text/javascript"})));
      var finished = false;
      w.onmessage = function(ev){
        if(ev.data && ev.data.p){ showProgress(ev.data.p); return; }
        if(finished) return;
        finished = true;
        w.terminate();
        cb(ev.data && ev.data.n ? ev.data.n : "");
      };
      w.onerror = function(){ if(!finished){ finished = true; solvePowChunked(cb); } };
      w.postMessage({s:powSeed,d:powDiff});
      return;
    }catch(e){ solvePowChunked(cb); }
  }
  function solvePowChunked(cb){
    var tgt="";for(var k=0;k<powDiff;k++)tgt+="0";
    var n=0;
    (function step(){
      var end = n + 25000;
      while(n < end){
        if(sha256hex(powSeed+":"+n).slice(0,powDiff)===tgt){cb(""+n);return;}
        n++;
      }
      showProgress(n);
      if(n < 50000000) setTimeout(step, 0); else cb(""+n);
    })();
  }
  function showProgress(n){
    var text = "Проверяем браузер: " + Math.round(n/1000) + " тыс. попыток";
    if(progressDetail){
      var pct = Math.min(82,38+Math.floor(Math.log(n+1)/Math.LN10*7));
      progressDetail.textContent = text;
      if(barEl) barEl.style.width = pct + "%";
      if(progressValue) progressValue.textContent = pct + " %";
      if(progressRoot) progressRoot.setAttribute("aria-valuenow",String(pct));
    }else{
      var st = document.getElementById("subtitle");
      if(st) st.textContent = text;
    }
  }
  function submit(){
    solvePowAsync(function(nonce){setStep(2);sendVerify(nonce);});
  }
  function finish(){
    done = true;
    step = 3;
    setStep(step);
    document.body.classList.add("complete");
    swapText(document.getElementById("title"),"Можно продолжать");
    swapText(document.getElementById("subtitle"),"Проверка завершена. Сейчас откроем сайт.");
  }
  function sendVerify(nonce){
    fetch(verifyURL,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({seed:powSeed,nonce:nonce})})
      .then(function(r){if(!r.ok)throw new Error();try{sessionStorage.removeItem("tg_pow_try");}catch(e){}finish();setTimeout(function(){location.replace(next);},650);})
      .catch(function(){
        var t=0;try{t=parseInt(sessionStorage.getItem("tg_pow_try")||"0",10)||0;}catch(e){}
        if(t<2){try{sessionStorage.setItem("tg_pow_try",t+1);}catch(e){}setTimeout(function(){location.reload();},1200);}
        else{location.replace(next);}
      });
  }
  function tick(){
    if(done) return;
    step = 1;
    setStep(step);
    submit();
  }
  setStep(0);
  setTimeout(tick, 350);
})();
