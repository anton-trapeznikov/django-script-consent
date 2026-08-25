/**
 * Cookie consent banner — works without customization.
 * Optional callbacks:
 *   window.ScriptConsent = {
 *     onAccept, onRejectOptional, onCustom, onDismiss, onWithdraw
 *   }
 */
(function () {
  "use strict";

  var ROOT_ID = "script-consent-banner";
  var LAUNCHER_ID = "script-consent-launcher";

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match) {
      return decodeURIComponent(match[1]);
    }
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function getRoot() {
    return document.getElementById(ROOT_ID);
  }

  function getLauncher() {
    return document.getElementById(LAUNCHER_ID);
  }

  function callHook(name, arg) {
    var api = window.ScriptConsent || {};
    if (typeof api[name] === "function") {
      try {
        api[name](arg);
      } catch (e) {
        if (typeof console !== "undefined" && console.error) {
          console.error("ScriptConsent." + name + " error", e);
        }
      }
    }
  }

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
        Accept: "application/json",
      },
      body: body ? JSON.stringify(body) : "{}",
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok || !data.ok) {
          var err = new Error((data && data.error) || "request_failed");
          err.data = data;
          throw err;
        }
        return data;
      });
    });
  }

  function selectedCategories(root) {
    var boxes = root.querySelectorAll('input[name="cc-category"]');
    var codes = [];
    boxes.forEach(function (el) {
      if (el.checked || el.disabled) {
        codes.push(el.value);
      }
    });
    return codes;
  }

  function setBusy(root, busy) {
    root.querySelectorAll("button").forEach(function (btn) {
      btn.disabled = !!busy;
    });
    var launcher = getLauncher();
    if (launcher) {
      launcher.disabled = !!busy;
    }
  }

  function prefersReducedMotion() {
    return (
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function attentionEnabled() {
    if (prefersReducedMotion()) {
      return false;
    }
    var launcher = getLauncher();
    if (!launcher) {
      return false;
    }
    var raw = window
      .getComputedStyle(launcher)
      .getPropertyValue("--cc-launcher-attention")
      .trim();
    // default on; "0" / "none" / "false" disable
    return raw !== "0" && raw !== "none" && raw !== "false";
  }

  function clearLauncherAttention(launcher) {
    if (!launcher) {
      return;
    }
    launcher.classList.remove("cc-launcher--attention");
    if (launcher._ccAttentionTimer) {
      clearTimeout(launcher._ccAttentionTimer);
      launcher._ccAttentionTimer = null;
    }
  }

  function playLauncherAttention(launcher) {
    if (!launcher || !attentionEnabled()) {
      return;
    }
    clearLauncherAttention(launcher);
    // reflow so re-adding the class restarts the animation
    void launcher.offsetWidth;
    launcher.classList.add("cc-launcher--attention");
    var durationMs = 1200;
    var raw = window
      .getComputedStyle(launcher)
      .getPropertyValue("--cc-launcher-attention-duration")
      .trim();
    if (raw) {
      var n = parseFloat(raw);
      if (!isNaN(n)) {
        durationMs = raw.indexOf("ms") !== -1 ? n : n * 1000;
      }
    }
    launcher._ccAttentionTimer = setTimeout(function () {
      launcher.classList.remove("cc-launcher--attention");
      launcher._ccAttentionTimer = null;
    }, durationMs + 50);
  }

  function showLauncher(opts) {
    opts = opts || {};
    var launcher = getLauncher();
    if (launcher) {
      launcher.hidden = false;
      launcher.disabled = false;
      launcher.removeAttribute("aria-hidden");
      if (opts.attention) {
        playLauncherAttention(launcher);
      }
    }
  }

  function hideLauncher() {
    var launcher = getLauncher();
    if (launcher) {
      clearLauncherAttention(launcher);
      launcher.hidden = true;
      launcher.setAttribute("aria-hidden", "true");
    }
  }

  function hide(root, opts) {
    opts = opts || {};
    // Clear busy so banner buttons and launcher work on next open
    setBusy(root, false);
    root.hidden = true;
    root.setAttribute("aria-hidden", "true");
    root.dataset.manualOpen = "";
    // Hint after close/dismiss; skip if page is about to reload (accept)
    var attention = opts.attention !== false && opts.reloading !== true;
    showLauncher({ attention: attention });
  }

  function show(root, opts) {
    opts = opts || {};
    setBusy(root, false);
    root.hidden = false;
    root.removeAttribute("aria-hidden");
    if (opts.manual) {
      root.dataset.manualOpen = "1";
    }
    hideLauncher();
    var closeBtn = root.querySelector(".cc-banner__close");
    if (closeBtn) {
      closeBtn.focus();
    }
  }

  function handleAccept(root, action) {
    var url = root.getAttribute("data-accept-url");
    var categories = selectedCategories(root);
    var body = { action: action, categories: categories };
    setBusy(root, true);
    return postJson(url, body)
      .then(function (data) {
        if (action === "accept_all") {
          callHook("onAccept", data.categories || categories);
        } else if (action === "reject_optional" || action === "only_required") {
          callHook("onRejectOptional", data.categories || categories);
        } else {
          callHook("onCustom", data.categories || categories);
        }
        var willReload = data.reload !== false;
        hide(root, { reloading: willReload });
        if (willReload) {
          window.location.reload();
        }
      })
      .catch(function (err) {
        setBusy(root, false);
        if (typeof console !== "undefined" && console.error) {
          console.error("Cookie consent accept failed", err);
        }
      });
  }

  function recordImpression(root) {
    var url = root.getAttribute("data-impression-url");
    if (!url) {
      return;
    }
    postJson(url, {}).catch(function (err) {
      if (typeof console !== "undefined" && console.error) {
        console.error("Cookie consent impression failed", err);
      }
    });
  }

  function handleDismiss(root) {
    var url = root.getAttribute("data-dismiss-url");
    setBusy(root, true);
    return postJson(url, {})
      .then(function () {
        callHook("onDismiss");
        hide(root); // setBusy(false) inside hide
      })
      .catch(function (err) {
        setBusy(root, false);
        if (typeof console !== "undefined" && console.error) {
          console.error("Cookie consent dismiss failed", err);
        }
      });
  }

  /**
   * Close control: if banner was auto-opened (first visit), treat as dismiss.
   * If user opened it via the floating button, just hide the UI.
   */
  function handleClose(root) {
    var auto = root.getAttribute("data-auto-open") === "1";
    var manual = root.dataset.manualOpen === "1";
    if (auto && !manual) {
      handleDismiss(root);
    } else {
      hide(root);
    }
  }

  function handleWithdraw() {
    var root = getRoot();
    var url =
      (root && root.getAttribute("data-withdraw-url")) ||
      "/script-consent/withdraw/";
    return postJson(url, {})
      .then(function (data) {
        callHook("onWithdraw");
        if (data.reload !== false) {
          window.location.reload();
        }
      })
      .catch(function (err) {
        if (typeof console !== "undefined" && console.error) {
          console.error("Cookie consent withdraw failed", err);
        }
      });
  }

  function bind(root) {
    root.addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-cc-action]");
      if (!btn || !root.contains(btn)) {
        return;
      }
      var action = btn.getAttribute("data-cc-action");
      if (action === "close" || action === "dismiss") {
        handleClose(root);
      } else if (
        action === "accept_all" ||
        action === "reject_optional" ||
        action === "custom"
      ) {
        handleAccept(root, action);
      }
    });

    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && root && !root.hidden) {
        handleClose(root);
      }
    });

    var launcher = getLauncher();
    if (launcher) {
      launcher.addEventListener("click", function () {
        show(root, { manual: true });
      });
    }
  }

  function exposeApi(root) {
    var publicApi = window.ScriptConsent || {};
    publicApi.withdraw = handleWithdraw;
    publicApi.open = function () {
      var el = root || getRoot();
      if (el) {
        show(el, { manual: true });
      }
    };
    publicApi.close = function () {
      var el = root || getRoot();
      if (el && !el.hidden) {
        handleClose(el);
      }
    };
    window.ScriptConsent = publicApi;
  }

  function init() {
    var root = getRoot();
    if (!root) {
      exposeApi(null);
      return;
    }
    bind(root);
    if (root.getAttribute("data-auto-open") === "1") {
      show(root, { manual: false });
      recordImpression(root);
    } else {
      showLauncher();
    }
    exposeApi(root);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
