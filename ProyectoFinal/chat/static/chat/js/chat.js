(() => {
    const app = document.getElementById("chat-app");
    if (!app) return;
    const configured = JSON.parse(document.getElementById("chat-configured").textContent);
    const messages = document.getElementById("chat-messages");
    const welcome = document.getElementById("chat-welcome");
    const input = document.getElementById("chat-message");
    const send = document.getElementById("chat-send");
    const clear = document.getElementById("chat-clear");
    const confirmation = document.getElementById("chat-clear-confirmation");
    const clearAccept = document.getElementById("chat-clear-accept");
    const clearCancel = document.getElementById("chat-clear-cancel");
    const status = document.getElementById("chat-status");
    const errorBox = document.getElementById("chat-error");
    const suggestions = app.querySelectorAll("[data-suggestion]");
    let busy = false;
    let expired = false;

    const scrollToLatest = () => { messages.scrollTop = messages.scrollHeight; };
    const showError = text => {
        errorBox.textContent = text;
        if (expired) {
            const link = document.createElement("a");
            link.href = app.dataset.loginUrl;
            link.textContent = "Iniciar sesión";
            errorBox.append(" ", link);
        }
        errorBox.hidden = false;
    };
    const syncControls = () => {
        input.disabled = busy || !configured || expired;
        send.disabled = input.disabled || !input.value.trim();
        clear.disabled = busy || expired;
        clearAccept.disabled = busy || expired;
        suggestions.forEach(button => { button.disabled = input.disabled; });
        messages.setAttribute("aria-busy", String(busy));
    };
    const addMessage = (role, text) => {
        welcome.hidden = true;
        const article = document.createElement("article");
        article.className = `chat-message${role === "user" ? " chat-message-user" : ""}`;
        const label = document.createElement("span");
        label.className = "chat-message-label";
        label.textContent = role === "user" ? "Tú" : "Asistente";
        const bubble = document.createElement("p");
        bubble.className = "chat-bubble";
        bubble.textContent = text;
        article.append(label, bubble);
        messages.append(article);
        scrollToLatest();
    };
    const addTools = calls => {
        for (const call of calls || []) {
            const line = document.createElement("p");
            line.className = "chat-tool";
            const args = Object.entries(call.argumentos)
                .map(([key, value]) => `${key}=${JSON.stringify(value)}`).join(", ");
            line.textContent = `🔧 ${call.nombre}(${args}) · ${call.estado}`;
            messages.append(line);
        }
        scrollToLatest();
    };
    const request = async (url, body) => {
        const csrf = document.cookie.split("; ")
            .find(cookie => cookie.startsWith("csrftoken="))?.split("=").slice(1).join("=") || "";
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {"Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(csrf)},
            body: JSON.stringify(body),
        });
        if (response.status === 401 || response.redirected) {
            expired = true;
            throw new Error("Tu sesión terminó. Inicia sesión de nuevo para continuar.");
        }
        if (response.status === 403) {
            throw new Error("No se pudo validar la sesión. Recarga la página antes de continuar.");
        }
        if (!response.headers.get("Content-Type")?.includes("application/json")) {
            throw new Error("El servidor no pudo completar la solicitud. Revisa Gastos antes de repetirla.");
        }
        const data = await response.json();
        if (!response.ok) {
            addTools(data.llamadas);
            throw new Error(data.error || "No se pudo completar la solicitud.");
        }
        return data;
    };
    const sendMessage = async () => {
        const text = input.value.trim();
        if (!text || busy || !configured || expired) return;
        if (text.length > input.maxLength) {
            showError(`El mensaje no puede superar ${input.maxLength} caracteres.`);
            return;
        }
        busy = true;
        confirmation.hidden = true;
        errorBox.hidden = true;
        status.textContent = "El asistente está consultando tu solicitud…";
        addMessage("user", text);
        input.value = "";
        syncControls();
        try {
            const data = await request(app.dataset.endpoint, {mensaje: text});
            addTools(data.llamadas);
            addMessage("model", data.respuesta);
        } catch (error) {
            showError(error instanceof TypeError
                ? "Se perdió la conexión. Algunas operaciones pudieron aplicarse: revisa Gastos antes de repetirlas."
                : error.message);
        } finally {
            busy = false;
            status.textContent = "";
            syncControls();
            if (!expired) input.focus();
        }
    };

    const history = JSON.parse(document.getElementById("chat-history").textContent);
    history.forEach(turn => addMessage(turn.role, turn.text));
    syncControls();
    input.addEventListener("input", syncControls);
    input.addEventListener("keydown", event => {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            sendMessage();
        }
    });
    send.addEventListener("click", sendMessage);
    suggestions.forEach(button => button.addEventListener("click", () => {
        input.value = button.dataset.suggestion;
        syncControls();
        input.focus();
    }));
    clear.addEventListener("click", () => {
        confirmation.hidden = false;
        clearCancel.focus();
    });
    clearCancel.addEventListener("click", () => {
        confirmation.hidden = true;
        clear.focus();
    });
    clearAccept.addEventListener("click", async () => {
        if (busy || expired) return;
        busy = true;
        errorBox.hidden = true;
        syncControls();
        try {
            await request(app.dataset.clearEndpoint, {});
            messages.querySelectorAll(".chat-message, .chat-tool").forEach(node => node.remove());
            confirmation.hidden = true;
            welcome.hidden = false;
            status.textContent = "Conversación borrada. Tus gastos no se modificaron.";
        } catch (error) {
            showError(error instanceof TypeError ? "No se pudo conectar con el servidor." : error.message);
        } finally {
            busy = false;
            syncControls();
        }
    });
})();
