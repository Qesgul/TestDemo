/**
 * selector_finder 页面注入脚本。
 *
 * 核心能力：
 *   1. 多策略元素信息提取（testId / role+name / label / placeholder / text / css）
 *   2. file input 自动探测（上传按钮通常配一个隐藏 <input type="file">）
 *   3. 动态文本启发式标记（含数字、状态切换词 → ⚠）
 *   4. 人工点选浮窗 + 策略选择面板
 *
 * Playwright 通过 page.add_init_script() 注入。
 * Python 端通过 page.evaluate 轮询 window.__sfPicks / window.__sfDone。
 */
(function () {
  "use strict";

  // 不稳定 ID 过滤
  const UNSTABLE_ID = /^(:r\w+:|[a-z]+-\d{4,}|react-[\w-]+|__\w+)$/i;

  // 动态文本判断：含数字 / 状态切换词
  const DYNAMIC_TEXT_RE = /\d|标准模式|思考模式|已选|未选|已激活|未激活|选中|已开启|已关闭|开启中|关闭中|加载中|loading/i;

  // ── DOM 工具 ─────────────────────────────────────────────────────────

  function isVisible(el) {
    const r = el.getBoundingClientRect();
    if (r.width < 2 && r.height < 2) return false;
    const s = getComputedStyle(el);
    return s.display !== "none" && s.visibility !== "hidden" && s.opacity !== "0";
  }

  function hasDirectText(el) {
    for (const n of el.childNodes) {
      if (n.nodeType === 3 && n.textContent.trim()) return true;
    }
    return false;
  }

  function isMeaningful(el) {
    if (hasDirectText(el)) return true;
    if (el.querySelector("img,video,canvas,svg,button,a,input,select,textarea,iframe")) return true;
    if (el.children.length > 1) return true;
    return false;
  }

  function resolveTarget(el) {
    let cur = el;
    while (cur && cur !== document.body && cur !== document.documentElement) {
      if (cur.closest && cur.closest("#__sf-picker-root")) {
        cur = cur.parentElement;
        continue;
      }
      if (!isVisible(cur)) { cur = cur.parentElement; continue; }
      if (isMeaningful(cur)) return cur;
      cur = cur.parentElement;
    }
    return el;
  }

  function buildSelector(el) {
    if (!el) return null;
    if (el.id && !UNSTABLE_ID.test(el.id)) return "#" + el.id;
    const parts = [];
    let node = el;
    while (node && node !== document.body && node !== document.documentElement) {
      let seg = node.tagName.toLowerCase();
      if (node.id && !UNSTABLE_ID.test(node.id)) {
        parts.unshift("#" + node.id);
        break;
      }
      const p = node.parentElement;
      if (p) {
        const siblings = Array.from(p.children).filter(c => c.tagName === node.tagName);
        if (siblings.length > 1) seg += ":nth-of-type(" + (siblings.indexOf(node) + 1) + ")";
      }
      parts.unshift(seg);
      node = node.parentElement;
    }
    return parts.join(" > ");
  }

  // ── file input 探测 ──────────────────────────────────────────────────

  function findNearbyFileInput(el) {
    if (!el) return null;
    if (el.tagName === "INPUT" && (el.type || "").toLowerCase() === "file") return el;
    const desc = el.querySelector && el.querySelector('input[type="file"]');
    if (desc) return desc;
    let cur = el.parentElement;
    for (let i = 0; i < 5 && cur; i++) {
      const found = cur.querySelector && cur.querySelector('input[type="file"]');
      if (found) return found;
      cur = cur.parentElement;
    }
    return null;
  }

  // ── 多策略信息提取 ───────────────────────────────────────────────────

  const ROLE_MAP = {
    BUTTON: "button", A: "link",
    H1: "heading", H2: "heading", H3: "heading", H4: "heading",
    NAV: "navigation", MAIN: "main", FOOTER: "contentinfo",
    HEADER: "banner", ARTICLE: "article", SECTION: "region",
    UL: "list", OL: "list", LI: "listitem",
    TABLE: "table", TR: "row", TD: "cell", TH: "columnheader",
    SELECT: "combobox", TEXTAREA: "textbox",
  };

  function inferRole(el) {
    const explicit = el.getAttribute("role");
    if (explicit) return explicit;
    if (el.tagName === "INPUT") {
      const t = el.type || "text";
      if (t === "checkbox") return "checkbox";
      if (t === "radio") return "radio";
      if (["button", "submit", "reset"].includes(t)) return "button";
      return "textbox";
    }
    return ROLE_MAP[el.tagName] || null;
  }

  function getLabel(el) {
    if (el.id) {
      const lbl = document.querySelector('label[for="' + el.id + '"]');
      if (lbl) return lbl.textContent.trim();
    }
    const parent = el.closest("label");
    if (parent) return parent.textContent.trim().slice(0, 80);
    const ariaLabelledby = el.getAttribute("aria-labelledby");
    if (ariaLabelledby) {
      const ref = document.getElementById(ariaLabelledby);
      if (ref) return ref.textContent.trim();
    }
    return null;
  }

  function getElementInfo(el) {
    el = resolveTarget(el);

    const testId =
      el.getAttribute("data-testid") ||
      el.getAttribute("data-pw") ||
      el.getAttribute("data-cy") ||
      el.getAttribute("data-test") || null;

    const role = inferRole(el);
    const ariaName =
      el.getAttribute("aria-label") ||
      el.textContent?.trim().slice(0, 80) || null;

    const textContent = el.textContent?.trim().slice(0, 80) || null;

    const fileInput = findNearbyFileInput(el);
    const fileInputCss = fileInput ? buildSelector(fileInput) : null;

    const isDynamic = textContent ? DYNAMIC_TEXT_RE.test(textContent) : false;

    return {
      testId,
      role,
      name: ariaName,
      label: getLabel(el),
      placeholder: el.getAttribute("placeholder") || null,
      text: textContent,
      css: buildSelector(el),
      tag: el.tagName.toLowerCase(),
      fileInputCss,
      isDynamicText: isDynamic,
    };
  }

  // ── 候选策略生成 + 打分 ──────────────────────────────────────────────

  function buildCandidates(info, descCtx) {
    const cs = [];
    const dyn = info.isDynamicText;
    const isUploadCtx = /上传|截图|图片|文件|upload/i.test(descCtx || "");

    if (info.fileInputCss && isUploadCtx) {
      cs.push({ strategy: "file_input", score: 95, label: "⭐ 上传 input",
        detail: info.fileInputCss, spec: { strategy: "css", selector: info.fileInputCss, action: "upload" } });
    }
    if (info.testId) {
      cs.push({ strategy: "test_id", score: 100, label: "✓ testId",
        detail: info.testId, spec: { strategy: "test_id", test_id: info.testId } });
    }
    if (info.role && info.name) {
      const nameDyn = DYNAMIC_TEXT_RE.test(info.name);
      cs.push({ strategy: "role", score: nameDyn ? 30 : 80,
        label: (nameDyn ? "⚠ " : "✓ ") + "role+name",
        detail: info.role + " / " + info.name,
        spec: { strategy: "role", role: info.role, name: info.name, exact: false } });
      cs.push({ strategy: "role_only", score: 50,
        label: "✓ role（不带 name，可能多命中）",
        detail: info.role,
        spec: { strategy: "role", role: info.role, name: null, exact: false } });
    } else if (info.role) {
      cs.push({ strategy: "role_only", score: 50,
        label: "✓ role",
        detail: info.role,
        spec: { strategy: "role", role: info.role, name: null, exact: false } });
    }
    if (info.label) {
      cs.push({ strategy: "label", score: 60, label: "✓ label",
        detail: info.label, spec: { strategy: "label", label: info.label } });
    }
    if (info.placeholder) {
      cs.push({ strategy: "placeholder", score: 60, label: "✓ placeholder",
        detail: info.placeholder, spec: { strategy: "placeholder", placeholder: info.placeholder } });
    }
    if (info.text) {
      cs.push({ strategy: "text", score: dyn ? 0 : 40,
        label: (dyn ? "⚠ " : "") + "text（精确匹配）",
        detail: info.text + (dyn ? "  ← 含动态字符，不推荐" : ""),
        spec: { strategy: "text", text: info.text, exact: true } });
    }
    if (info.css) {
      const pathLen = info.css.split(">").length;
      const cssScore = 25 - Math.min(pathLen, 15);
      cs.push({ strategy: "css", score: cssScore,
        label: "✓ css 结构路径",
        detail: info.css,
        spec: { strategy: "css", selector: info.css } });
    }

    cs.sort((a, b) => b.score - a.score);
    return cs;
  }

  // ── 人工点选浮窗 ─────────────────────────────────────────────────────

  let _pendingItems = [];
  let _currentIndex = 0;
  let _root = null;
  let _overlay = null;
  let _awaitingChoice = false;  // 候选选择面板展示中时不再响应新点击

  function _buildRoot() {
    const root = document.createElement("div");
    root.id = "__sf-picker-root";
    root.style.cssText = [
      "position:fixed", "top:0", "left:0", "right:0", "z-index:2147483647",
      "background:#1e1e2e", "color:#cdd6f4", "font:13px/1.5 monospace",
      "padding:8px 16px", "max-height:60vh", "overflow:auto",
      "box-shadow:0 2px 12px rgba(0,0,0,.6)",
    ].join(";");
    document.body.prepend(root);
    return root;
  }

  function _renderPanel() {
    if (!_root) return;
    _awaitingChoice = false;
    const remaining = _pendingItems.length - _currentIndex;
    const current = _pendingItems[_currentIndex];
    _root.innerHTML =
      '<div style="display:flex;align-items:center;gap:12px">' +
      '<span style="background:#89b4fa;color:#1e1e2e;padding:2px 8px;border-radius:4px;font-weight:bold">元素选择器</span>' +
      '<span>剩余 <b>' + remaining + '</b> 项</span>' +
      '<span style="color:#f9e2af">▶ 请点击：<b>' + (current || "") + '</b></span>' +
      '<button id="__sf-skip" style="margin-left:auto;padding:2px 10px;background:#f38ba8;border:none;border-radius:4px;color:#1e1e2e;cursor:pointer">跳过</button>' +
      '<button id="__sf-done" style="padding:2px 10px;background:#a6e3a1;border:none;border-radius:4px;color:#1e1e2e;cursor:pointer">完成</button>' +
      '</div>';

    document.getElementById("__sf-skip").onclick = () => {
      _currentIndex++;
      if (_currentIndex >= _pendingItems.length) {
        _finish();
      } else {
        _renderPanel();
      }
    };
    document.getElementById("__sf-done").onclick = _finish;
  }

  function _renderChoicePanel(info, candidates) {
    if (!_root) return;
    _awaitingChoice = true;
    const current = _pendingItems[_currentIndex] || "";

    let html =
      '<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">' +
      '<span style="background:#89b4fa;color:#1e1e2e;padding:2px 8px;border-radius:4px;font-weight:bold">选择策略</span>' +
      '<span style="color:#f9e2af">▶ ' + current + '</span>' +
      '<button id="__sf-redo" style="margin-left:auto;padding:2px 10px;background:#fab387;border:none;border-radius:4px;color:#1e1e2e;cursor:pointer">重选元素</button>' +
      '</div>' +
      '<div style="display:grid;grid-template-columns:1fr;gap:4px">';

    candidates.forEach((c, i) => {
      const bg = i === 0 ? "#a6e3a1" : "#45475a";
      const fg = i === 0 ? "#1e1e2e" : "#cdd6f4";
      html +=
        '<button class="__sf-choice" data-idx="' + i + '" ' +
        'style="text-align:left;padding:6px 10px;background:' + bg + ';color:' + fg + ';' +
        'border:none;border-radius:4px;cursor:pointer;font-family:monospace;font-size:12px">' +
        '<b>' + c.label + '</b> [score=' + c.score + ']<br>' +
        '<span style="opacity:.85">' + (c.detail || "") + '</span>' +
        '</button>';
    });
    html += '</div>';
    _root.innerHTML = html;

    document.getElementById("__sf-redo").onclick = _renderPanel;
    _root.querySelectorAll(".__sf-choice").forEach(btn => {
      btn.onclick = () => {
        const idx = parseInt(btn.getAttribute("data-idx"), 10);
        const chosen = candidates[idx];
        const pickInfo = Object.assign({}, info, {
          chosenStrategy: chosen.strategy,
          chosenSpec: chosen.spec,
          elementDesc: _pendingItems[_currentIndex] || "",
        });
        window.__sfPicks.push(pickInfo);
        if (typeof window.__sfOnPick === "function") {
          try { window.__sfOnPick(pickInfo); } catch (e) {}
        }
        _currentIndex++;
        if (_currentIndex >= _pendingItems.length) {
          _finish();
        } else {
          _renderPanel();
        }
      };
    });
  }

  function _finish() {
    window.__sfDone = true;
    if (_overlay) { _overlay.remove(); _overlay = null; }
    if (_root) { _root.remove(); _root = null; }
    document.removeEventListener("click", _handleClick, true);
  }

  window.__sfPicks = [];
  window.__sfDone = false;

  function _handleClick(e) {
    if (_root && _root.contains(e.target)) return;
    if (_awaitingChoice) return;  // 正在等用户选策略，忽略页面点击
    e.preventDefault();
    e.stopPropagation();

    const info = getElementInfo(e.target);
    const candidates = buildCandidates(info, _pendingItems[_currentIndex] || "");
    if (candidates.length === 0) {
      // 极端情况：什么都提不出，仍然 push 原 info 让 Python 端兜底
      info.elementDesc = _pendingItems[_currentIndex] || "";
      window.__sfPicks.push(info);
      _currentIndex++;
      if (_currentIndex >= _pendingItems.length) _finish();
      else _renderPanel();
      return;
    }
    _renderChoicePanel(info, candidates);
  }

  function createPicker(missingDescriptions) {
    _pendingItems = missingDescriptions || [];
    _currentIndex = 0;
    window.__sfPicks = [];
    window.__sfDone = false;

    if (_pendingItems.length === 0) return;

    _root = _buildRoot();
    _renderPanel();

    _overlay = document.createElement("div");
    _overlay.id = "__sf-overlay";
    _overlay.style.cssText =
      "position:fixed;pointer-events:none;border:2px solid #89b4fa;border-radius:3px;z-index:2147483646;transition:all .1s";
    document.body.appendChild(_overlay);

    document.addEventListener("mousemove", (e) => {
      if (!_overlay) return;
      const target = resolveTarget(e.target);
      if (_root && _root.contains(target)) return;
      const r = target.getBoundingClientRect();
      _overlay.style.left = (r.left + window.scrollX) + "px";
      _overlay.style.top = (r.top + window.scrollY) + "px";
      _overlay.style.width = r.width + "px";
      _overlay.style.height = r.height + "px";
    }, true);

    document.addEventListener("click", _handleClick, true);
  }

  window.__selectorFinder = { createPicker, getElementInfo };
})();
