// main.js — Spendly front-end behaviour.
//
// All interactive UI lives here so templates stay free of inline <script>
// blocks. Two small widgets ship today:
//
//   1. Video modal (landing page). Lazy-loads the YouTube iframe on first
//      open, then tears it down on close so the video doesn't keep
//      playing in the background.
//   2. "Notify me" stub (analytics page). Just an alert — left in place
//      so the analytics route's marketing CTA isn't a dead link before
//      the real feature ships.

(function () {
    "use strict";

    // --- 1. Video modal ---------------------------------------------- //
    var modal = document.getElementById("video-modal");
    if (modal) {
        var iframe = document.getElementById("video-modal-iframe");
        var openBtn = document.getElementById("how-it-works-btn");

        function openVideoModal() {
            if (!iframe || !iframe.dataset.src) return;
            if (!iframe.dataset.loaded) {
                iframe.src = iframe.dataset.src + "&autoplay=1";
                iframe.dataset.loaded = "1";
            }
            modal.classList.add("is-open");
            modal.setAttribute("aria-hidden", "false");
            document.body.style.overflow = "hidden";
        }

        function closeVideoModal() {
            modal.classList.remove("is-open");
            modal.setAttribute("aria-hidden", "true");
            document.body.style.overflow = "";
            if (iframe) {
                iframe.src = "";
                delete iframe.dataset.loaded;
            }
        }

        if (openBtn) {
            openBtn.addEventListener("click", function (e) {
                e.preventDefault();
                openVideoModal();
            });
        }
        modal.querySelectorAll("[data-close-modal]").forEach(function (el) {
            el.addEventListener("click", closeVideoModal);
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && modal.classList.contains("is-open")) {
                closeVideoModal();
            }
        });
    }

    // --- 2. Analytics notify-me stub --------------------------------- //
    var notifyBtn = document.getElementById("notify-me-btn");
    if (notifyBtn) {
        notifyBtn.addEventListener("click", function (e) {
            e.preventDefault();
            window.alert("Thanks for your interest! We'll notify you when Analytics is ready.");
        });
    }
})();
