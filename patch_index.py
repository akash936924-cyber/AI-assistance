"""
Usage:  python patch_index.py templates/index.html
Makes a backup (index.html.bak) and applies these upgrades:
  - smart auto-scroll (does not drag you down while you read)
  - smoother streaming (render once per frame)
  - error text is not saved into chat history
  - Retry button after an error / empty stop
  - Study mode dropdown in the header
  - aria-live on the thread
"""
import shutil
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "templates/index.html"
src = open(path, encoding="utf-8").read()
shutil.copyfile(path, path + ".bak")

edits = []


def edit(old, new):
    edits.append((old, new))


# ---------- CSS ----------
edit("#scroll{flex:1;overflow-y:auto;scroll-behavior:smooth}",
     "#scroll{flex:1;overflow-y:auto}")

edit("</style>", """.mode{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:4px 10px;font-size:12.5px;color:var(--dim);outline:0;cursor:pointer;max-width:160px}
.mode:focus-visible{outline:2px solid var(--brass)}
.mode option{background:var(--panel);color:var(--text)}
</style>""")

# ---------- HTML ----------
edit('<div id="thread"></div>', '<div id="thread" aria-live="polite"></div>')

edit('<span class="chip"><span class="dot"></span>',
     '<select class="mode" id="modeSel" aria-label="Study mode"></select>'
     '<span class="chip"><span class="dot"></span>')

# ---------- JS: helpers, modes, throttled paint ----------
edit("function toBottom(){ scroller.scrollTop = scroller.scrollHeight; }", r'''function toBottom(){ scroller.scrollTop = scroller.scrollHeight; }
const nearBottom = () => scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 80;
const ERR_MARK = "\u241eERR\u241e";
let raf = 0, pend = null;
function paint(o, r){
  pend = [o, r];
  if(raf) return;
  raf = requestAnimationFrame(()=>{
    raf = 0; const [o2, r2] = pend;
    const stick = nearBottom();
    o2.innerHTML = md(r2.split(ERR_MARK)[0]);
    if(stick) toBottom();
  });
}

// ---- study modes ----
const MODES = {
  "":       ["Normal", ""],
  teacher:  ["Teacher", "You are a patient teacher for a first-year student. Explain step by step in simple Hinglish (or the user's language) with one small example. End with one quick question to check understanding."],
  quiz:     ["Quiz", "You are a quiz master. When the user gives a topic, ask ONE multiple-choice question (A to D) at a time, in the user's language. Wait for the answer, say if it is right or wrong with a one-line reason, keep a running score, then ask the next question."],
  code:     ["Code reviewer", "You are a careful code reviewer. When the user pastes code, list bugs first, then improvements, then show the corrected code. Keep explanations short and in simple Hinglish or the user's language."],
  email:    ["Email writer", "You write clear, polite, formal emails and letters. Ask for missing details only if essential. Give a subject line and the email body, ready to send."]
};
function syncMode(){
  const sel = $("#modeSel");
  if(!sel.options.length){
    Object.entries(MODES).forEach(([k, v])=>{ const o = document.createElement("option"); o.value = k; o.textContent = v[0] + " mode"; sel.appendChild(o); });
  }
  sel.value = (settings.mode in MODES) ? settings.mode : "";
}
$("#modeSel").onchange = e=>{
  settings.mode = e.target.value; settings.system = MODES[settings.mode][1];
  saveSettings();
};''')

edit("function showModel(){", "function showModel(){ syncMode();")

edit('system:$("#sSys").value.trim()};',
     'system:$("#sSys").value.trim()};\n'
     '  settings.mode = (MODES[settings.mode||""] && MODES[settings.mode||""][1] === settings.system) ? (settings.mode||"") : "";')

# ---------- JS: generate() ----------
edit('let reply = ""; ctrl = new AbortController();',
     'let reply = "", errNote = ""; ctrl = new AbortController();')

edit("for(;;){ const {done,value} = await rd.read(); if(done) break; reply += dec.decode(value,{stream:true}); out.innerHTML = md(reply); toBottom(); }",
     '''for(;;){ const {done,value} = await rd.read(); if(done) break; reply += dec.decode(value,{stream:true}); paint(out, reply); }
      cancelAnimationFrame(raf); raf = 0;
      const k = reply.indexOf(ERR_MARK);
      if(k >= 0){ errNote = reply.slice(k + ERR_MARK.length).trim(); reply = reply.slice(0, k).trim(); }
      out.innerHTML = md(reply);
      if(errNote){ const p = document.createElement("p"); p.className = "err"; p.textContent = errNote; out.appendChild(p); }''')

edit("if(reply){ c.messages.push({role:\"assistant\",content:reply}); m._raw = reply; }",
     'cancelAnimationFrame(raf); raf = 0;\n'
     '  if(reply){ out.innerHTML = md(reply); if(errNote){ const p = document.createElement("p"); p.className = "err"; p.textContent = errNote; out.appendChild(p); } c.messages.push({role:"assistant",content:reply}); m._raw = reply; }\n'
     '  else m._failed = true;')

# ---------- JS: Retry button ----------
edit("    if(!m._raw) return;\n",
     "    const last = i===ais.length-1 && !busy;\n    if(!m._raw && !(last && m._failed)) return;\n")

edit('a.innerHTML = `<button data-act="copy">Copy</button>` + (i===ais.length-1 && !busy ? `<button data-act="regen">Regenerate</button>` : "");',
     'a.innerHTML = m._raw ? `<button data-act="copy">Copy</button>` + (last ? `<button data-act="regen">Regenerate</button>` : "") : `<button data-act="retry">Retry</button>`;')

edit('act.dataset.act==="regen" && !busy',
     '(act.dataset.act==="regen" || act.dataset.act==="retry") && !busy')

for old, new in edits:
    n = src.count(old)
    if n != 1:
        sys.exit(f"STOP: expected 1 match, found {n} for:\n{old[:90]}\n(Backup is at {path}.bak, file not changed.)")
    src = src.replace(old, new)

open(path, "w", encoding="utf-8").write(src)
print("Done. Backup:", path + ".bak")