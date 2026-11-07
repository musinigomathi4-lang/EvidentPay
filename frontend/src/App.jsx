import { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, BadgeCheck,
  Banknote, Bell, Check, CheckCircle2, ChevronDown, ChevronRight,
  CircleAlert, Clock3, CloudUpload, FileCheck2, FileImage, FileSpreadsheet,
  Fingerprint, History, LayoutDashboard, LoaderCircle, Menu, Plus,
  RefreshCw, Search, ShieldCheck, Sparkles, Upload, Users, Wallet,
  X, Zap
} from "lucide-react";
import "./index.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiRequest(path, options = {}) {
  const response = await fetch(API + path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || data.message || "Something went wrong.";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function money(value) {
  const number = Number(value || 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency", currency: "INR", maximumFractionDigits: 0
  }).format(number);
}

function shortDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("en-IN", {
    day: "2-digit", month: "short", year: "numeric"
  });
}

function statusTone(status) {
  const value = String(status || "").toLowerCase();
  if (value.includes("match") || value.includes("verified")) return "good";
  if (value.includes("duplicate") || value.includes("review") || value.includes("mismatch")) return "warning";
  if (value.includes("outside") || value.includes("not_found") || value.includes("unmatched")) return "muted";
  return "neutral";
}

function StatusPill({ value }) {
  return <span className={"status-pill " + statusTone(value)}><span />{String(value || "Pending").replaceAll("_", " ")}</span>;
}

function App() {
  const [page, setPage] = useState("overview");
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [claims, setClaims] = useState([]);
  const [results, setResults] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [eventName, setEventName] = useState("");
  const [eventPrice, setEventPrice] = useState("500");
  const [participants, setParticipants] = useState("100");
  const [screenshots, setScreenshots] = useState([]);
  const [statement, setStatement] = useState(null);
  const [uploadSummary, setUploadSummary] = useState(null);
  const [statementSummary, setStatementSummary] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);

  async function loadEvents() {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest("/api/events");
      setEvents(data.events || []);
    } catch (err) {
      setError(err.message + " Check that the EvidentPay backend is running on port 8000.");
    } finally {
      setLoading(false);
    }
  }

  async function loadEventData(event) {
    setSelectedEvent(event);
    setPage("event");
    setClaims([]);
    setResults([]);
    setUploadSummary(null);
    setStatementSummary(null);
    setError("");
    try {
      const [claimData, resultData] = await Promise.all([
        apiRequest("/api/events/" + event.event_id + "/claims"),
        apiRequest("/api/events/" + event.event_id + "/results")
      ]);
      setClaims(claimData.claims || []);
      setResults(resultData.results || []);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { loadEvents(); }, []);

  const filteredEvents = useMemo(() => events.filter((event) =>
    (event.event_name + " " + event.event_id).toLowerCase().includes(search.toLowerCase())
  ), [events, search]);

  const totalClaims = events.reduce((sum, event) => sum + Number(event.total_claims || 0), 0);
  const totalResults = events.reduce((sum, event) => sum + Number(event.total_results || 0), 0);
  const totalMatched = results.filter((item) => String(item.status).toLowerCase().includes("match")).length;
  const reviewCount = results.filter((item) => statusTone(item.status) === "warning").length;
  const processedEvents = events.filter((event) => Number(event.total_results || 0) > 0).length;

  function startNewEvent() {
    setEventName("");
    setEventPrice("500");
    setParticipants("100");
    setScreenshots([]);
    setStatement(null);
    setUploadSummary(null);
    setStatementSummary(null);
    setSelectedEvent(null);
    setError("");
    setNotice("");
    setPage("new");
  }

  async function createEvent(event) {
    event.preventDefault();
    setBusy("create");
    setError("");
    setNotice("");
    try {
      const created = await apiRequest("/api/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_name: eventName.trim(),
          event_price: Number(eventPrice),
          expected_participant_count: Number(participants)
        })
      });
      await loadEvents();
      setSelectedEvent({
        event_id: created.event_id,
        event_name: created.event_name,
        event_price: created.event_price,
        expected_participant_count: created.expected_participant_count,
        total_claims: 0,
        total_bank_transactions: 0,
        total_results: 0
      });
      setPage("new");
      setNotice("Event created. Add screenshots and the recipient-side bank statement to continue.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function uploadScreenshots() {
    if (!selectedEvent || screenshots.length === 0) return;
    setBusy("screenshots");
    setError("");
    setNotice("");
    const body = new FormData();
    screenshots.forEach((file) => body.append("files", file));
    try {
      const data = await apiRequest("/api/events/" + selectedEvent.event_id + "/screenshots", {
        method: "POST", body
      });
      setUploadSummary(data);
      setScreenshots([]);
      setNotice(data.successful + " screenshot(s) processed. " + data.failed + " failed.");
      await loadEvents();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function uploadStatement() {
    if (!selectedEvent || !statement) return;
    setBusy("statement");
    setError("");
    setNotice("");
    const body = new FormData();
    body.append("file", statement);
    try {
      const data = await apiRequest("/api/events/" + selectedEvent.event_id + "/statement", {
        method: "POST", body
      });
      setStatementSummary(data);
      setStatement(null);
      setNotice(data.message || "Bank statement imported.");
      await loadEvents();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function reconcile() {
    if (!selectedEvent) return;
    setBusy("reconcile");
    setError("");
    setNotice("");
    try {
      const data = await apiRequest("/api/events/" + selectedEvent.event_id + "/reconcile", {
        method: "POST"
      });
      setNotice(data.message || "Reconciliation completed.");
      await loadEvents();
      await loadEventData({
        ...selectedEvent,
        total_results: data.total_reconciled
      });
    } catch (err) {
      setError(err.message);
      try {
        const data = await apiRequest("/api/events/" + selectedEvent.event_id + "/results");
        setResults(data.results || []);
      } catch {}
    } finally {
      setBusy("");
    }
  }

  async function openEvent(event) {
    await loadEventData(event);
  }

  function navigate(nextPage) {
    setPage(nextPage);
    setError("");
    setNotice("");
    if (nextPage !== "event") setSelectedEvent(null);
    setSidebarOpen(false);
  }

  const navItems = [
    { id: "overview", label: "Command centre", icon: LayoutDashboard },
    { id: "events", label: "Events & records", icon: History },
    { id: "new", label: "New event", icon: Plus }
  ];

  return (
    <div className="app-shell">
      <aside className={"sidebar " + (sidebarOpen ? "sidebar-open" : "")}>
        <div className="brand-lockup">
          <div className="brand-mark"><ShieldCheck size={23} strokeWidth={2.3} /></div>
          <div><strong>evident<span>pay</span></strong><small>PAYMENT INTELLIGENCE</small></div>
          <button className="mobile-close" onClick={() => setSidebarOpen(false)}><X size={18} /></button>
        </div>

        <div className="workspace-switcher">
          <div className="workspace-avatar">EP</div>
          <div><strong>Organizer workspace</strong><small>Personal workspace</small></div>
          <ChevronDown size={16} />
        </div>

        <div className="nav-caption">WORKSPACE</div>
        <nav className="main-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            return <button key={item.id} className={"nav-item " + (page === item.id || (item.id === "events" && page === "event") ? "active" : "")} onClick={() => item.id === "new" ? startNewEvent() : navigate(item.id)}>
              <Icon size={18} /><span>{item.label}</span>{item.id === "events" && events.length > 0 && <small>{events.length}</small>}
            </button>;
          })}
        </nav>

        <div className="sidebar-spacer" />
        <div className="sidebar-tip">
          <div className="tip-icon"><Sparkles size={17} /></div>
          <strong>Clarity over claims.</strong>
          <p>Only a matching bank credit confirms a payment. Screenshots are supporting evidence.</p>
        </div>
        <div className="sidebar-bottom">
          <div className="connection-indicator"><span /> API connection · localhost</div>
          <div className="sidebar-foot"><ShieldCheck size={15} /> EvidentPay <span>v1.0</span></div>
        </div>
      </aside>

      {sidebarOpen && <button className="mobile-scrim" onClick={() => setSidebarOpen(false)} aria-label="Close navigation" />}

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button>
            <div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} /><strong>{page === "overview" ? "Command centre" : page === "events" ? "Events & records" : page === "new" ? "New event" : selectedEvent?.event_name || "Event details"}</strong></div>
          </div>
          <div className="topbar-actions">
            <div className="system-status"><span /> System operational</div>
            <button className="icon-button notification-trigger" onClick={() => setShowNotifications(!showNotifications)}><Bell size={18} /><i /></button>
            {showNotifications && <div className="notification-popover"><strong>Activity inbox</strong><p>{reviewCount ? reviewCount + " item(s) may need review in the open event." : "You're all caught up. New activity will appear here."}</p></div>}
            <div className="user-chip"><div className="user-avatar">A</div><span>Organizer</span><ChevronDown size={15} /></div>
          </div>
        </header>

        <div className="page-wrap">
          {error && <div className="alert alert-error"><CircleAlert size={17} /><span>{error}</span><button onClick={() => setError("")}><X size={16} /></button></div>}
          {notice && <div className="alert alert-success"><CheckCircle2 size={17} /><span>{notice}</span><button onClick={() => setNotice("")}><X size={16} /></button></div>}

          {page === "overview" && <>
            <section className="welcome-row">
              <div>
                <div className="eyebrow"><span className="eyebrow-dot" /> LIVE OVERVIEW</div>
                <h1>Good morning. <span>Here's your pulse.</span></h1>
                <p className="page-subtitle">One place to track event collections, verify payments and catch exceptions.</p>
              </div>
              <button className="button-primary" onClick={startNewEvent}><Plus size={17} /> Create event <ArrowUpRight size={16} /></button>
            </section>

            <section className="metric-grid">
              <div className="metric-card metric-purple">
                <div className="metric-top"><span>Total events</span><div className="metric-icon"><Wallet size={19} /></div></div>
                <div className="metric-value">{loading ? "—" : events.length}</div>
                <div className="metric-foot"><span className="metric-note">Across your workspace</span><span className="metric-symbol"><Activity size={16} /></span></div>
              </div>
              <div className="metric-card">
                <div className="metric-top"><span>Payment claims</span><div className="metric-icon"><FileImage size={19} /></div></div>
                <div className="metric-value">{loading ? "—" : totalClaims}</div>
                <div className="metric-foot"><span className="metric-note">Screenshots processed</span><span className="metric-symbol"><ArrowUpRight size={16} /></span></div>
              </div>
              <div className="metric-card">
                <div className="metric-top"><span>Reconciled records</span><div className="metric-icon"><BadgeCheck size={19} /></div></div>
                <div className="metric-value">{loading ? "—" : totalResults}</div>
                <div className="metric-foot"><span className="metric-note">Compared with bank credits</span><span className="metric-symbol"><Check size={16} /></span></div>
              </div>
              <div className="metric-card metric-amber">
                <div className="metric-top"><span>Events processed</span><div className="metric-icon"><Zap size={19} /></div></div>
                <div className="metric-value">{loading ? "—" : processedEvents}<small> / {events.length}</small></div>
                <div className="metric-foot"><span className="metric-note">Reconciliation completed</span><span className="metric-symbol"><Clock3 size={16} /></span></div>
              </div>
            </section>

            <section className="command-grid">
              <div className="surface events-surface">
                <div className="surface-heading">
                  <div><div className="eyebrow">YOUR WORKSPACE</div><h2>Recent events</h2><p>Pick up where you left off.</p></div>
                  <button className="button-quiet" onClick={() => navigate("events")}>All events <ArrowRight size={15} /></button>
                </div>
                {loading ? <div className="loading-state"><LoaderCircle className="spin" size={22} /> Loading event data…</div> : events.length === 0 ? <div className="empty-state"><div className="empty-illustration"><CalendarDaysIcon /></div><h3>Your first event starts here</h3><p>Create an event to start collecting and reconciling payment proofs.</p><button className="button-primary" onClick={startNewEvent}><Plus size={16} /> Create your first event</button></div> : <div className="event-list">
                  {events.slice(0, 5).map((event) => <button className="event-row" key={event.event_id} onClick={() => openEvent(event)}>
                    <div className="event-symbol"><Wallet size={18} /></div>
                    <div className="event-main"><strong>{event.event_name}</strong><span>Event #{event.event_id} · {shortDate(event.created_at)}</span></div>
                    <div className="event-count"><strong>{event.total_claims || 0}</strong><span>claims</span></div>
                    <div className="event-count"><strong>{event.total_results || 0}</strong><span>results</span></div>
                    <ChevronRight className="event-chevron" size={18} />
                  </button>)}
                </div>}
              </div>

              <div className="right-rail">
                <div className="surface quick-surface">
                  <div className="surface-heading compact"><div><div className="eyebrow">QUICK ACTIONS</div><h2>Move things forward</h2></div><div className="sparkle-badge"><Zap size={17} /></div></div>
                  <button className="quick-action" onClick={startNewEvent}><div className="quick-icon lavender"><Plus size={18} /></div><div><strong>Create an event</strong><span>Set price and expected headcount</span></div><ArrowUpRight size={16} /></button>
                  <button className="quick-action" onClick={() => navigate("events")}><div className="quick-icon blue"><FileCheck2 size={18} /></div><div><strong>Review payment records</strong><span>Open an event and inspect results</span></div><ArrowUpRight size={16} /></button>
                </div>
                <div className="insight-card">
                  <div className="insight-orb"><Fingerprint size={22} /></div>
                  <div className="eyebrow">VERIFICATION PRINCIPLE</div>
                  <h3>Evidence first.<br />Assumptions never.</h3>
                  <p>A screenshot can make a claim. A matching credit in the recipient's bank statement verifies it.</p>
                  <div className="insight-rule"><span /> BANK-LED RECONCILIATION</div>
                </div>
              </div>
            </section>
          </>}

          {page === "events" && <>
            <section className="welcome-row compact-welcome">
              <div><div className="eyebrow">WORKSPACE RECORDS</div><h1>Events & <span>records.</span></h1><p className="page-subtitle">Every event, its uploaded claims and reconciliation progress.</p></div>
              <button className="button-primary" onClick={startNewEvent}><Plus size={17} /> Create event</button>
            </section>
            <div className="surface records-surface">
              <div className="records-toolbar"><div><h2>All events <span className="count-bubble">{events.length}</span></h2><p>Choose an event to view its payment workflow.</p></div><div className="search-field"><Search size={17} /><input placeholder="Search events…" value={search} onChange={(e) => setSearch(e.target.value)} /></div></div>
              {loading ? <div className="loading-state"><LoaderCircle className="spin" size={22} /> Loading events…</div> : filteredEvents.length === 0 ? <div className="empty-state"><h3>No events found</h3><p>Try another search or create a new event.</p></div> : <div className="table-scroll"><table className="data-table"><thead><tr><th>EVENT</th><th>PRICE</th><th>EXPECTED</th><th>SCREENSHOTS</th><th>STATEMENT ROWS</th><th>RESULTS</th><th>CREATED</th><th /></tr></thead><tbody>{filteredEvents.map((event) => <tr key={event.event_id} onClick={() => openEvent(event)}><td><div className="table-event"><div className="event-symbol small"><Wallet size={16} /></div><div><strong>{event.event_name}</strong><span>EP-{String(event.event_id).padStart(4, "0")}</span></div></div></td><td>{money(event.event_price)}</td><td>{event.expected_participant_count ?? "—"}</td><td>{event.total_claims || 0}</td><td>{event.total_bank_transactions || 0}</td><td><strong>{event.total_results || 0}</strong></td><td>{shortDate(event.created_at)}</td><td><ChevronRight size={17} /></td></tr>)}</tbody></table></div>}
            </div>
          </>}

          {page === "new" && <>
            <section className="welcome-row compact-welcome">
              <div><div className="eyebrow">NEW WORKFLOW</div><h1>Set up your <span>event.</span></h1><p className="page-subtitle">Create the event, add payment proofs and import recipient-side bank data.</p></div>
              <div className="step-indicator"><span className={selectedEvent ? "complete" : "current"}>01</span><i /><span className={selectedEvent ? "current" : ""}>02</span><i /><span>03</span></div>
            </section>
            {!selectedEvent ? <div className="setup-layout">
              <form className="surface setup-form" onSubmit={createEvent}>
                <div className="form-heading"><div className="form-icon"><CalendarDaysIcon /></div><div><h2>Event details</h2><p>These details are used to organize payment claims.</p></div></div>
                <label>Event name<input required maxLength="150" placeholder="e.g. TechFest 2026" value={eventName} onChange={(e) => setEventName(e.target.value)} /></label>
                <div className="form-two"><label>Registration fee (₹)<input required min="1" type="number" step="0.01" value={eventPrice} onChange={(e) => setEventPrice(e.target.value)} /></label><label>Expected participants<input required min="1" type="number" value={participants} onChange={(e) => setParticipants(e.target.value)} /></label></div>
                <div className="form-note"><CircleAlert size={16} /><span>Use the amount each participant is expected to pay. You can upload screenshots after creating the event.</span></div>
                <button className="button-primary wide" type="submit" disabled={busy === "create"}>{busy === "create" ? <LoaderCircle className="spin" size={17} /> : <Plus size={17} />} Create event and continue <ArrowRight size={16} /></button>
              </form>
              <div className="setup-aside"><div className="aside-art"><div className="art-card art-back"><span>PAYMENT RECEIVED</span><strong>₹500.00</strong><small>UPI transaction</small></div><div className="art-card art-front"><div className="art-check"><Check size={18} /></div><span>VERIFICATION READY</span><strong>Evidence matched</strong><small>Bank statement comparison</small></div><div className="art-orbit" /></div><h3>A cleaner way to close the books.</h3><p>Keep screenshots, bank credits and review outcomes tied to one event.</p></div>
            </div> : <div className="workflow-layout">
              <div className="workflow-main">
                <div className="surface workflow-card">
                  <div className="workflow-heading"><div className="step-number">01</div><div><div className="eyebrow">PAYMENT PROOFS</div><h2>Upload screenshots</h2><p>Choose multiple PNG, JPG or WebP files. Maximum 10 MB each.</p></div><div className="workflow-state done"><Check size={15} /> {selectedEvent.total_claims || uploadSummary?.successful || 0} saved</div></div>
                  <label className="drop-zone"><input type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" multiple onChange={(e) => setScreenshots(Array.from(e.target.files || []))} /><div className="drop-icon"><CloudUpload size={25} /></div><strong>Drop screenshots here or <span>browse files</span></strong><small>{screenshots.length ? screenshots.length + " file(s) selected" : "Multiple files · PNG, JPG, WEBP"}</small></label>
                  {screenshots.length > 0 && <div className="selected-files">{screenshots.map((file) => <div key={file.name}><FileImage size={16} /><span>{file.name}</span><small>{(file.size / 1024 / 1024).toFixed(1)} MB</small></div>)}</div>}
                  {uploadSummary && <div className="inline-result"><CheckCircle2 size={16} /> {uploadSummary.successful} successful · {uploadSummary.failed} failed</div>}
                  <div className="workflow-footer"><span>OCR extracts the payment details automatically.</span><button className="button-secondary" disabled={!screenshots.length || busy === "screenshots"} onClick={uploadScreenshots}>{busy === "screenshots" ? <LoaderCircle className="spin" size={16} /> : <Upload size={16} />} Upload screenshots</button></div>
                </div>
                <div className="surface workflow-card">
                  <div className="workflow-heading"><div className="step-number">02</div><div><div className="eyebrow">RECIPIENT-SIDE EVIDENCE</div><h2>Import bank statement</h2><p>Upload the CSV exported from the account that received payments.</p></div><div className="workflow-state"><Banknote size={15} /> CSV required</div></div>
                  <label className="statement-picker"><input type="file" accept=".csv,text/csv" onChange={(e) => setStatement(e.target.files?.[0] || null)} /><div className="statement-icon"><FileSpreadsheet size={23} /></div><div><strong>{statement ? statement.name : "Choose bank statement CSV"}</strong><small>{statement ? (statement.size / 1024).toFixed(0) + " KB selected" : "CSV format · Up to 20 MB"}</small></div><span className="button-outline">Browse</span></label>
                  {statementSummary && <div className="inline-result"><CheckCircle2 size={16} /> {statementSummary.total_transactions} transactions imported · {statementSummary.credit_transactions} credits</div>}
                  <div className="workflow-footer"><span>Only incoming credits can confirm a payment.</span><button className="button-secondary" disabled={!statement || busy === "statement"} onClick={uploadStatement}>{busy === "statement" ? <LoaderCircle className="spin" size={16} /> : <Upload size={16} />} Import statement</button></div>
                </div>
                <div className="surface reconcile-strip">
                  <div className="reconcile-icon"><Zap size={20} /></div><div><strong>Ready to reconcile?</strong><p>Compare screenshot claims against the imported bank credits.</p></div><button className="button-primary" onClick={reconcile} disabled={busy === "reconcile" || !(selectedEvent.total_claims || uploadSummary?.successful) || !(selectedEvent.total_bank_transactions || statementSummary?.total_transactions)}>{busy === "reconcile" ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />} Run reconciliation</button>
                </div>
              </div>
              <aside className="workflow-side">
                <div className="surface event-summary"><div className="eyebrow">ACTIVE EVENT</div><h3>{selectedEvent.event_name}</h3><div className="event-id">EP-{String(selectedEvent.event_id).padStart(4, "0")}</div><div className="summary-line"><span>Registration fee</span><strong>{money(selectedEvent.event_price)}</strong></div><div className="summary-line"><span>Expected participants</span><strong>{selectedEvent.expected_participant_count ?? "—"}</strong></div><div className="summary-line"><span>Screenshots uploaded</span><strong>{selectedEvent.total_claims || uploadSummary?.successful || 0}</strong></div><div className="summary-line"><span>Statement transactions</span><strong>{selectedEvent.total_bank_transactions || statementSummary?.total_transactions || 0}</strong></div><button className="text-button" onClick={() => setSelectedEvent(null)}>Edit event setup <ArrowRight size={14} /></button></div>
                <div className="trust-note"><ShieldCheck size={18} /><div><strong>Verification, not guesswork</strong><p>Without a matching bank credit, a claim remains unverified. Screenshot analysis is supplementary evidence only.</p></div></div>
                {results.length > 0 && <button className="button-secondary wide" onClick={() => openEvent(selectedEvent)}>View reconciliation results <ArrowRight size={15} /></button>}
              </aside>
            </div>}
          </>}

          {page === "event" && selectedEvent && <>
            <section className="welcome-row compact-welcome">
              <div><div className="eyebrow">EVENT EP-{String(selectedEvent.event_id).padStart(4, "0")}</div><h1>{selectedEvent.event_name}<span>.</span></h1><p className="page-subtitle">{money(selectedEvent.event_price)} registration · {selectedEvent.expected_participant_count ?? "—"} expected participants · Created {shortDate(selectedEvent.created_at)}</p></div>
              <div className="heading-actions"><button className="button-secondary" onClick={() => { setPage("new"); setNotice(""); }}>Open workflow <ArrowRight size={15} /></button><button className="icon-button" onClick={() => loadEventData(selectedEvent)}><RefreshCw size={17} /></button></div>
            </section>
            <div className="event-detail-metrics"><div className="surface mini-metric"><span>Payment screenshots</span><strong>{claims.length}</strong></div><div className="surface mini-metric"><span>Reconciliation results</span><strong>{results.length}</strong></div><div className="surface mini-metric"><span>Matched</span><strong>{results.filter((item) => String(item.status).toLowerCase().includes("match")).length}</strong></div><div className="surface mini-metric"><span>Needs attention</span><strong>{results.filter((item) => statusTone(item.status) === "warning").length}</strong></div></div>
            <div className="surface records-surface result-surface">
              <div className="records-toolbar"><div><div className="eyebrow">RECONCILIATION OUTPUT</div><h2>Payment results</h2><p>Each screenshot claim compared with recipient-side bank data.</p></div><button className="button-secondary" onClick={() => { setPage("new"); setNotice(""); }}>Continue workflow <ArrowRight size={15} /></button></div>
              {results.length > 0 ? <div className="table-scroll"><table className="data-table"><thead><tr><th>SCREENSHOT</th><th>CLAIMED AMOUNT</th><th>UTR</th><th>BANK CREDIT</th><th>STATUS</th><th>REASONS</th></tr></thead><tbody>{results.map((result) => <tr key={result.result_id}><td><strong>{result.screenshot_filename || "Claim #" + result.claim_id}</strong><span className="cell-sub">Claim #{result.claim_id}</span></td><td>{money(result.screenshot_amount)}</td><td className="mono">{result.screenshot_utr || "—"}</td><td>{result.bank_transaction ? money(result.bank_transaction.credit) : "—"}</td><td><StatusPill value={result.status} /></td><td className="reason-cell">{(result.reasons || []).join(", ") || "—"}</td></tr>)}</tbody></table></div> : <div className="empty-state compact-empty"><div className="empty-illustration"><FileCheck2 size={25} /></div><h3>No reconciliation results yet</h3><p>Upload screenshots and a bank statement, then run reconciliation to see verified matches and exceptions.</p><button className="button-primary" onClick={() => { setPage("new"); setNotice(""); }}>Continue verification <ArrowRight size={15} /></button></div>}
            </div>
            <div className="surface claims-surface"><div className="records-toolbar"><div><h2>Extracted claims <span className="count-bubble">{claims.length}</span></h2><p>Fields read from uploaded payment screenshots.</p></div></div>{claims.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>FILE</th><th>AMOUNT</th><th>UTR</th><th>TRANSACTION DATE</th><th>SENDER</th><th>OCR</th></tr></thead><tbody>{claims.map((claim) => <tr key={claim.claim_id}><td><strong>{claim.screenshot_filename}</strong></td><td>{money(claim.amount)}</td><td className="mono">{claim.utr || "—"}</td><td>{shortDate(claim.transaction_date)}</td><td>{claim.sender_name || "—"}</td><td>{claim.needs_review ? <StatusPill value="Needs review" /> : <StatusPill value="Extracted" />}</td></tr>)}</tbody></table></div> : <div className="empty-inline">No screenshots have been uploaded for this event.</div>}</div>
          </>}
          <footer className="page-footer"><span>© 2026 EvidentPay</span><span><ShieldCheck size={14} /> Built around evidence-led payment verification</span></footer>
        </div>
      </main>
    </div>
  );
}

function CalendarDaysIcon() {
  return <div className="calendar-glyph"><span /><span /><span /><span /></div>;
}

export default App;
