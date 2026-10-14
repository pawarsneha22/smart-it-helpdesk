/*
 * main.js - small progressive enhancements for the Helpdesk UI.
 * Everything here is optional; the application works without JS.
 */
(function () {
  "use strict";

  var shell = document.querySelector(".app-shell");
  var navToggle = document.querySelector("[data-nav-toggle]");
  var navClose = document.querySelector("[data-nav-close]");

  function closeNavigation() {
    if (!shell || !navToggle) return;
    shell.classList.remove("nav-open");
    navToggle.setAttribute("aria-expanded", "false");
    navToggle.setAttribute("aria-label", "Open navigation");
  }

  if (navToggle && shell) {
    navToggle.addEventListener("click", function () {
      var isOpen = shell.classList.toggle("nav-open");
      navToggle.setAttribute("aria-expanded", String(isOpen));
      navToggle.setAttribute("aria-label", isOpen ? "Close navigation" : "Open navigation");
    });
  }
  if (navClose) navClose.addEventListener("click", closeNavigation);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeNavigation();
  });
  document.querySelectorAll(".app-sidebar a").forEach(function (link) {
    link.addEventListener("click", closeNavigation);
  });

  // Make whole table rows clickable when they carry a data-href attribute.
  document.addEventListener("click", function (event) {
    var row = event.target.closest("tr.clickable-row");
    if (row && row.dataset.href) {
      window.location.href = row.dataset.href;
    }
  });

  document.addEventListener("keydown", function (event) {
    var row = event.target.closest("tr.clickable-row");
    if (row && row.dataset.href && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      window.location.href = row.dataset.href;
    }
  });

  // Client-side validation helpers for the ticket + register forms.
  var ticketForm = document.getElementById("ticketForm");
  if (ticketForm) {
    ticketForm.addEventListener("submit", function (event) {
      var title = (document.getElementById("title").value || "").trim();
      var desc = (document.getElementById("description").value || "").trim();
      var titleField = document.getElementById("title");
      var descField = document.getElementById("description");
      titleField.setCustomValidity(title.length < 5 ? "Please enter at least 5 characters." : "");
      descField.setCustomValidity(desc.length < 20 ? "Please enter at least 20 characters." : "");
      if (!ticketForm.checkValidity()) {
        event.preventDefault();
        ticketForm.reportValidity();
        return;
      }
      setSubmitting(ticketForm);
    });
  }

  var registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", function (event) {
      var password = document.getElementById("password").value || "";
      var confirm = document.getElementById("confirm").value || "";
      if (password !== confirm) {
        event.preventDefault();
        document.getElementById("confirm").setCustomValidity("Passwords do not match.");
        document.getElementById("confirm").reportValidity();
        return;
      }
      document.getElementById("confirm").setCustomValidity("");
      if (registerForm.checkValidity()) setSubmitting(registerForm);
    });
  }

  function setSubmitting(form) {
    var button = form.querySelector('button[type="submit"]');
    if (!button) return;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.dataset.originalText = button.textContent.trim();
    button.textContent = "Please wait…";
  }
})();
