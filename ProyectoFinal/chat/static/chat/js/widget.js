(() => {
    const widget = document.getElementById("chat-widget");
    if (!widget) return;
    const toggle = document.getElementById("chat-widget-toggle");
    const panel = document.getElementById("chat-widget-window");
    const close = document.getElementById("chat-widget-close");
    const loading = document.getElementById("chat-widget-loading");
    const failure = document.getElementById("chat-widget-failure");
    const errorBox = document.getElementById("chat-widget-load-error");
    const retry = document.getElementById("chat-widget-retry");
    const content = document.getElementById("chat-widget-content");
    let mounted = false;
    let pending = false;

    const focusPanel = () => {
        if (panel.hidden) return;
        const input = content.querySelector("textarea:not(:disabled)");
        (input || close).focus({preventScroll: true});
        const messages = content.querySelector(".chat-messages");
        if (messages) {
            messages.scrollTop = messages.querySelector(".chat-message") ? messages.scrollHeight : 0;
        }
    };
    const load = async () => {
        if (mounted || pending) return;
        pending = true;
        loading.hidden = false;
        failure.hidden = true;
        try {
            const response = await fetch(widget.dataset.panelUrl, {
                credentials: "same-origin",
                headers: {"Accept": "text/html"},
                cache: "no-store",
            });
            if (response.redirected || response.status === 401) {
                retry.hidden = true;
                const link = document.createElement("a");
                link.href = widget.dataset.loginUrl;
                link.textContent = "Iniciar sesión";
                errorBox.replaceChildren("Tu sesión terminó. ", link);
                failure.hidden = false;
                return;
            }
            if (!response.ok) throw new Error("No se pudo cargar el chat. Inténtalo de nuevo.");
            const documentFragment = new DOMParser().parseFromString(await response.text(), "text/html");
            const app = documentFragment.querySelector("#chat-widget-app[data-chat-app]");
            if (!app) throw new Error("El servidor no devolvió el panel de chat esperado.");
            content.replaceChildren(document.importNode(app, true));
            window.SpendingChat.mount(content.querySelector("[data-chat-app]"));
            mounted = true;
            focusPanel();
        } catch (error) {
            errorBox.textContent = error instanceof TypeError
                ? "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo."
                : error.message;
            failure.hidden = false;
        } finally {
            pending = false;
            loading.hidden = true;
        }
    };
    const setOpen = open => {
        panel.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", open ? "Minimizar chat" : "Abrir chat de gastos");
        if (open) {
            focusPanel();
            load();
        } else {
            toggle.focus({preventScroll: true});
        }
    };
    toggle.hidden = false;
    toggle.addEventListener("click", () => setOpen(panel.hidden));
    close.addEventListener("click", () => setOpen(false));
    retry.addEventListener("click", load);
    widget.addEventListener("keydown", event => {
        if (event.key === "Escape" && !panel.hidden) {
            event.preventDefault();
            event.stopPropagation();
            setOpen(false);
        }
    });
})();
