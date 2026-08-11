/**
 * @jest-environment jsdom
 */

// jsdom exposes window.location.reload as read-only, so we do not assert
// that the page reloads. We verify the banner is hidden and that the server
// response flag reload:false keeps the page intact.

const path = require("path");
const bannerScriptPath = path.resolve(__dirname, "banner.js");

function loadBanner() {
    // Load the IIFE in isolation so each test gets a fresh init().
    return jest.isolateModules(() => require(bannerScriptPath));
}

function makeBanner(attrs) {
    attrs = attrs || {};
    var root = document.createElement("div");
    root.id = "script-consent-banner";
    root.hidden = true;
    root.dataset.acceptUrl = attrs.acceptUrl || "/script-consent/accept/";
    root.dataset.dismissUrl = attrs.dismissUrl || "/script-consent/dismiss/";
    root.dataset.withdrawUrl = attrs.withdrawUrl || "/script-consent/withdraw/";
    root.dataset.autoOpen = attrs.autoOpen === undefined ? "1" : attrs.autoOpen;
    root.innerHTML = [
        '<button class="cc-banner__close" data-cc-action="close">Close</button>',
        '<fieldset class="cc-banner__categories">',
        '  <label><input type="checkbox" name="cc-category" value="required" checked disabled> Required</label>',
        '  <label><input type="checkbox" name="cc-category" value="analytics"> Analytics</label>',
        '  <label><input type="checkbox" name="cc-category" value="marketing"> Marketing</label>',
        "</fieldset>",
        '<button data-cc-action="accept_all">Accept all</button>',
        '<button data-cc-action="reject_optional">Only required</button>',
        '<button data-cc-action="custom">Save choice</button>',
        '<button data-cc-action="dismiss">Dismiss</button>',
    ].join("");
    return root;
}

function makeLauncher() {
    var btn = document.createElement("button");
    btn.id = "script-consent-launcher";
    btn.hidden = true;
    return btn;
}

function setupDom(opts) {
    opts = opts || {};
    document.body.innerHTML = "";
    document.head.innerHTML = "";
    // Clear any csrftoken cookie left by a previous test.
    document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
    if (window.ScriptConsent) {
        delete window.ScriptConsent;
    }

    var root = makeBanner(opts.banner || {});
    document.body.appendChild(root);
    var launcher = opts.launcher === false ? null : makeLauncher();
    if (launcher) {
        document.body.appendChild(launcher);
    }
    return { root: root, launcher: launcher };
}

function queryBtn(root, action) {
    return root.querySelector('[data-cc-action="' + action + '"]');
}

function mockFetch(response) {
    global.fetch = jest.fn(() => Promise.resolve(response));
}

function mockOk(data) {
    return {
        ok: true,
        json: () => Promise.resolve(data),
    };
}

function mockError(data, status) {
    return {
        ok: false,
        status: status || 400,
        json: () => Promise.resolve(data),
    };
}

function flushPromises() {
    return new Promise((resolve) => setTimeout(resolve, 10));
}

describe("ScriptConsent banner", function () {
    beforeEach(function () {
        global.fetch = jest.fn();
    });

    afterEach(function () {
        jest.restoreAllMocks();
    });

    test("exposes public API even when banner element is missing", function () {
        document.body.innerHTML = "";
        if (window.ScriptConsent) {
            delete window.ScriptConsent;
        }
        loadBanner();
        expect(window.ScriptConsent).toBeDefined();
        expect(typeof window.ScriptConsent.open).toBe("function");
        expect(typeof window.ScriptConsent.close).toBe("function");
        expect(typeof window.ScriptConsent.withdraw).toBe("function");
    });

    test("auto-opens banner and hides launcher", function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        loadBanner();
        expect(dom.root.hidden).toBe(false);
        expect(dom.launcher.hidden).toBe(true);
    });

    test("does not auto-open banner and shows launcher", function () {
        var dom = setupDom({ banner: { autoOpen: "0" } });
        loadBanner();
        expect(dom.root.hidden).toBe(true);
        expect(dom.launcher.hidden).toBe(false);
    });

    test("launcher click opens banner manually", function () {
        var dom = setupDom({ banner: { autoOpen: "0" } });
        loadBanner();
        dom.launcher.click();
        expect(dom.root.hidden).toBe(false);
        expect(dom.launcher.hidden).toBe(true);
    });

    test("Escape key closes auto-opened banner as dismiss", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        mockFetch(mockOk({ ok: true }));
        loadBanner();
        var event = new KeyboardEvent("keydown", { key: "Escape", bubbles: true });
        document.dispatchEvent(event);
        await flushPromises();
        expect(global.fetch).toHaveBeenCalledWith(
            "/script-consent/dismiss/",
            expect.objectContaining({ method: "POST" })
        );
        expect(dom.root.hidden).toBe(true);
    });

    test("accept_all sends selected categories and hides banner", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        dom.root.querySelectorAll('input[name="cc-category"]').forEach(function (el) {
            el.checked = true;
        });
        mockFetch(mockOk({ ok: true, categories: ["required", "analytics", "marketing"], reload: false }));
        loadBanner();
        queryBtn(dom.root, "accept_all").click();
        await flushPromises();
        expect(global.fetch).toHaveBeenCalledTimes(1);
        var call = global.fetch.mock.calls[0];
        expect(call[0]).toBe("/script-consent/accept/");
        expect(call[1]).toEqual(
            expect.objectContaining({
                method: "POST",
                credentials: "same-origin",
                headers: expect.objectContaining({
                    "Content-Type": "application/json",
                    Accept: "application/json",
                }),
            })
        );
        var body = JSON.parse(call[1].body);
        expect(body.action).toBe("accept_all");
        expect(body.categories).toEqual(["required", "analytics", "marketing"]);
        expect(dom.root.hidden).toBe(true);
    });

    test("reject_optional sends only required categories", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        mockFetch(mockOk({ ok: true, categories: ["required"], reload: false }));
        loadBanner();
        queryBtn(dom.root, "reject_optional").click();
        await flushPromises();
        var body = JSON.parse(global.fetch.mock.calls[0][1].body);
        expect(body.action).toBe("reject_optional");
        expect(body.categories).toEqual(["required"]);
    });

    test("custom sends user-selected categories", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        dom.root.querySelector('input[value="analytics"]').checked = true;
        mockFetch(mockOk({ ok: true, categories: ["required", "analytics"], reload: false }));
        loadBanner();
        queryBtn(dom.root, "custom").click();
        await flushPromises();
        var body = JSON.parse(global.fetch.mock.calls[0][1].body);
        expect(body.action).toBe("custom");
        expect(body.categories).toEqual(["required", "analytics"]);
    });

    test("dismiss button posts to dismiss URL", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        mockFetch(mockOk({ ok: true }));
        loadBanner();
        queryBtn(dom.root, "dismiss").click();
        await flushPromises();
        expect(global.fetch).toHaveBeenCalledWith(
            "/script-consent/dismiss/",
            expect.objectContaining({ method: "POST", body: "{}" })
        );
        expect(dom.root.hidden).toBe(true);
    });

    test("close on auto-opened banner acts as dismiss", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        mockFetch(mockOk({ ok: true }));
        loadBanner();
        queryBtn(dom.root, "close").click();
        await flushPromises();
        expect(global.fetch).toHaveBeenCalledTimes(1);
        expect(dom.root.hidden).toBe(true);
    });

    test("close on manually opened banner hides without posting", function () {
        var dom = setupDom({ banner: { autoOpen: "0" } });
        loadBanner();
        dom.launcher.click();
        queryBtn(dom.root, "close").click();
        expect(global.fetch).not.toHaveBeenCalled();
        expect(dom.root.hidden).toBe(true);
    });

    test("public API open/close work", function () {
        var dom = setupDom({ banner: { autoOpen: "0" } });
        loadBanner();
        window.ScriptConsent.open();
        expect(dom.root.hidden).toBe(false);
        window.ScriptConsent.close();
        expect(global.fetch).not.toHaveBeenCalled();
        expect(dom.root.hidden).toBe(true);
    });

    test("withdraw posts to withdraw URL", async function () {
        setupDom({ banner: { autoOpen: "0" } });
        mockFetch(mockOk({ ok: true, reload: false }));
        loadBanner();
        window.ScriptConsent.withdraw();
        await flushPromises();
        expect(global.fetch).toHaveBeenCalledWith(
            "/script-consent/withdraw/",
            expect.objectContaining({ method: "POST", body: "{}" })
        );
    });

    test("uses csrftoken cookie for CSRF header", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        document.cookie = "csrftoken=abc123; path=/";
        mockFetch(mockOk({ ok: true, reload: false }));
        loadBanner();
        queryBtn(dom.root, "accept_all").click();
        await flushPromises();
        expect(global.fetch.mock.calls[0][1].headers["X-CSRFToken"]).toBe("abc123");
    });

    test("falls back to csrfmiddlewaretoken input for CSRF", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        var input = document.createElement("input");
        input.name = "csrfmiddlewaretoken";
        input.value = "formtoken";
        document.body.appendChild(input);
        mockFetch(mockOk({ ok: true, reload: false }));
        loadBanner();
        queryBtn(dom.root, "accept_all").click();
        await flushPromises();
        expect(global.fetch.mock.calls[0][1].headers["X-CSRFToken"]).toBe("formtoken");
    });

    test("calls onAccept hook when accepting", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        var hook = jest.fn();
        window.ScriptConsent = { onAccept: hook };
        mockFetch(mockOk({ ok: true, categories: ["required", "analytics"], reload: false }));
        loadBanner();
        queryBtn(dom.root, "accept_all").click();
        await flushPromises();
        expect(hook).toHaveBeenCalledWith(["required", "analytics"]);
    });

    test("calls onCustom hook when saving custom selection", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        var hook = jest.fn();
        window.ScriptConsent = { onCustom: hook };
        dom.root.querySelector('input[value="analytics"]').checked = true;
        mockFetch(mockOk({ ok: true, categories: ["required", "analytics"], reload: false }));
        loadBanner();
        queryBtn(dom.root, "custom").click();
        await flushPromises();
        expect(hook).toHaveBeenCalledWith(["required", "analytics"]);
    });

    test("calls onRejectOptional hook when rejecting optional", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        var hook = jest.fn();
        window.ScriptConsent = { onRejectOptional: hook };
        mockFetch(mockOk({ ok: true, categories: ["required"], reload: false }));
        loadBanner();
        queryBtn(dom.root, "reject_optional").click();
        await flushPromises();
        expect(hook).toHaveBeenCalledWith(["required"]);
    });

    test("calls onDismiss hook when dismissing", async function () {
        var dom = setupDom({ banner: { autoOpen: "1" } });
        var hook = jest.fn();
        window.ScriptConsent = { onDismiss: hook };
        mockFetch(mockOk({ ok: true }));
        loadBanner();
        queryBtn(dom.root, "dismiss").click();
        await flushPromises();
        expect(hook).toHaveBeenCalled();
    });

    test("calls onWithdraw hook when withdrawing", async function () {
        setupDom({ banner: { autoOpen: "0" } });
        var hook = jest.fn();
        window.ScriptConsent = { onWithdraw: hook };
        mockFetch(mockOk({ ok: true, reload: false }));
        loadBanner();
        window.ScriptConsent.withdraw();
        await flushPromises();
        expect(hook).toHaveBeenCalled();
    });

    test("logs error when server returns failure", async function () {
        var errorSpy = jest.spyOn(console, "error").mockImplementation(() => { });
        var dom = setupDom({ banner: { autoOpen: "1" } });
        mockFetch(mockError({ ok: false, error: "bad request" }, 400));
        loadBanner();
        queryBtn(dom.root, "accept_all").click();
        await flushPromises();
        expect(errorSpy).toHaveBeenCalledWith(expect.stringContaining("accept failed"), expect.any(Error));
        expect(queryBtn(dom.root, "accept_all").disabled).toBe(false);
    });

    test("logs hook errors but does not break flow", async function () {
        var errorSpy = jest.spyOn(console, "error").mockImplementation(() => { });
        var dom = setupDom({ banner: { autoOpen: "1" } });
        window.ScriptConsent = {
            onAccept: function () {
                throw new Error("boom");
            },
        };
        mockFetch(mockOk({ ok: true, categories: ["required"], reload: false }));
        loadBanner();
        queryBtn(dom.root, "accept_all").click();
        await flushPromises();
        expect(errorSpy).toHaveBeenCalledWith(expect.stringContaining("onAccept error"), expect.any(Error));
        expect(dom.root.hidden).toBe(true);
    });

    test("plays launcher attention on manual close when motion is allowed", function () {
        window.matchMedia = jest.fn().mockReturnValue({ matches: false });
        var dom = setupDom({ banner: { autoOpen: "0" } });
        loadBanner();
        dom.launcher.click();
        expect(dom.root.hidden).toBe(false);
        queryBtn(dom.root, "close").click();
        // hide() → showLauncher({ attention: true }) when not reloading
        expect(dom.launcher.hidden).toBe(false);
        expect(dom.launcher.classList.contains("cc-launcher--attention")).toBe(true);
    });

    test("does not play launcher attention when reduced motion is preferred", function () {
        window.matchMedia = jest.fn().mockReturnValue({ matches: true });
        var dom = setupDom({ banner: { autoOpen: "0" } });
        loadBanner();
        dom.launcher.click();
        queryBtn(dom.root, "close").click();
        expect(dom.launcher.hidden).toBe(false);
        expect(dom.launcher.classList.contains("cc-launcher--attention")).toBe(false);
    });
});
