(function () {
  const base = (window.APP_CONFIG && window.APP_CONFIG.baseUrl) || 'http://127.0.0.1:8000';
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const views = $$('.view');
  const navButtons = $$('header nav button');
  let accessToken = localStorage.getItem('access_token') || '';

  function show(viewId) {
    views.forEach(v => v.classList.add('hidden'));
    $('#' + viewId).classList.remove('hidden');
    navButtons.forEach(b => b.classList.toggle('active', b.dataset.view === viewId));
  }

  async function api(path, opts = {}) {
    const res = await fetch(base + path, {
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { 'Authorization': 'Bearer ' + accessToken } : {})
      },
      ...opts,
    });
    if (!res.ok) {
      let message = res.statusText;
      let body;
      try {
        body = await res.json();
        if (body && body.detail) message = body.detail;
      } catch (_) {
        try { message = await res.text(); } catch (_) {}
      }
      const err = new Error(message || 'Request failed');
      err.status = res.status;
      err.body = body;
      throw err;
    }
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) return res.json();
    return res.text();
  }

  function fmt(n, digits = 2) { return Number(n).toFixed(digits); }

  // Dashboard loaders
  async function loadCurrentMonth() {
    const el = $('#current-month');
    try {
      const data = await api('/api/v1/current-month/');
      el.innerHTML = `
        <div><strong>${data.year}-${String(data.month).padStart(2, '0')}</strong></div>
        <div>kWh: ${fmt(data.kilowatt_hours)}</div>
        <div>Cost: ${fmt(data.cost)}</div>
        <div>Emissions: ${fmt(data.emissions_kg)} kg</div>`;
    } catch (e) {
      el.textContent = 'No data yet. Add your first bill.';
    }
  }

  async function loadSummary() {
    const el = $('#summary');
    const s = await api('/api/v1/summary/');
    el.innerHTML = `
      <div>Total kWh: ${fmt(s.total_kwh)}</div>
      <div>Total cost: ${fmt(s.total_cost)}</div>
      <div>Total emissions: ${fmt(s.total_emissions_kg)} kg</div>
      <div>Avg kWh: ${fmt(s.average_kwh)}</div>
      <div>Avg cost: ${fmt(s.average_cost)}</div>
      <div>Avg emissions: ${fmt(s.average_emissions_kg)} kg</div>`;
  }

  async function loadRecentUsage() {
    const tbody = $('#recent-usage tbody');
    const rows = await api('/api/v1/usage/recent?limit=6');
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td>${r.year}</td>
        <td>${r.month}</td>
        <td>${fmt(r.kilowatt_hours)}</td>
        <td>${fmt(r.cost)}</td>
        <td>${fmt(r.emissions_kg)}</td>
      </tr>`).join('');
  }

  // Bills page
  async function loadBills() {
    const tbody = $('#bills tbody');
    const rows = await api('/api/v1/bills/');
    tbody.innerHTML = rows.map(b => `
      <tr>
        <td>${b.id}</td>
        <td>${b.year}</td>
        <td>${b.month}</td>
        <td>${fmt(b.kilowatt_hours)}</td>
        <td>${fmt(b.cost)}</td>
      </tr>`).join('');
  }

  async function submitBill(ev) {
    ev.preventDefault();
    $('#bill-status').textContent = 'Submitting...';
    const form = ev.target;
    const payload = Object.fromEntries(new FormData(form).entries());
    // coerce number fields
    payload.year = Number(payload.year);
    payload.month = Number(payload.month);
    payload.kilowatt_hours = Number(payload.kilowatt_hours);
    payload.cost = Number(payload.cost);
    if (payload.emission_factor_kg_per_kwh)
      payload.emission_factor_kg_per_kwh = Number(payload.emission_factor_kg_per_kwh);
    try {
      await api('/api/v1/bills/', { method: 'POST', body: JSON.stringify(payload) });
      $('#bill-status').textContent = 'Saved!';
      form.reset();
      await Promise.all([loadBills(), loadCurrentMonth(), loadSummary(), loadRecentUsage(), loadTrends()]);
    } catch (e) {
      if (e.status === 401) {
        $('#bill-status').textContent = 'Please sign in first (see Sign In tab).';
      } else {
        $('#bill-status').textContent = 'Error: ' + (e.message || e);
      }
    }
  }

  // Auth
  async function signIn(ev) {
    ev.preventDefault();
    $('#signin-status').textContent = 'Signing in...';
    const form = ev.target;
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      const data = await api('/auth/login', { method: 'POST', body: JSON.stringify(payload) });
      accessToken = data.access_token;
      localStorage.setItem('access_token', accessToken);
      $('#signin-status').textContent = 'Signed in';
    } catch (e) {
      $('#signin-status').textContent = 'Error: ' + (e.message || e);
    }
  }

  // OTP flow
  let otpContact = '';
  async function requestOtp(ev) {
    ev.preventDefault();
    $('#otp-request-status').textContent = 'Sending...';
    const form = ev.target;
    const payload = Object.fromEntries(new FormData(form).entries());
    otpContact = (payload.contact || '').toString();
    try {
      const data = await api('/auth/request-otp', { method: 'POST', body: JSON.stringify({ contact: otpContact }) });
      $('#otp-request-status').textContent = 'OTP sent (demo: ' + (data.otp_demo || '***') + ')';
    } catch (e) {
      $('#otp-request-status').textContent = 'Error: ' + (e.message || e);
    }
  }

  async function verifyOtp(ev) {
    ev.preventDefault();
    $('#otp-verify-status').textContent = 'Verifying...';
    const form = ev.target;
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      const data = await api('/auth/verify-otp', { method: 'POST', body: JSON.stringify({ contact: otpContact, otp: payload.otp }) });
      accessToken = data.access_token;
      localStorage.setItem('access_token', accessToken);
      $('#otp-verify-status').textContent = 'Signed in';
      updateProfileSigned();
    } catch (e) {
      $('#otp-verify-status').textContent = 'Error: ' + (e.message || e);
    }
  }

  // Analysis
  async function loadTrends() {
    const el = $('#trends');
    const t = await api('/api/v1/analysis/trends');
    if (!t.points || !t.points.length) { el.textContent = 'No data yet.'; return; }
    el.innerHTML = '<table><thead><tr><th>Year</th><th>Month</th><th>kWh</th><th>Δ kWh</th><th>3-mo MA</th></tr></thead><tbody></tbody></table>';
    const tbody = $('#trends tbody');
    tbody.innerHTML = t.points.map(p => `
      <tr>
        <td>${p.year}</td>
        <td>${p.month}</td>
        <td>${fmt(p.kilowatt_hours)}</td>
        <td>${p.month_over_month_delta_kwh == null ? '-' : fmt(p.month_over_month_delta_kwh)}</td>
        <td>${p.moving_average_3mo_kwh == null ? '-' : fmt(p.moving_average_3mo_kwh)}</td>
      </tr>
    `).join('');
    // Chart
    const ctx = document.getElementById('trend-chart');
    if (ctx) {
      const labels = t.points.map(p => `${p.year}-${String(p.month).padStart(2, '0')}`);
      const kwh = t.points.map(p => p.kilowatt_hours);
      const ma3 = t.points.map(p => p.moving_average_3mo_kwh);
      if (window._trendChart) window._trendChart.destroy();
      window._trendChart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets: [
          { label: 'kWh', data: kwh, borderColor: '#22d3ee', backgroundColor: 'rgba(34,211,238,0.2)', tension: 0.25 },
          { label: '3-mo MA', data: ma3, borderColor: '#a78bfa', backgroundColor: 'rgba(167,139,250,0.2)', tension: 0.25 }
        ] },
        options: { plugins: { legend: { labels: { color: '#e5e7eb' } } }, scales: { x: { ticks: { color: '#9ca3af' } }, y: { ticks: { color: '#9ca3af' } } } }
      });
    }
  }

  async function loadPredictions() {
    const months = Number($('#horizon').value || 3);
    const data = await api(`/api/v1/analysis/predict?horizon_months=${months}`);
    const el = $('#predictions');
    el.innerHTML = '<table><thead><tr><th>Year</th><th>Month</th><th>Predicted kWh</th></tr></thead><tbody></tbody></table>';
    const tbody = $('#predictions tbody');
    tbody.innerHTML = data.predictions.map(p => `
      <tr>
        <td>${p.year}</td>
        <td>${p.month}</td>
        <td>${fmt(p.predicted_kwh)}</td>
      </tr>
    `).join('');
    // Chart
    const ctx = document.getElementById('prediction-chart');
    if (ctx) {
      const labels = data.predictions.map(p => `${p.year}-${String(p.month).padStart(2, '0')}`);
      const kwh = data.predictions.map(p => p.predicted_kwh);
      if (window._predChart) window._predChart.destroy();
      window._predChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [
          { label: 'Predicted kWh', data: kwh, backgroundColor: 'rgba(34,211,238,0.6)', borderColor: '#22d3ee' }
        ] },
        options: { plugins: { legend: { labels: { color: '#e5e7eb' } } }, scales: { x: { ticks: { color: '#9ca3af' } }, y: { ticks: { color: '#9ca3af' } } } }
      });
    }
  }

  async function loadAdvice() {
    const list = $('#advice-list');
    const data = await api('/api/v1/advice/');
    list.innerHTML = data.tips.map(t => `<li><strong>${t.title}:</strong> ${t.detail}</li>`).join('');
  }

  function updateProfileSigned() {
    $('#profile-signed').textContent = accessToken ? 'Yes' : 'No';
  }

  // Calculator (local only)
  function calcEmissions(ev) {
    ev.preventDefault();
    const form = ev.target;
    const payload = Object.fromEntries(new FormData(form).entries());
    const kwh = Number(payload.kwh || 0);
    const factor = Number(payload.factor || 0.7);
    const emissions = kwh * factor;
    $('#calc-result').textContent = 'Emissions: ' + emissions.toFixed(2) + ' kg CO2e';
  }

  // Estimate emission factor via backend
  async function estimateFactor(ev) {
    ev.preventDefault();
    $('#factor-result').textContent = 'Estimating...';
    const form = ev.target;
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.total_cost = Number(payload.total_cost);
    payload.kwh = Number(payload.kwh);
    if (payload.energy_price_per_kwh) payload.energy_price_per_kwh = Number(payload.energy_price_per_kwh);
    if (payload.carbon_price_per_kg) payload.carbon_price_per_kg = Number(payload.carbon_price_per_kg);
    try {
      const data = await api('/api/v1/tools/estimate-factor', { method: 'POST', body: JSON.stringify(payload) });
      $('#factor-result').textContent = 'Estimated factor: ' + data.estimated_emission_factor_kg_per_kwh.toFixed(4) + ' kg/kWh';
    } catch (e) {
      $('#factor-result').textContent = 'Error: ' + (e.message || e);
    }
  }

  // Analyzer
  async function loadAverages() {
    const data = await api('/api/v1/analysis/averages');
    $('#averages').innerHTML = `
      <div>Last month - kWh: ${data.last_month.kwh.toFixed(2)}, Emissions: ${data.last_month.emissions_kg.toFixed(2)} kg</div>
      <div>6-month avg - kWh: ${data.six_month_avg.kwh.toFixed(2)}, Emissions: ${data.six_month_avg.emissions_kg.toFixed(2)} kg</div>
    `;
  }

  function wireNav() {
    navButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        show(btn.dataset.view);
        refreshView(btn.dataset.view);
      });
    });
  }

  async function refreshView(view) {
    if (view === 'dashboard') {
      await Promise.all([loadCurrentMonth(), loadSummary(), loadRecentUsage()]);
    } else if (view === 'add-bill') {
      await loadBills();
    } else if (view === 'analysis') {
      await Promise.all([loadTrends(), loadPredictions()]);
    } else if (view === 'advice') {
      await loadAdvice();
    }
  }

  function init() {
    $('#api-base').textContent = base;
    $('#bill-form').addEventListener('submit', submitBill);
    $('#predict-btn').addEventListener('click', loadPredictions);
    $('#signin-form').addEventListener('submit', signIn);
    $('#otp-request-form').addEventListener('submit', requestOtp);
    $('#otp-verify-form').addEventListener('submit', verifyOtp);
    $('#calc-form').addEventListener('submit', calcEmissions);
    $('#factor-form').addEventListener('submit', estimateFactor);
    $('#refresh-dashboard').addEventListener('click', () => refreshView('dashboard'));
    $('#refresh-analysis').addEventListener('click', () => refreshView('analysis'));
    $('#refresh-advice').addEventListener('click', () => refreshView('advice'));
    $('#seed-data').addEventListener('click', async () => {
      const sample = [
        { year: 2025, month: 8, kilowatt_hours: 300.5, cost: 170.25 },
        { year: 2025, month: 9, kilowatt_hours: 320.5, cost: 185.75 }
      ];
      try {
        await Promise.all(sample.map(p => api('/api/v1/bills/', { method: 'POST', body: JSON.stringify(p) })));
        await Promise.all([loadBills(), loadCurrentMonth(), loadSummary(), loadRecentUsage(), loadTrends(), loadPredictions(), loadAdvice()]);
      } catch (e) {
        if (e.status === 401) {
          alert('Please sign in first (Sign In tab) to add sample bills.');
        }
        await Promise.all([loadBills(), loadCurrentMonth(), loadSummary(), loadRecentUsage(), loadTrends(), loadPredictions(), loadAdvice()]);
      }
    });
    wireNav();
    refreshView('dashboard');
    updateProfileSigned();
  }

  window.addEventListener('DOMContentLoaded', init);
})();

