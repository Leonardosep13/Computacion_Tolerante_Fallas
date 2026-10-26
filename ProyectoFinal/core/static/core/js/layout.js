(() => {
    const toggle = document.querySelector(".menu-toggle");
    if (!toggle) {
        return;
    }
    const sidebar = document.querySelector("#sidebar");
    const backdrop = document.querySelector(".sidebar-backdrop");
    const main = document.querySelector(".app-main");
    const footer = document.querySelector(".app-footer");
    const chatWidget = document.querySelector("#chat-widget");
    const mobile = window.matchMedia("(max-width: 760px)");
    let expanded = !mobile.matches;

    function render() {
        document.body.classList.toggle("sidebar-open", mobile.matches && expanded);
        document.body.classList.toggle("sidebar-collapsed", !mobile.matches && !expanded);
        toggle.setAttribute("aria-expanded", String(expanded));
        toggle.setAttribute("aria-label", expanded ? "Cerrar menú de navegación" : "Abrir menú de navegación");
        backdrop.hidden = !mobile.matches || !expanded;
        sidebar.inert = mobile.matches && !expanded;
        main.inert = mobile.matches && expanded;
        footer.inert = mobile.matches && expanded;
        if (chatWidget) chatWidget.inert = mobile.matches && expanded;
    }

    function closeMenu() {
        expanded = false;
        render();
        toggle.focus();
    }

    document.body.classList.add("js-enabled");
    toggle.hidden = false;
    render();
    toggle.addEventListener("click", () => {
        expanded = !expanded;
        render();
        if (mobile.matches && expanded) {
            sidebar.querySelector("a").focus();
        }
    });
    backdrop.addEventListener("click", closeMenu);
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && expanded) {
            closeMenu();
        }
        if (event.key === "Tab" && mobile.matches && expanded) {
            const controls = [toggle, ...sidebar.querySelectorAll("a")];
            const index = controls.indexOf(document.activeElement);
            const step = event.shiftKey ? -1 : 1;
            const next = (index + step + controls.length) % controls.length;
            event.preventDefault();
            controls[next].focus();
        }
    });
    mobile.addEventListener("change", () => {
        expanded = !mobile.matches;
        if (mobile.matches && sidebar.contains(document.activeElement)) {
            toggle.focus();
        }
        render();
    });
})();
