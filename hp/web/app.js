const $=i=>document.getElementById(i),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=d=>new Date(d+'T00:00:00').toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'}),today=()=>new Date().toISOString().slice(0,10);
const CROPS={rice:['🌾','Rice'],chilli:['🌶️','Chilli'],grapes:['🍇','Grapes'],tea:['🍵','Tea']},pc=v=>Math.round(v*100)+'%';
const MEAS={n_lesions:['Spots found',v=>Math.round(v)],burden:['Leaf area with spots',pc],spindle:['Long, thin spots',pc],round:['Round spots',pc],green:['Green leaf area',pc],yellow:['Yellow area',pc],white:['White area',pc],dark:['Dark or grey area',pc]};
const SAMPLES=[['tea_greyblight','tea','Tea','gray blight'],['tea_healthy','tea','Tea','healthy'],['tea_brownblight','tea','Tea','brown blight'],['chilli_powdery','chilli','Chilli','powdery mildew'],['chilli_cercospora','chilli','Chilli','cercospora'],['chilli_nutritional','chilli','Chilli','nutrient deficiency']];
const HINT={chilli_murda:'Murda is a mite, thrips and virus complex. A fungicide does not help. Ask an agriculture officer about controlling mites and thrips.',chilli_nutritional:'This looks like a nutrient problem, not a disease. Do not spray fungicide. Get a leaf or soil test.',tea_helopeltis:'Helopeltis is an insect pest, so a fungicide does not help.',tea_algalspot:'No fungicide on the official list names this problem. Ask a tea extension officer.',tea_redspot:'No fungicide on the official list names this problem. Ask a tea extension officer.',tea_brownblight:'No fungicide on the official list names this problem for tea. Ask a tea extension officer.'};
let tok=localStorage.getItem('hp_token'),demoMode=localStorage.getItem('hp_demo')=='1',META=null,S={crop:'tea',feats:null,answers:{},dx:null,pack:null,logged:0,groups:0,step:1,last:null};
function toast(t){const e=$('toast');e.textContent=t;e.hidden=false;clearTimeout(toast.t);toast.t=setTimeout(()=>e.hidden=true,3500)}
async function api(path,opt={}){const h={...(opt.headers||{})};if(tok)h.Authorization='Bearer '+tok;if(opt.json){h['Content-Type']='application/json';opt.body=JSON.stringify(opt.json)}
 const r=await fetch('/api'+path,{...opt,headers:h});let d={};try{d=await r.json()}catch(e){}
 if(r.status==401&&tok){signOut();throw new Error('Your session ended. Please sign in again.')}if(!r.ok)throw new Error(typeof d.detail=='string'?d.detail:'Something went wrong ('+r.status+')');return d}
function signOut(){tok=null;localStorage.removeItem('hp_token');localStorage.removeItem('hp_demo');demoMode=false;S={crop:'tea',feats:null,answers:{},dx:null,pack:null,logged:0,groups:0,step:1,last:null};view()}
function view(v){const on=!!tok;$('welcome').hidden=on||v=='how';$('app').hidden=!on||v=='how';$('how').hidden=v!='how';$('so').hidden=!on;$('who').textContent=on?(demoMode?'Demo mode':''):'';$('demobar').hidden=!(on&&demoMode);if(on&&v!='how')boot()}
$('nhow').onclick=()=>{$('how').hidden?view('how'):view()};$('so').onclick=signOut;
let mode='in';const setMode=m=>{mode=m;$('tin').classList.toggle('on',m=='in');$('tup').classList.toggle('on',m=='up');$('reg').hidden=m=='in';$('go').textContent=m=='in'?'Sign in':'Create account'};
$('tin').onclick=()=>setMode('in');$('tup').onclick=()=>setMode('up');$('mk').onclick=()=>{signOut();setMode('up')};
async function enter(path,body,demo){try{$('lme').hidden=true;const d=await api(path,{method:'POST',json:body});tok=d.token;demoMode=!!demo;localStorage.setItem('hp_token',tok);localStorage.setItem('hp_demo',demo?'1':'0');view()}catch(e){$('lme').textContent=e.message;$('lme').hidden=false}}
$('go').onclick=()=>mode=='in'?enter('/login',{email:$('em').value,password:$('pw').value}):enter('/register',{email:$('em').value,password:$('pw').value,name:$('nm').value,district:$('di').value});
$('demo').onclick=()=>{const r=crypto.randomUUID().replace(/-/g,'');enter('/register',{email:`demo-${r.slice(0,12)}@demo.local`,password:r,name:'Demo farmer',district:'Demo'},true)};
function step(n){S.step=n;[1,2,3,4].forEach(i=>$('p'+i).hidden=i!=n);renderJourney();if(n==3)prepPlan();if(n==4)passport();window.scrollTo({top:0,behavior:'smooth'})}
function renderJourney(){const L=[['Check the leaf','What is wrong?',!!S.dx],['Check the pack','Is it genuine?',!!S.pack],['Choose the spray','What fits?',S.logged>0||S.groups>0],['Passport','When is it safe?',S.groups>0]];
 $('journey').innerHTML=L.map((l,i)=>`<button data-s="${i+1}" class="${S.step==i+1?'on':''} ${l[2]?'done':''}"><span class="n">${l[2]?'✓':i+1}</span><span><b>${l[0]}</b><small>${l[1]}</small></span></button>`).join('');
 $('journey').querySelectorAll('button').forEach(b=>b.onclick=()=>step(+b.dataset.s))}
async function boot(){if(!META){META=await api('/meta');renderCrops();renderSamples();$('pcrop').innerHTML=META.crops.map(c=>`<option value="${c}">${CROPS[c]?.[1]||c}</option>`).join('');
 $('pcrop').onchange=()=>{fillDis($('pcrop').value)};const d=new Date();$('sd2').value=today();$('hd').value=new Date(d.getTime()+30*864e5).toISOString().slice(0,10);
 if(META.demo)try{const c=await api('/demo-codes');$('democ').hidden=!c.length;$('demol').innerHTML=c.map(x=>`<button class="${x.kind}" data-c="${esc(x.code)}" title="${esc(x.label)}">${esc(x.label)}</button>`).join('');
  $('demol').querySelectorAll('button').forEach(b=>b.onclick=()=>{$('code').value=b.dataset.c;verify()})}catch(e){}}
 try{S.groups=(await api('/passport')).groups.length}catch(e){}pickCrop(S.crop);step(1)}
/* 1 diagnose */
function renderCrops(){$('crops').innerHTML=META.crops.map(c=>`<button data-c="${c}" class="${c==S.crop?'on':''}" aria-pressed="${c==S.crop}"><span>${CROPS[c]?.[0]||''}</span>${CROPS[c]?.[1]||c}</button>`).join('');$('crops').querySelectorAll('button').forEach(b=>b.onclick=()=>pickCrop(b.dataset.c))}
function renderSamples(){$('samples').innerHTML=SAMPLES.map(s=>`<button data-f="${s[0]}" title="${s[2]} leaf. Dataset label: ${s[3]}"><img src="samples/${s[0]}.jpg" alt="${s[2]} leaf sample" loading="lazy"><span>${s[2]}: ${s[3]}</span></button>`).join('');
 $('samples').querySelectorAll('button').forEach(b=>b.onclick=async()=>{const s=SAMPLES.find(x=>x[0]==b.dataset.f);pickCrop(s[1],true);const bl=await (await fetch('samples/'+s[0]+'.jpg')).blob();$('pvimg').src=URL.createObjectURL(bl);dx(bl)})}
function pickCrop(c,keep){S.crop=c;if(!keep){S.feats=null;$('pv').hidden=true;$('img').value=''}S.answers={};S.dx=null;S.last=null;S.more=false;renderCrops();const t=META.photo_model.trained_crops.includes(c);
 $('nomodel').hidden=t;$('nomodel').textContent=`Photo analysis is not available for ${CROPS[c][1].toLowerCase()} yet (no labelled photos). Answer the questions below and we will work from your answers.`;if(!keep)dx();renderJourney()}
async function dx(file){const f=new FormData();f.append('crop',S.crop);f.append('answers',JSON.stringify(S.answers));if(file)f.append('image',file);else if(S.feats)f.append('features',JSON.stringify(S.feats));
 try{const r=await api('/diagnose',{method:'POST',body:f});if(file){S.feats=r.features;$('pv').hidden=false;$('meas').innerHTML=r.features?Object.entries(MEAS).map(([k,[n,fn]])=>`<span class="chip">${n}: <b>${fn(r.features[k])}</b></span>`).join(''):''}renderDx(r)}
 catch(e){$('dx').innerHTML=`<div class="note bad">${esc(e.message)}</div>`}}
function renderDx(r){S.last=r;const v=r.verdict,top=r.posterior[0],healthy=v.id&&v.id.endsWith('healthy');S.dx=v.id&&v.status!='asking'?v.id:null;S.dxName=v.name;
 let h='';if(r.note)h+=`<div class="note bad">${esc(r.note)}</div>`;
 if(v.status=='asking')h+=`<div class="verdict wn"><h3>Not sure yet</h3><p class="sm">Best guess so far: ${esc(top.name)} (${pc(top.p)}). Answer the question below to sharpen it.</p><div class="meter"><b style="width:${pc(top.p)}"></b></div></div>`;
 else if(v.id)h+=`<div class="verdict ${healthy?'ok':'wn'}"><span class="tag ${v.status=='confident'?'ok':'wn'}">${v.status=='confident'?'Confident':'Best guess'}</span><h3>${healthy?'Your leaf looks healthy':'Likely: '+esc(v.name)}</h3><div class="meter"><b style="width:${pc(v.p)}"></b></div><p class="sm">${pc(v.p)} sure, using ${r.photo_used?'your photo and ':''}${r.answered} answer${r.answered==1?'':'s'}.${r.photo_used&&r.photo_only?` The photo alone said ${esc(r.photo_only[0].name)} (${pc(r.photo_only[0].p)}).`:''}</p></div>`;
 else h+=`<div class="verdict bad"><h3>We cannot tell</h3><p class="sm">The evidence does not separate these causes, so we will not guess. Photograph a fresher leaf, or ask your agriculture officer.</p></div>`;
 if(r.next&&(v.status!='confident'||S.more))h+=`<div class="qcard"><h3>${esc(r.next.text)}?</h3><p class="sm mu">We ask this because it removes the most doubt right now.</p><div class="row"><button data-a="1">Yes</button><button data-a="0">No</button><button class="gh" data-a="x">Not sure</button></div></div>`;
 if(r.next&&v.status=='confident'&&!S.more)h+=`<button class="link" id="more">Want to double-check? Answer a few more questions</button>`;
 h+=`<div class="bars">${r.posterior.map(x=>`<div class="br"><span>${esc(x.name)}</span><i><b style="width:${pc(x.p)}"></b></i><span>${pc(x.p)}</span></div>`).join('')}</div>`;
 if(S.dx&&!healthy)h+=`<button class="big" id="nx">Next: find a spray for this →</button>`;else if(healthy)h+=`<div class="note ok">No spray is needed. You can still check a pack or view your passport using the steps above.</div>`;
 h+=`<details><summary>How did we decide?</summary><p>${r.photo_used?'The photo was turned into measurements (number of spots, how long and thin they are, how much of the leaf is green, yellow or dark). A model trained on labelled photos converted those into probabilities. ':'No photo analysis was used. '}Each answer you give then shifts the probabilities. The system is only called "Confident" once the chance passes ${pc(r.accept)} for this crop, a level chosen on held-out photos.</p></details>`;
 $('dx').innerHTML=h;$('dx').querySelectorAll('[data-a]').forEach(b=>b.onclick=()=>{const a=b.dataset.a;S.answers[r.next.question]=a=='x'?null:a=='1';dx()});if($('nx'))$('nx').onclick=()=>step(3);if($('more'))$('more').onclick=()=>{S.more=true;renderDx(S.last)};renderJourney()}
$('img').onchange=e=>{const f=e.target.files[0];if(!f)return;S.answers={};$('pvimg').src=URL.createObjectURL(f);dx(f)};
/* 2 verify */
async function verify(){const code=$('code').value.trim();if(!code){$('vres').innerHTML='<div class="note bad">Type or scan the batch code first.</div>';return}
 try{const r=await api('/verify',{method:'POST',json:{code}});S.pack=r.ok?r:null;if(r.ok)$('code').value=r.code;
  $('vres').innerHTML=`<div class="verdict ${r.ok?'ok':'bad'}"><h3>${r.ok?'✓ ':'✗ '}${esc(r.title)}</h3><p class="sm">${esc(r.text||'')}</p></div><ul class="checks">${(r.checks||[]).map(c=>`<li><span class="${c.ok?'t':'f'}">${c.ok?'✓':'✗'}</span><span>${esc(c.name)}<small>${esc(c.detail)}</small></span></li>`).join('')}</ul>`+
  (r.product?`<div><b>${esc(r.product)}</b><p class="sm mu">Made ${r.mfg?fmt(r.mfg):''} · expires ${r.exp?fmt(r.exp):''}</p></div>`:'')+(r.labels?`<table><tr><th>Registered for</th><th>Dose</th><th>Wait before harvest</th></tr>${r.labels.map(l=>`<tr><td>${CROPS[l.crop]?.[1]||l.crop}</td><td>${esc(l.dose)}</td><td>${l.phi} days</td></tr>`).join('')}</table>`:'')+
  (r.ok?`<button class="big" id="useit">Use this pack: choose the spray →</button>`:`<div class="note bad">Do not spray with this pack until the shop or the company confirms it.</div>`);if($('useit'))$('useit').onclick=()=>step(3);renderJourney()}
 catch(e){$('vres').innerHTML=`<div class="note bad">${esc(e.message)}</div>`}}
$('vb').onclick=verify;$('code').onkeydown=e=>{if(e.key=='Enter')verify()};
$('sc').onclick=async()=>{if(!('BarcodeDetector' in window))return toast('This browser cannot scan QR codes. Please type the code.');
 try{const st=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}}),v=$('vid');v.srcObject=st;v.hidden=false;await v.play();const det=new BarcodeDetector({formats:['qr_code']});
  const loop=async()=>{if(v.hidden)return;const r=await det.detect(v).catch(()=>[]);if(r.length){st.getTracks().forEach(t=>t.stop());v.hidden=true;$('code').value=r[0].rawValue;verify()}else requestAnimationFrame(loop)};loop()}
 catch(e){toast('Camera blocked. Allow camera access (needs HTTPS or localhost), or type the code.')}};
/* 3 plan and log */
function fillDis(crop,sel){$('pdis').innerHTML=Object.entries(META.classes).filter(([k,v])=>v.crop==crop).map(([k,v])=>`<option value="${k}"${k==sel?' selected':''}>${esc(v.name)}</option>`).join('')}
function prepPlan(){$('pcrop').value=S.crop;fillDis(S.crop,S.dx);$('ctx').innerHTML=(S.dx?`Based on your leaf check: <b>${esc(S.dxName)}</b>. `:'Choose the problem yourself, or go back to step 1. ')+(S.pack?`Pack checked: <b>${esc(S.pack.product)}</b>.`:'No pack checked yet (step 2).');if(S.dx)plan()}
async function plan(){const crop=$('pcrop').value,box=$('opts');box.innerHTML='<div class="card">Looking up the official label list...</div>';
 try{const r=await api('/plan',{method:'POST',json:{crop,disease:$('pdis').value,harvest:$('hd').value||null,field:$('field').value}});
  if(r.no_spray){box.innerHTML='<div class="note ok">No spray needed. The leaf looks healthy.</div>';return}
  const ok=r.options.filter(o=>!o.why),no=r.options.filter(o=>o.why);
  if(!r.options.length){box.innerHTML=`<div class="note bad"><b>No product fits.</b> ${esc(HINT[$('pdis').value]||'No fungicide on the official list names this problem on this crop. Ask your agriculture officer.')}</div>`;return}
  const card=o=>{const mine=S.pack&&S.pack.product_code==o.code;return `<div class="opt ${o.recommended?'best':''} ${o.why?'no':''}"><div class="row">${o.recommended?'<span class="tag ok">Best fit</span>':''}${mine?'<span class="tag wn">Your checked pack</span>':''}<h3 class="sp">${esc(o.product)}</h3></div>
   <div class="sm">Dose: <b>${esc(o.dose)}</b> · Mode of action: ${esc(o.moa)}</div>${o.why?`<div class="note">${esc(o.why)}</div>`:`<div><b>Wait ${o.wait} days</b> after spraying. Earliest harvest if you spray today: <b>${fmt(o.earliest)}</b></div>`}<div class="eu ${o.eu.level}">${esc(o.eu.text)}</div>
   ${!o.why?(mine?`<div class="row"><label style="flex:1">I sprayed on<input type="date" class="sdate" value="${today()}" max="${today()}"></label><button data-log="${o.code}">I sprayed this: log it</button></div>`:`<p class="sm mu">To log this spray you first need to check a pack of this product in step 2.</p>`):''}</div>`};
  box.innerHTML=(ok.length?ok.map(card).join(''):'<div class="note bad"><b>None of the listed sprays fits your harvest date.</b> Move the harvest date or ask your agriculture officer.</div>')+(no.length?`<details><summary>Set aside (${no.length})</summary><div class="col" style="margin-top:8px">${no.map(card).join('')}</div></details>`:'');
  box.querySelectorAll('[data-log]').forEach(b=>b.onclick=()=>logSpray(b.closest('.opt').querySelector('.sdate').value,crop))}
 catch(e){box.innerHTML=`<div class="note bad">${esc(e.message)}</div>`}}
async function logSpray(date,crop){if(!S.pack)return toast('Check a pack in step 2 first.');
 try{await api('/sprays',{method:'POST',json:{field:$('field').value,crop:crop||$('pcrop').value,code:S.pack.code,sprayed:date,disease:$('pdis').value}});S.logged++;toast('Spray logged. Your passport is updated.');step(4)}catch(e){toast(e.message)}}
$('pb').onclick=plan;$('log2').onclick=()=>logSpray($('sd2').value);
/* 4 passport */
async function passport(){const box=$('pass');
 try{const r=await api('/passport');S.groups=r.groups.length;renderJourney();
  if(!r.groups.length){box.innerHTML='<div class="card empty"><span style="font-size:2rem">📋</span><b>No sprays logged yet</b><span>Once you log a spray, this page shows the earliest safe harvest date.</span><button id="g1">Start with the leaf check</button></div>';$('g1').onclick=()=>step(1);return}
  box.innerHTML=r.groups.map((g,i)=>`<article class="pass ${g.hold_days?'hold':''}" id="pp${i}"><div class="row"><div class="sp"><h3>${esc(g.field)} · ${CROPS[g.crop]?.[1]||g.crop}</h3><p class="sm mu">Earliest safe harvest</p></div><div class="badge">${g.hold_days?'WAIT '+g.hold_days+' MORE DAY'+(g.hold_days==1?'':'S'):'CLEAR TO HARVEST'}</div></div>
   <div class="bigdate">${fmt(g.clear)}</div><ul class="tl">${g.sprays.map(s=>`<li><b>${fmt(s.date)}: ${esc(s.product)}</b><span class="sm mu">Dose ${esc(s.dose)} · wait ${s.wait} days · batch ${esc(s.batch)}</span><span class="eu ${s.eu.level}">${esc(s.eu.text)}</span><span><button class="link" data-rm="${s.id}">Remove this entry</button></span></li>`).join('')}</ul>
   ${g.export_warning?'<div class="note">Selling abroad? At least one spray has a strict or unknown EU residue limit. India\'s waiting period alone may not be enough. Get a lab residue test.</div>':''}
   <div class="row"><button data-sh="${i}">Create a link for my buyer</button><button class="gh" data-pr="${i}">Print or save as PDF</button></div><div id="sh${i}"></div></article>`).join('');
  box.querySelectorAll('[data-rm]').forEach(b=>b.onclick=async()=>{await api('/sprays/'+b.dataset.rm,{method:'DELETE'});passport()});
  box.querySelectorAll('[data-pr]').forEach(b=>b.onclick=()=>{const a=$('pp'+b.dataset.pr);a.classList.add('printing');window.print();a.classList.remove('printing')});
  box.querySelectorAll('[data-sh]').forEach(b=>b.onclick=async()=>{const g=r.groups[+b.dataset.sh],d=await api('/passport/share',{method:'POST',json:{field:g.field,crop:g.crop}}),u=location.origin+d.url;
   $('sh'+b.dataset.sh).innerHTML=`<div class="note ok col"><span>Send this link. The buyer sees your passport and whether it has been altered:</span><a href="${d.url}" target="_blank" rel="noopener">${esc(u)}</a><img alt="QR code for the passport link" width="130" height="130" src="/api/qr.png?text=${encodeURIComponent(u)}"></div>`})}
 catch(e){box.innerHTML=`<div class="note bad">${esc(e.message)}</div>`}}
setMode('in');view();
