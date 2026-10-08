/* SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
   Tastatur på skjermen (norsk, med æøå) for PC-en i maskina, der det ikkje er tastatur.

   - Kjem opp når ein trykkjer på eit skrivefelt med fingeren (AUTO), alltid (ALLTID) eller aldri (AV).
     I AUTO forsvinn det når ein trykkjer på ein ekte tast, og kjem att ved neste trykk med fingeren.
   - Talfelt får eit talpanel, tekstfelt eit norsk tastatur. Passord blir vist som prikkar.
   - Legg seg på motsett side av feltet (felt nede → tastatur oppe), viser kva felt og kva som er skrive,
     er halvgjennomsiktig og kan dragast. Windows sitt eige tastatur blir halde unna (inputmode="none").
   - Endringar sender «input», og «change» når ein trykkjer OK, lukkar eller går til eit anna felt –
     slik at skjemaa i SNOWMAN lagrar som før. Innstillinga ligg i førarskjermen (Innst. › System).
*/
(function () {
  const TEXT_TYPES = ["text", "password", "search", "url", "email", "tel", "number", ""];
  let mode = "auto",
    lastPointer = "mouse",
    el = null, // feltet vi skriv i
    buf = "", // talfelt: det som er skrive (kan vere «-» eller «0,» som enno ikkje er eit tal)
    shift = false,
    caps = false,
    kb = null,
    moved = null; // plassering etter at føraren har dratt tastaturet
  try {
    mode = localStorage.getItem("snowman_kb") || "auto";
  } catch (e) {}

  const css = `
  #skb{position:fixed;left:50%;transform:translateX(-50%);z-index:100000;width:min(1000px,calc(100vw - 12px));
    background:rgba(2,18,27,.80);backdrop-filter:blur(3px);border:1px solid #3d5c6e;border-radius:14px;padding:8px;
    box-shadow:0 8px 30px #000a;font-family:system-ui,Arial,sans-serif;user-select:none;-webkit-user-select:none;touch-action:none}
  #skb.hide{display:none}
  #skb .bar{display:flex;align-items:center;gap:8px;margin:0 2px 8px;cursor:move}
  #skb .lbl{color:#9ab3c1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:40%}
  #skb .val{flex:1;min-height:38px;background:#0d2531e6;border:1px solid #4db8ff;border-radius:8px;color:#fff;font-size:22px;
    font-weight:700;padding:4px 10px;display:flex;align-items:center;overflow:hidden;white-space:pre}
  #skb .val:after{content:"";width:2px;height:24px;background:#4db8ff;margin-left:2px;animation:skbb 1s steps(1) infinite}
  @keyframes skbb{50%{opacity:0}}
  #skb .x{width:46px;height:40px;border:0;border-radius:8px;background:#5a2a2a;color:#fff;font-size:20px}
  #skb .rows{display:flex;flex-direction:column;gap:6px}
  #skb .r{display:flex;gap:6px;justify-content:center}
  #skb .k{flex:1 1 0;min-width:0;height:54px;border:1px solid #3d5c6e;border-radius:9px;background:rgba(23,53,69,.95);color:#fff;
    font-size:22px;font-weight:700;padding:0}
  #skb .k:active,#skb .k.dn{background:#1687bd}
  #skb .k.w15{flex-grow:1.5}#skb .k.w2{flex-grow:2}#skb .k.w5{flex-grow:5}
  #skb .k.on{background:#0878df}
  #skb .k.ok{background:#1f8a4c}
  #skb.num{width:min(420px,calc(100vw - 12px))}
  #skb.num .k{height:62px;font-size:26px}`;

  function build() {
    if (kb) return;
    let st = document.createElement("style");
    st.textContent = css;
    document.head.appendChild(st);
    kb = document.createElement("div");
    kb.id = "skb";
    kb.className = "hide";
    kb.innerHTML = '<div class="bar"><span class="lbl"></span><span class="val"></span><button class="x" data-k="close" title="Lukk">✕</button></div><div class="rows"></div>';
    document.body.appendChild(kb);
    // Tastane skal ikkje ta fokus frå feltet
    kb.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      let b = e.target.closest("[data-k]");
      if (b) {
        b.classList.add("dn");
        setTimeout(() => b.classList.remove("dn"), 120);
        press(b.dataset.k);
      } else if (e.target.closest(".bar")) drag(e);
    });
    kb.addEventListener("mousedown", (e) => e.preventDefault());
  }
  function drag(e) {
    let r = kb.getBoundingClientRect(),
      dx = e.clientX - r.left,
      dy = e.clientY - r.top;
    const mv = (ev) => {
      moved = { x: Math.max(0, Math.min(innerWidth - r.width, ev.clientX - dx)), y: Math.max(0, Math.min(innerHeight - r.height, ev.clientY - dy)) };
      place();
    };
    const up = () => {
      removeEventListener("pointermove", mv);
      removeEventListener("pointerup", up);
    };
    addEventListener("pointermove", mv);
    addEventListener("pointerup", up);
  }

  // Talfelt: type=number (verdien blir halden i buf) – eller tekst/passord med inputmode="numeric" (t.d. PIN)
  const isNum = () => el && el.type === "number";
  const numPad = () => el && (el.type === "number" || (el.dataset.skbIm || el.getAttribute("inputmode")) === "numeric");
  function layout() {
    let rows;
    if (isNum())
      rows = [
        ["1", "2", "3", "⌫:back"],
        ["4", "5", "6", "−:-"],
        ["7", "8", "9", ",:."],
        ["C:clear", "0", "OK:ok"],
      ];
    else if (numPad())
      rows = [
        ["1", "2", "3"],
        ["4", "5", "6"],
        ["7", "8", "9"],
        ["⌫:back", "0", "OK:ok"],
      ];
    else {
      let up = shift || caps,
        L = (s) => s.split("").map((c) => (up ? c.toUpperCase() : c));
      rows = [
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "⌫:back"],
        L("qwertyuiopå"),
        L("asdfghjkløæ"),
        ["⇧:shift", ...L("zxcvbnm"), ",", ".", "-"],
        ["@", "_", "/", ":", "MELLOMROM:space", "←:left", "→:right", "OK:ok"],
      ];
    }
    kb.classList.toggle("num", numPad());
    kb.querySelector(".rows").innerHTML = rows
      .map(
        (r) =>
          '<div class="r">' +
          r
            .map((k) => {
              let [lab, code] = k.includes(":") && k.length > 1 ? k.split(/:(.*)/s) : [k, k],
                cls = "k" + (code === "space" ? " w5" : code === "ok" || code === "back" || code === "shift" ? " w15" : "") + (code === "ok" ? " ok" : "") + (code === "shift" && (shift || caps) ? " on" : "");
              return '<button class="' + cls + '" data-k="' + code.replace(/"/g, "&quot;") + '">' + (code === "shift" && caps ? "⇪" : lab) + "</button>";
            })
            .join("") +
          "</div>",
      )
      .join("");
  }
  function label(e) {
    let t = "";
    if (e.id) {
      let l = document.querySelector('label[for="' + e.id + '"]');
      if (l) t = l.textContent;
    }
    if (!t) {
      let row = e.closest(".row, .rowWide");
      if (row) t = (row.querySelector("span, div") || {}).textContent || "";
    }
    if (!t && e.previousElementSibling && e.previousElementSibling.tagName === "LABEL") t = e.previousElementSibling.textContent;
    if (!t && e.parentElement && e.parentElement.previousElementSibling && e.parentElement.previousElementSibling.tagName === "LABEL") t = e.parentElement.previousElementSibling.textContent;
    return (t || e.placeholder || e.name || "").trim();
  }
  function show(e) {
    build();
    if (el && el !== e) commit();
    el = e;
    buf = isNum() ? String(e.value) : "";
    if (!e.dataset.skbIm) e.dataset.skbIm = e.getAttribute("inputmode") || "-";
    e.setAttribute("inputmode", "none"); // Windows sitt eige tastatur skal ikkje kome i tillegg
    shift = false;
    layout();
    kb.querySelector(".lbl").textContent = label(e);
    kb.classList.remove("hide");
    preview();
    place();
  }
  function place() {
    if (!kb || kb.classList.contains("hide")) return;
    if (moved) {
      kb.style.left = moved.x + "px";
      kb.style.top = moved.y + "px";
      kb.style.bottom = "auto";
      kb.style.transform = "none";
      return;
    }
    kb.style.left = "50%";
    kb.style.transform = "translateX(-50%)";
    let r = el ? el.getBoundingClientRect() : { top: 0, bottom: 0 },
      low = (r.top + r.bottom) / 2 > innerHeight / 2; // feltet nede → tastaturet oppe
    if (low) {
      kb.style.top = "6px";
      kb.style.bottom = "auto";
    } else {
      kb.style.top = "auto";
      kb.style.bottom = "6px";
    }
  }
  function hide() {
    if (!kb) return;
    commit();
    kb.classList.add("hide");
    if (el && el.dataset.skbIm) {
      if (el.dataset.skbIm === "-") el.removeAttribute("inputmode");
      else el.setAttribute("inputmode", el.dataset.skbIm);
      delete el.dataset.skbIm;
    }
    el = null;
  }
  function commit() {
    if (!el) return;
    if (isNum()) {
      let v = parseFloat(buf.replace(",", "."));
      el.value = buf === "" ? "" : isNaN(v) ? el.value : String(v);
    }
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }
  function preview() {
    if (!kb || !el) return;
    let v = isNum() ? buf.replace(".", ",") : el.value;
    kb.querySelector(".val").textContent = el.type === "password" ? "•".repeat(v.length) : v;
  }
  function fire() {
    el.dispatchEvent(new Event("input", { bubbles: true }));
    preview();
  }
  function insert(s) {
    if (isNum()) {
      if (s === "-") buf = buf.startsWith("-") ? buf.slice(1) : "-" + buf;
      else if (s === ".") {
        if (!buf.includes(".")) buf += buf === "" || buf === "-" ? "0." : ".";
      } else buf += s;
      let v = parseFloat(buf);
      if (/^-?\d+(\.\d+)?$/.test(buf) && !isNaN(v)) el.value = String(v);
      fire();
      return;
    }
    let a = el.selectionStart ?? el.value.length,
      b = el.selectionEnd ?? el.value.length,
      max = el.maxLength > 0 ? el.maxLength : 1e9;
    if (el.value.length - (b - a) + s.length > max) return;
    el.setRangeText(s, a, b, "end");
    fire();
  }
  function press(k) {
    if (!el) return;
    switch (k) {
      case "close":
      case "ok":
        let e = el;
        if (k === "ok") e.dispatchEvent(new Event("skbok")); // OK på skjermtastaturet (t.d. i spørjeboksen)
        hide();
        e.blur();
        return;
      case "back":
        if (isNum()) {
          buf = buf.slice(0, -1);
          let v = parseFloat(buf);
          if (/^-?\d+(\.\d+)?$/.test(buf)) el.value = String(v);
          else if (buf === "") el.value = "";
          fire();
        } else {
          let a = el.selectionStart ?? el.value.length,
            b = el.selectionEnd ?? el.value.length;
          if (a === b && a > 0) a--;
          el.setRangeText("", a, b, "end");
          fire();
        }
        return;
      case "clear":
        if (!isNum()) {
          el.value = "";
          fire();
          return;
        }
        buf = "";
        el.value = "";
        fire();
        return;
      case "shift":
        if (shift) {
          caps = !caps;
          shift = false;
        } else if (caps) caps = false;
        else shift = true;
        layout();
        return;
      case "space":
        insert(" ");
        return;
      case "left":
      case "right":
        if (!isNum()) {
          let p = Math.max(0, Math.min(el.value.length, (el.selectionStart ?? el.value.length) + (k === "left" ? -1 : 1)));
          el.setSelectionRange(p, p);
        }
        return;
      default:
        insert(k);
        if (shift) {
          shift = false;
          layout();
        }
    }
  }

  const wants = (e) =>
    e &&
    ((e.tagName === "INPUT" && TEXT_TYPES.includes((e.getAttribute("type") || "").toLowerCase()) && !e.readOnly && !e.disabled) ||
      (e.tagName === "TEXTAREA" && !e.readOnly && !e.disabled));
  document.addEventListener("pointerdown", (e) => (lastPointer = e.pointerType || "mouse"), true);
  document.addEventListener(
    "keydown",
    (e) => {
      if (e.isTrusted) {
        if (mode === "auto" && kb && !kb.classList.contains("hide")) hide();
      }
    },
    true,
  );
  document.addEventListener("focusin", (e) => {
    let t = e.target;
    if (!wants(t)) return;
    // Kvart trykk med fingeren opnar tastaturet igjen – også etter at eit ekte tastatur har vore brukt
    // (tastaturet på Surface kan vere kopla til og frå)
    let on = mode === "alltid" || (mode === "auto" && lastPointer === "touch");
    if (on) show(t);
  });
  // Trykk med fingeren i feltet som alt har fokus (då kjem ikkje «focusin»): opne tastaturet igjen
  document.addEventListener(
    "pointerup",
    (e) => {
      if (mode === "av" || e.pointerType !== "touch") return;
      let t = e.target;
      if (wants(t) && document.activeElement === t && (!kb || kb.classList.contains("hide") || el !== t)) show(t);
    },
    true,
  );
  document.addEventListener("focusout", (e) => {
    if (e.target !== el) return;
    setTimeout(() => {
      if (el && document.activeElement !== el && !wants(document.activeElement)) hide();
    }, 0);
  });
  addEventListener("resize", place);
  addEventListener("scroll", place, true);

  // Eigen spørjeboks i staden for prompt() – prompt() kan ikkje brukast utan tastatur (t.d. PIN i kioskmodus)
  function ask(title, opt) {
    opt = opt || {};
    return new Promise((res) => {
      let bg = document.createElement("div");
      bg.style.cssText = "position:fixed;inset:0;z-index:99999;background:#000a;display:flex;align-items:flex-start;justify-content:center;padding-top:12vh";
      bg.innerHTML =
        '<div style="background:#0b202b;border:1px solid #3d5c6e;border-radius:14px;padding:18px;min-width:min(420px,92vw);color:#fff;font:16px system-ui,Arial">' +
        '<div class="skbT" style="font-weight:800;margin-bottom:10px"></div><input style="width:100%;box-sizing:border-box;font-size:22px;padding:10px;background:#102b39;color:#fff;border:1px solid #4db8ff;border-radius:8px">' +
        '<div style="display:flex;gap:8px;margin-top:12px"><button data-a="0" style="flex:1;padding:12px;border:0;border-radius:8px;background:#2e4b5c;color:#fff;font-weight:800">AVBRYT</button>' +
        '<button data-a="1" style="flex:1;padding:12px;border:0;border-radius:8px;background:#1f8a4c;color:#fff;font-weight:800">OK</button></div></div>';
      bg.querySelector(".skbT").textContent = title;
      let inp = bg.querySelector("input");
      inp.type = opt.password ? "password" : "text";
      if (opt.numeric) inp.setAttribute("inputmode", "numeric");
      document.body.appendChild(bg);
      let done = (v) => {
        if (el === inp) hide();
        bg.remove();
        res(v);
      };
      bg.querySelector('[data-a="0"]').onclick = () => done(null);
      bg.querySelector('[data-a="1"]').onclick = () => done(inp.value);
      inp.addEventListener("keydown", (e) => e.key === "Enter" && done(inp.value));
      inp.addEventListener("skbok", () => setTimeout(() => done(inp.value), 0)); // OK på skjermtastaturet
      inp.focus();
      if (mode === "alltid" || (mode === "auto" && lastPointer === "touch")) show(inp);
    });
  }

  window.SKB = {
    ask,
    setMode(m) {
      mode = ["auto", "alltid", "av"].includes(m) ? m : "auto";
      try {
        localStorage.setItem("snowman_kb", mode);
      } catch (e) {}
      if (mode === "av") hide();
    },
    mode: () => mode,
    show,
    hide,
  };
  // Same innstilling på alle sidene (førarskjermen lagrar ho i tenesta)
  fetch("/api/ui-config")
    .then((r) => r.json())
    .then((d) => {
      let c = (d && (d.cfg || d.config || d)) || {};
      if (c.kbMode) window.SKB.setMode(c.kbMode);
    })
    .catch(() => {});
})();
