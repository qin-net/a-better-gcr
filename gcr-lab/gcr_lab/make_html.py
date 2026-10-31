"""Generate out/lab.html: a standalone step-through of the decoding traces.

Usage: python3 -m gcr_lab.make_html
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")

TEMPLATE = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>GCR Lab — 图约束解码，一步一看</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{
  color-scheme:light;
  --surface-0:#f5f5f2; --surface-1:#fcfcfb; --surface-2:#eeede8;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#7a7974;
  --line:#dcdad2;
  --ok:#1baf7a; --ok-ink:#0d6b4a; --bad:#e34948; --bad-ink:#a12626;
  --accent:#2a78d6; --accent-ink:#1c5cab; --warn:#eda100;
}
@media (prefers-color-scheme:dark){
  :root:where(:not([data-theme="light"])){ color-scheme:dark;
    --surface-0:#111110; --surface-1:#1a1a19; --surface-2:#242422;
    --text-primary:#f0efec; --text-secondary:#c3c2b7; --text-muted:#8d8c84;
    --line:#33332f;
    --ok:#199e70; --ok-ink:#5fd1a8; --bad:#e66767; --bad-ink:#f09a9a;
    --accent:#3987e5; --accent-ink:#8fbdf3; --warn:#c98500;
  }
}
:root[data-theme="dark"]{ color-scheme:dark;
  --surface-0:#111110; --surface-1:#1a1a19; --surface-2:#242422;
  --text-primary:#f0efec; --text-secondary:#c3c2b7; --text-muted:#8d8c84;
  --line:#33332f;
  --ok:#199e70; --ok-ink:#5fd1a8; --bad:#e66767; --bad-ink:#f09a9a;
  --accent:#3987e5; --accent-ink:#8fbdf3; --warn:#c98500;
}
*{box-sizing:border-box}
body{margin:0;background:var(--surface-0);color:var(--text-primary);
  font:15px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--text-secondary);margin:0 0 22px;font-size:14px}
.panel{background:var(--surface-1);border:1px solid var(--line);border-radius:10px;
  padding:16px 18px;margin-bottom:14px}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.seg button{border:0;background:transparent;color:var(--text-secondary);padding:7px 14px;
  font:inherit;font-size:13px;cursor:pointer}
.seg button.on{background:var(--surface-2);color:var(--text-primary);font-weight:600}
.qsel{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.qsel button{border:1px solid var(--line);background:var(--surface-1);color:var(--text-secondary);
  border-radius:999px;padding:6px 14px;font:inherit;font-size:13px;cursor:pointer}
.qsel button.on{border-color:var(--accent);color:var(--accent-ink);background:var(--surface-2)}
.question{font-size:17px;font-weight:600;margin:0}
.tag{display:inline-block;font-size:12px;padding:2px 9px;border-radius:999px;
  border:1px solid var(--line);color:var(--text-secondary)}
.tag.ok{color:var(--ok-ink);border-color:var(--ok)}
.tag.bad{color:var(--bad-ink);border-color:var(--bad)}
.path{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;
  color:var(--text-secondary);word-break:break-word;line-height:1.9}
.path .cur{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px;
  color:var(--text-primary)}
.tokens{display:flex;flex-wrap:wrap;gap:6px;min-height:32px}
.tok{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;
  padding:5px 9px;border-radius:6px;border:1px solid var(--line);
  background:var(--surface-1);color:var(--text-primary)}
.tok.cur{border-color:var(--accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 25%,transparent)}
.tok.special{color:var(--text-muted)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:700px){.grid{grid-template-columns:1fr}}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--text-muted);margin:0 0 10px;font-weight:600}
.cand{display:grid;grid-template-columns:150px 1fr 46px 54px;gap:10px;align-items:center;
  padding:4px 0;font-size:13px}
.cand .name{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cand .bar{height:8px;border-radius:4px;background:var(--surface-2);position:relative;overflow:hidden}
.cand .bar i{position:absolute;left:0;top:0;bottom:0;border-radius:4px}
.cand .sc{text-align:right;color:var(--text-muted);font-variant-numeric:tabular-nums;font-size:12px}
.cand .badge{font-size:11px;color:var(--accent-ink);font-weight:600}
.cand.allowed .bar i{background:var(--accent)}
.cand.masked{opacity:.45}
.cand.masked .bar i{background:var(--bad)}
.cand.chosen .name{font-weight:700}
.empty{color:var(--text-muted);font-size:13px;font-style:italic}
.nav{display:flex;gap:8px;align-items:center;margin-top:14px}
.nav button{border:1px solid var(--line);background:var(--surface-1);color:var(--text-primary);
  border-radius:8px;padding:7px 12px;font:inherit;font-size:13px;cursor:pointer}
.nav button:disabled{opacity:.4;cursor:default}
.nav .stepno{color:var(--text-secondary);font-size:13px;margin-left:auto;font-variant-numeric:tabular-nums}
.note{color:var(--text-secondary);font-size:13px;margin:10px 0 0}
.kbd{font-family:ui-monospace,monospace;font-size:12px;border:1px solid var(--line);
  border-bottom-width:2px;border-radius:4px;padding:0 4px;color:var(--text-secondary)}
footer{margin-top:28px;color:var(--text-muted);font-size:12.5px;line-height:1.7}
</style>
</head>
<body>
<div class="wrap">
  <h1>图约束解码，一步一看</h1>
  <p class="sub">每一步只允许知识图谱词表中合法的下一个 token；蓝色是被放行的候选，红色是被 mask 掉的。
     切换模式可以看同一道题在无约束时的输出。</p>

  <div class="qsel" id="qsel"></div>

  <div class="panel">
    <div class="row" style="margin-bottom:10px">
      <p class="question" id="qtext"></p>
      <span class="tag" id="verdict"></span>
    </div>
    <div class="row" style="margin-bottom:14px">
      <div class="seg" id="modesel">
        <button data-mode="constrained">图约束解码</button>
        <button data-mode="free">自由解码</button>
      </div>
      <span class="tag" id="info"></span>
    </div>
    <div class="path" id="pathline"></div>
  </div>

  <div class="grid">
    <div class="panel">
      <h2>本步合法 token（trie 允许）</h2>
      <div class="tokens" id="allowed"></div>
      <p class="note" id="masknote"></p>
    </div>
    <div class="panel">
      <h2>模型打分 · 前 8</h2>
      <div id="scores"></div>
    </div>
  </div>

  <div class="panel">
    <div class="row">
      <div class="tokens" id="so_far" style="flex:1"></div>
    </div>
    <div class="nav">
      <button id="prev">← 上一步</button>
      <button id="next">下一步 →</button>
      <button id="reset">重来</button>
      <span class="stepno" id="stepno"></span>
    </div>
    <p class="note">键盘 <span class="kbd">←</span> <span class="kbd">→</span> 也可以翻步。</p>
  </div>

  <footer>
    生成自 <code>gcr_lab/</code>：手写知识图谱 + 透明打分表 + 官方同款 <code>get(prefix)</code> 契约。
    打分是人为设定的，目的是让 mask 的机制可见；真实 GCR 用微调后的 Llama/Qwen 输出 logits，
    但每一步的过滤规则完全一样。
  </footer>
</div>

<script>
const DATA = __DATA__;
let qi = 0, mode = "constrained", si = 0;

const $ = id => document.getElementById(id);
const tok = s => s.replace(/^▁/, "");

function cur() { return DATA.questions[qi].runs[mode]; }
function steps() { return cur().steps; }

function renderQsel() {
  $("qsel").innerHTML = "";
  DATA.questions.forEach((q, i) => {
    const b = document.createElement("button");
    b.textContent = tok(q.question).length > 34 ? q.question.slice(0, 34) + "…" : q.question;
    b.className = i === qi ? "on" : "";
    b.onclick = () => { qi = i; si = 0; render(); };
    $("qsel").appendChild(b);
  });
}

function modeButtons() {
  [...$("modesel").children].forEach(b =>
    b.className = b.dataset.mode === mode ? "on" : "");
}

function render() {
  const q = DATA.questions[qi], r = cur(), st = steps()[si];
  const p = new URLSearchParams(location.search);
  p.set("q", qi); p.set("mode", mode); p.set("step", si);
  history.replaceState(null, "", "?" + p.toString());
  renderQsel(); modeButtons();
  $("qtext").textContent = q.question;
  $("verdict").textContent = r.faithful ? "路径全部可在图中核对" : "路径含图中不存在的边";
  $("verdict").className = "tag " + (r.faithful ? "ok" : "bad");
  $("info").textContent =
    (mode === "constrained" ? `路径候选 ${r.n_paths_in_trie} 条` : "无 trie，全词表解码");

  $("pathline").innerHTML = r.ids.map((id, i) => {
    const t = tok(DATA.vocab[id]);
    const special = id === DATA.vocab.indexOf("<PATH>") || id === DATA.vocab.indexOf("</PATH>");
    const future = i > si;
    const cls = (i === si + 1) ? "cur" : "";
    const style = [
      special ? "color:var(--text-muted)" : "",
      future ? "opacity:.18" : "",
    ].join(";");
    return `<span class="${cls}" style="${style}">${t}</span>`;
  }).join(" ");

  const allowed = st.allowed;
  $("allowed").innerHTML = allowed
    ? allowed.map(t => `<span class="tok ${t === st.chosen ? "cur" : ""}">${tok(t)}</span>`).join("")
    : `<span class="empty">未约束（路径外或自由模式），全词表可用</span>`;
  $("masknote").textContent = allowed
    ? `共 ${allowed.length} 个候选；其余 ${DATA.vocab.length - allowed.length} 个 token 概率置零。`
    : "";

  const maxAbs = Math.max(...st.scores.map(s => Math.abs(s.score)), 1);
  $("scores").innerHTML = st.scores.map(s => {
    const isAllowed = !allowed || allowed.includes(s.token);
    const w = Math.max(2, Math.abs(s.score) / maxAbs * 100);
    const cls = ["cand", isAllowed ? "allowed" : "masked",
                 s.token === st.chosen ? "chosen" : ""].join(" ");
    return `<div class="${cls}">
      <span class="name" title="${tok(s.token)}">${tok(s.token)}</span>
      <span class="bar"><i style="width:${w}%"></i></span>
      <span class="sc">${s.score.toFixed(1)}</span>
      <span class="badge">${s.token === st.chosen ? "← 选中" : ""}</span></div>`;
  }).join("");

  $("so_far").innerHTML = st.prefix.map((t, i) =>
    `<span class="tok ${i === st.prefix.length - 1 ? "cur" : ""}">${tok(t)}</span>`).join("");

  $("stepno").textContent = `第 ${si + 1} / ${steps().length} 步`;
  $("prev").disabled = si === 0;
  $("next").disabled = si === steps().length - 1;
}

$("modesel").onclick = e => {
  if (!e.target.dataset.mode) return;
  mode = e.target.dataset.mode; si = 0; render();
};
$("prev").onclick = () => { if (si > 0) { si--; render(); } };
$("next").onclick = () => { if (si < steps().length - 1) { si++; render(); } };
$("reset").onclick = () => { si = 0; render(); };
document.onkeydown = e => {
  if (e.key === "ArrowLeft") $("prev").click();
  if (e.key === "ArrowRight") $("next").click();
};
const params = new URLSearchParams(location.search);
if (params.get("theme")) document.documentElement.dataset.theme = params.get("theme");
qi = Math.min(Math.max(parseInt(params.get("q") || "0", 10) || 0, 0), DATA.questions.length - 1);
mode = params.get("mode") === "free" ? "free" : "constrained";
si = parseInt(params.get("step") || "0", 10) || 0;
si = Math.min(Math.max(si, 0), steps().length - 1);
render();
</script>
</body>
</html>
"""


def main():
    with open(os.path.join(OUT, "traces.json")) as f:
        data = json.load(f)
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    dest = os.path.join(OUT, "lab.html")
    with open(dest, "w") as f:
        f.write(html)
    print("wrote", os.path.abspath(dest))


if __name__ == "__main__":
    main()
