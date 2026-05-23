// ── Sidebar Toggle ────────────────────────────────────────────
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('sidebarOverlay');
const toggleBtn = document.getElementById('sidebarToggle');

if (toggleBtn) {
  toggleBtn.addEventListener('click', () => {
    sidebar.classList.toggle('show');
    overlay.classList.toggle('show');
  });
}
if (overlay) {
  overlay.addEventListener('click', () => {
    sidebar.classList.remove('show');
    overlay.classList.remove('show');
  });
}

// ── Auto-dismiss Toasts ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const toastEls = document.querySelectorAll('.toast');
  toastEls.forEach(el => {
    const toast = new bootstrap.Toast(el, { delay: 4000 });
    toast.show();
  });
});

// ── Loading Spinner on Submit ─────────────────────────────────
document.querySelectorAll('form').forEach(form => {
  form.addEventListener('submit', function () {
    const btn = this.querySelector('button[type="submit"]');
    if (btn && !btn.dataset.noSpinner) {
      btn.disabled = true;
      const original = btn.innerHTML;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = original;
      }, 8000);
    }
  });
});

// ── Plan Auto-fill (Add Membership) ──────────────────────────
const planSelect = document.getElementById('plan_id');
const startDateInput = document.getElementById('start_date');
const endDateDisplay = document.getElementById('end_date_display');
const priceDisplay = document.getElementById('price_display');

function updatePlanInfo() {
  const planId = planSelect ? planSelect.value : null;
  if (!planId || !startDateInput) return;
  fetch(`/api/plan/${planId}`)
    .then(r => r.json())
    .then(data => {
      if (priceDisplay) priceDisplay.textContent = '₹' + parseFloat(data.price).toFixed(2);
      if (startDateInput.value && endDateDisplay) {
        const start = new Date(startDateInput.value);
        start.setMonth(start.getMonth() + data.duration_months);
        endDateDisplay.textContent = start.toISOString().split('T')[0];
      }
    });
}

if (planSelect) planSelect.addEventListener('change', updatePlanInfo);
if (startDateInput) startDateInput.addEventListener('change', updatePlanInfo);

// ── Confirm Delete Modals ─────────────────────────────────────
document.querySelectorAll('[data-confirm]').forEach(btn => {
  btn.addEventListener('click', function (e) {
    if (!confirm(this.dataset.confirm)) e.preventDefault();
  });
});

// ── Search filter highlight ───────────────────────────────────
const searchInput = document.getElementById('searchInput');
if (searchInput) {
  searchInput.addEventListener('input', function () {
    const val = this.value.toLowerCase();
    document.querySelectorAll('.searchable-row').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(val) ? '' : 'none';
    });
  });
}
