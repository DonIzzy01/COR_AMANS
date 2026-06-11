/* ============================================================
   COR AMANS — Main JavaScript v2.0
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {

  // ── Notifications ────────────────────────────────────────
  const notifContainer = document.getElementById("notification-container");

  function showNotification(message, type = "info", duration = 6000) {
    if (!notifContainer) return;
    const icons = { success: "fa-check-circle", error: "fa-circle-xmark", warning: "fa-triangle-exclamation", info: "fa-circle-info" };
    const el = document.createElement("div");
    el.className = `notification ${type}`;
    el.style.animation = "notifSlideIn 0.35s cubic-bezier(0.34,1.56,0.64,1) forwards";
    el.innerHTML = `
      <div class="notification__icon"><i class="fas ${icons[type] || icons.info}"></i></div>
      <div class="notification__content"><p class="notification__message">${message}</p></div>
      <button class="notification__close" aria-label="Dismiss"><i class="fas fa-xmark"></i></button>
    `;
    notifContainer.appendChild(el);

    const dismiss = () => {
      el.style.animation = "notifSlideOut 0.3s ease forwards";
      el.addEventListener("animationend", () => el.remove(), { once: true });
    };
    el.querySelector(".notification__close").addEventListener("click", dismiss);
    if (duration > 0) setTimeout(dismiss, duration);
  }

  // Convert flash messages
  document.querySelectorAll(".flash-message").forEach(msg => {
    const cat = msg.dataset.category || "info";
    const text = msg.dataset.message || "";
    const typeMap = { success: "success", error: "error", danger: "error", warning: "warning", info: "info" };
    showNotification(text, typeMap[cat] || "info");
  });

  // ── Navbar scroll ────────────────────────────────────────
  const navbar = document.querySelector(".navbar");
  if (navbar) {
    const toggle = () => navbar.classList.toggle("navbar--scrolled", window.scrollY > 10);
    toggle();
    window.addEventListener("scroll", toggle, { passive: true });
  }

  // ── Mobile menu ──────────────────────────────────────────
  const hamburger = document.querySelector(".navbar__hamburger");
  const mobileMenu = document.querySelector(".mobile-menu");
  if (hamburger && mobileMenu) {
    hamburger.addEventListener("click", () => {
      const isOpen = mobileMenu.classList.toggle("is-open");
      hamburger.setAttribute("aria-expanded", isOpen);
      hamburger.innerHTML = isOpen
        ? '<i class="fas fa-xmark text-lg"></i>'
        : '<i class="fas fa-bars text-lg"></i>';
    });
    document.addEventListener("click", e => {
      if (!navbar.contains(e.target)) {
        mobileMenu.classList.remove("is-open");
        hamburger.setAttribute("aria-expanded", "false");
        hamburger.innerHTML = '<i class="fas fa-bars text-lg"></i>';
      }
    });
  }

  // ── Dashboard / Admin sidebar ────────────────────────────
  const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
  const sidebar = document.querySelector(".sidebar, .admin-sidebar");
  const sidebarOverlay = document.querySelector(".sidebar-overlay");

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener("click", () => {
      sidebar.classList.toggle("is-open");
      sidebarOverlay && sidebarOverlay.classList.toggle("is-visible");
    });
    sidebarOverlay && sidebarOverlay.addEventListener("click", () => {
      sidebar.classList.remove("is-open");
      sidebarOverlay.classList.remove("is-visible");
    });
  }

  // ── Scroll-reveal (IntersectionObserver) ─────────────────
  const revealEls = document.querySelectorAll(".reveal, .reveal-left, .reveal-right, .reveal-scale");
  if (revealEls.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: "0px 0px -40px 0px" });
    revealEls.forEach(el => io.observe(el));
  }

  // ── Button ripple effect ──────────────────────────────────
  document.querySelectorAll(".btn").forEach(btn => {
    btn.style.overflow = "hidden";
    btn.style.position = "relative";
    btn.addEventListener("click", function (e) {
      const ripple = document.createElement("span");
      ripple.className = "btn-ripple";
      const rect = this.getBoundingClientRect();
      ripple.style.left = `${e.clientX - rect.left}px`;
      ripple.style.top  = `${e.clientY - rect.top}px`;
      this.appendChild(ripple);
      ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
    });
  });

  // ── Password visibility toggle ────────────────────────────
  document.querySelectorAll(".password-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const wrap  = btn.closest(".password-wrap");
      const input = wrap && wrap.querySelector("input");
      if (!input) return;
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      const icon = btn.querySelector("i");
      if (icon) { icon.classList.toggle("fa-eye", !show); icon.classList.toggle("fa-eye-slash", show); }
    });
  });

  // ── Multi-step register form ──────────────────────────────
  const stepForm = document.getElementById("register-form");
  if (stepForm) {
    let currentStep = 1;
    const totalSteps = stepForm.querySelectorAll(".step-panel").length;

    function goToStep(n) {
      stepForm.querySelectorAll(".step-panel").forEach((panel, i) => {
        panel.classList.toggle("active", i + 1 === n);
      });
      stepForm.querySelectorAll(".step").forEach((step, i) => {
        step.classList.toggle("active", i + 1 === n);
        step.classList.toggle("done", i + 1 < n);
      });
      stepForm.querySelectorAll(".step-connector").forEach((conn, i) => {
        conn.classList.toggle("done", i + 1 < n);
      });
      currentStep = n;
      const progress = document.getElementById("form-progress");
      if (progress) progress.value = Math.round(((n - 1) / totalSteps) * 100);
    }

    function validateStep(step) {
      const panel = stepForm.querySelector(`.step-panel:nth-of-type(${step})`);
      if (!panel) return true;
      const required = panel.querySelectorAll("[required]");
      let valid = true;
      required.forEach(field => {
        if (!field.value.trim()) {
          field.classList.add("is-error");
          valid = false;
          field.addEventListener("input", () => field.classList.remove("is-error"), { once: true });
        }
      });
      if (!valid) showNotification("Please fill in all required fields before continuing.", "warning");
      return valid;
    }

    stepForm.querySelectorAll("[data-step-next]").forEach(btn => {
      btn.addEventListener("click", () => {
        if (validateStep(currentStep) && currentStep < totalSteps) {
          goToStep(currentStep + 1);
          stepForm.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });
    stepForm.querySelectorAll("[data-step-prev]").forEach(btn => {
      btn.addEventListener("click", () => {
        if (currentStep > 1) goToStep(currentStep - 1);
      });
    });

    goToStep(1);
  }

  // ── Payment toggle ────────────────────────────────────────
  document.querySelectorAll(".payment-toggle").forEach(toggle => {
    toggle.addEventListener("change", async function () {
      const userId = this.dataset.userId;
      const isPaid = this.checked;
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
      const row = this.closest("tr, .user-card");
      if (row) row.style.opacity = "0.6";

      try {
        const resp = await fetch(`/admin/toggle-payment/${userId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
          body: JSON.stringify({ is_paid: isPaid }),
        });
        const data = await resp.json();
        if (!data.success) throw new Error();
        const badge = document.querySelector(`[data-status-badge="${userId}"]`);
        if (badge) {
          badge.textContent = isPaid ? "Paid" : "Unpaid";
          badge.className = `badge ${isPaid ? "badge-success" : "badge-error"}`;
        }
        showNotification(isPaid ? "Payment status activated." : "Payment status deactivated.", "success");
      } catch (_) {
        this.checked = !isPaid;
        showNotification("Could not update payment status. Please try again.", "error");
      } finally {
        if (row) row.style.opacity = "";
      }
    });
  });

  // ── Admin confirm dialogs ─────────────────────────────────
  document.querySelectorAll("[data-confirm]").forEach(el => {
    el.addEventListener("click", e => {
      const msg = el.dataset.confirm || "Are you sure?";
      if (!confirm(msg)) e.preventDefault();
    });
  });

  // ── Animated stat counters ────────────────────────────────
  document.querySelectorAll("[data-count-to]").forEach(el => {
    const target = parseInt(el.dataset.countTo, 10);
    const prefix = el.dataset.prefix || "";
    const suffix = el.dataset.suffix || "";
    const duration = parseInt(el.dataset.duration || "1500", 10);

    const io = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting) {
        io.disconnect();
        let start = 0;
        const step = (timestamp) => {
          if (!start) start = timestamp;
          const progress = Math.min((timestamp - start) / duration, 1);
          const val = Math.floor(progress * target);
          el.textContent = prefix + val.toLocaleString() + suffix;
          if (progress < 1) requestAnimationFrame(step);
          else el.textContent = prefix + target.toLocaleString() + suffix;
        };
        requestAnimationFrame(step);
      }
    }, { threshold: 0.5 });
    io.observe(el);
  });

  // ── User search filter ────────────────────────────────────
  const searchInput = document.getElementById("user-search");
  if (searchInput) {
    searchInput.addEventListener("input", function () {
      const q = this.value.toLowerCase().trim();
      document.querySelectorAll("[data-searchable]").forEach(row => {
        const text = row.dataset.searchable.toLowerCase();
        row.style.display = q === "" || text.includes(q) ? "" : "none";
      });
    });
  }

  // ── Profile photo preview ─────────────────────────────────
  const photoInput = document.getElementById("profile-photo-input");
  const photoPreview = document.getElementById("photo-preview");
  if (photoInput && photoPreview) {
    photoInput.addEventListener("change", function () {
      const file = this.files[0];
      if (file && file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = e => {
          photoPreview.src = e.target.result;
          photoPreview.style.display = "block";
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // ── Chart.js default theme ────────────────────────────────
  if (typeof Chart !== "undefined") {
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.color = "#64748B";
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.tooltip.backgroundColor = "#1C2B2E";
    Chart.defaults.plugins.tooltip.titleFont = { family: "'Playfair Display', serif", size: 13 };
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
  }

  // ── Petal celebration on success ─────────────────────────
  function launchPetals(x, y) {
    const colors = ["#1B4332","#40916C","#74C69D","#C9A84C","#D8F3DC","#FFFFFF"];
    for (let i = 0; i < 18; i++) {
      const petal = document.createElement("div");
      petal.className = "petal";
      petal.style.cssText = `
        left:${x}px; top:${y}px;
        background:${colors[i % colors.length]};
        --tx:${(Math.random() - 0.5) * 200}px;
        --ty:${-80 - Math.random() * 120}px;
        --rot:${(Math.random() - 0.5) * 360}deg;
        animation-duration:${0.8 + Math.random() * 0.8}s;
        animation-delay:${Math.random() * 0.2}s;
      `;
      document.body.appendChild(petal);
      petal.addEventListener("animationend", () => petal.remove(), { once: true });
    }
  }

  document.querySelectorAll(".btn-primary, .btn-gold").forEach(btn => {
    btn.addEventListener("click", function (e) {
      if (this.type === "submit") {
        const rect = this.getBoundingClientRect();
        launchPetals(rect.left + rect.width / 2, rect.top + rect.height / 2);
      }
    });
  });

  // ── Session timeout warning ───────────────────────────────
  const timeoutEl = document.getElementById("session-timer");
  if (timeoutEl) {
    const totalSeconds = parseInt(timeoutEl.dataset.timeout || "1200", 10);
    let remaining = totalSeconds;
    const tick = () => {
      remaining--;
      const m = Math.floor(remaining / 60);
      const s = remaining % 60;
      timeoutEl.textContent = `Session: ${m}:${s.toString().padStart(2,"0")}`;
      if (remaining <= 120 && remaining > 0) {
        timeoutEl.style.background = "#FEE2E2";
        timeoutEl.style.color = "#DC2626";
      }
      if (remaining <= 0) {
        clearInterval(timer);
        showNotification("Your session has expired. Redirecting to login…", "warning", 0);
        setTimeout(() => window.location.href = "/login", 2500);
      }
    };
    const timer = setInterval(tick, 1000);

    document.addEventListener("click", () => {
      remaining = totalSeconds;
      if (timeoutEl) {
        timeoutEl.style.background = "";
        timeoutEl.style.color = "";
      }
    });
  }

  // Expose showNotification globally for inline use
  window.COR = { showNotification, launchPetals };
});
