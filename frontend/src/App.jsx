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
  if (value === "matched" || value === "verified") return "good";
  if (value.includes("duplicate") || value.includes("review") || value.includes("mismatch")) return "warning";
  if (value.includes("outside") || value.includes("not_found") || value === "unmatched") return "muted";
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
    { id: "overview", label: "Overview", icon: LayoutDashboard },
    { id: "events", label: "Events", icon: History },
    { id: "new", label: "New event", icon: Plus }
  ];

  const matchedCount = results.filter((item) => String(item.status).toLowerCase() === "matched").length;
  const attentionCount = results.filter((item) => statusTone(item.status) === "warning").length;

  return (
    <div className="ep-app">
      <aside className={"ep-rail " + (sidebarOpen ? "is-open" : "")}>
        <button className="ep-brand" onClick={() => navigate("overview")} aria-label="EvidentPay home">
          <span className="ep-brand-mark"><ShieldCheck size={22} /></span>
          <span className="ep-brand-word">ep<span>.</span></span>
        </button>
        <div className="ep-rail-label">WORKSPACE</div>
        <nav className="ep-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = page === item.id || (item.id === "events" && page === "event");
            return <button key={item.id} className={active ? "active" : ""} onClick={() => item.id === "new" ? startNewEvent() : navigate(item.id)} title={item.label}>
              <Icon size={19} /><span>{item.label}</span>
              {item.id === "events" && events.length > 0 && <i>{events.length}</i>}
            </button>;
          })}
        </nav>
        <div className="ep-rail-bottom">
          <div className="ep-live-dot" title="API workspace" />
          <span>LOCAL</span>
        </div>
      </aside>

      {sidebarOpen && <button className="ep-scrim" onClick={() => setSidebarOpen(false)} aria-label="Close menu" />}
      <main className="ep-main">
        <header className="ep-topbar">
          <div className="ep-top-left">
            <button className="ep-mobile-menu" onClick={() => setSidebarOpen(!sidebarOpen)}><Menu size={20} /></button>
            <div className="ep-crumb">EVIDENTPAY <span>/</span> {page === "overview" ? "OVERVIEW" : page === "events" ? "EVENT REGISTER" : page === "new" ? "NEW WORKFLOW" : "EVENT DETAIL"}</div>
          </div>
          <div className="ep-top-right">
            <span className="ep-api-state"><i /> API CONNECTED</span>
            <div className="ep-avatar">O</div>
            <span className="ep-user-label">Organizer</span>
          </div>
        </header>

        <div className="ep-content">
          {(error || notice) && <div className={"ep-message " + (error ? "error" : "success")}>
            {error ? <CircleAlert size={17} /> : <CheckCircle2 size={17} />}
            <span>{error || notice}</span>
            <button onClick={() => { setError(""); setNotice(""); }}><X size={16} /></button>
          </div>}

          {page === "overview" && <>
            <section className="ep-page-heading">
              <div><div className="ep-kicker">YOUR PAYMENT OPERATIONS</div><h1>Overview<span className="ep-period">.</span></h1><p>One workspace for event collections, payment evidence and reconciliation.</p></div>
              <button className="ep-button primary" onClick={startNewEvent}><Plus size={17} /> Create event</button>
            </section>

            <section className="ep-hero">
              <div className="ep-hero-copy">
                <div className="ep-hero-label"><span /> EVIDENCE-LED VERIFICATION</div>
                <h2>Know what arrived.<br /><em>Not just what was claimed.</em></h2>
                <p>Compare submitted payment screenshots with incoming credits from the recipient-side bank statement.</p>
                <button className="ep-hero-button" onClick={startNewEvent}>Start a verification <ArrowUpRight size={16} /></button>
              </div>
              <div className="ep-hero-graphic" aria-hidden="true">
                <div className="ep-orbit orbit-one" /><div className="ep-orbit orbit-two" />
                <div className="ep-float-card"><div className="ep-float-top"><span>PAYMENT RECORD</span><CheckCircle2 size={17} /></div><strong>₹500.00</strong><div className="ep-float-line"><i /><i /><i /></div><small>BANK CREDIT MATCHED</small></div>
                <div className="ep-float-stamp"><ShieldCheck size={23} /><span>VERIFIED<br/>BY EVIDENCE</span></div>
              </div>
              <div className="ep-hero-index">01 <span>/</span> 03</div>
            </section>

            <section className="ep-stat-grid">
              <div className="ep-stat"><div className="ep-stat-head">EVENTS <CalendarDaysIcon /></div><strong>{loading ? "—" : events.length}</strong><small>Created in workspace</small></div>
              <div className="ep-stat"><div className="ep-stat-head">SCREENSHOT CLAIMS <FileImage size={16} /></div><strong>{loading ? "—" : totalClaims}</strong><small>Payment proofs received</small></div>
              <div className="ep-stat"><div className="ep-stat-head">RECONCILIATION RECORDS <Activity size={16} /></div><strong>{loading ? "—" : totalResults}</strong><small>Compared with bank data</small></div>
              <div className="ep-stat"><div className="ep-stat-head">PROCESSED EVENTS <BadgeCheck size={16} /></div><strong>{loading ? "—" : processedEvents}<small className="ep-stat-total"> / {events.length}</small></strong><small>Reconciliation completed</small></div>
            </section>

            <section className="ep-section-head"><div><div className="ep-kicker">RECENT ACTIVITY</div><h2>Events in your workspace</h2></div><button className="ep-text-button" onClick={() => navigate("events")}>View event register <ArrowRight size={15} /></button></section>
            <section className="ep-event-panel">
              {loading ? <div className="ep-empty"><LoaderCircle className="spin" size={22} /> Loading your events…</div> : events.length === 0 ? <div className="ep-empty"><div className="ep-empty-icon"><Wallet size={24} /></div><h3>Your workspace is ready.</h3><p>Create your first event to start collecting and verifying payments.</p><button className="ep-button primary" onClick={startNewEvent}><Plus size={16} /> Create first event</button></div> :
                <div className="ep-recent-list">{events.slice(0,5).map((event,index) => <button className="ep-recent-row" key={event.event_id} onClick={() => openEvent(event)}>
                  <span className="ep-row-index">{String(index+1).padStart(2,"0")}</span><span className="ep-event-monogram">{(event.event_name || "E").slice(0,1).toUpperCase()}</span>
                  <span className="ep-event-title"><strong>{event.event_name}</strong><small>EP-{String(event.event_id).padStart(4,"0")} · {shortDate(event.created_at)}</small></span>
                  <span className="ep-row-metric"><strong>{event.total_claims || 0}</strong><small>CLAIMS</small></span><span className="ep-row-metric"><strong>{event.total_results || 0}</strong><small>RESULTS</small></span><span className="ep-row-arrow"><ArrowUpRight size={18}/></span>
                </button>)}</div>}
            </section>
            <div className="ep-footnote"><ShieldCheck size={15}/> A matching incoming bank credit is the confirmation signal. Screenshot analysis is supplementary only.</div>
          </>}

          {page === "events" && <>
            <section className="ep-page-heading"><div><div className="ep-kicker">WORKSPACE INDEX</div><h1>Event register<span className="ep-period">.</span></h1><p>Browse every event and its payment processing progress.</p></div><button className="ep-button primary" onClick={startNewEvent}><Plus size={17}/> Create event</button></section>
            <section className="ep-table-panel">
              <div className="ep-table-toolbar"><div><strong>{events.length} <span>EVENTS</span></strong><small>All registered events</small></div><label className="ep-search"><Search size={17}/><input value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="Find an event…"/></label></div>
              {loading ? <div className="ep-empty"><LoaderCircle className="spin" size={22}/> Loading events…</div> : filteredEvents.length === 0 ? <div className="ep-empty"><h3>No matching events</h3><p>Try a different search or create a new event.</p></div> :
                <div className="ep-table-scroll"><table className="ep-table"><thead><tr><th>EVENT</th><th>REGISTRATION</th><th>EXPECTED</th><th>CLAIMS</th><th>BANK ROWS</th><th>RESULTS</th><th>CREATED</th><th></th></tr></thead><tbody>{filteredEvents.map(event=><tr key={event.event_id} onClick={()=>openEvent(event)}><td><div className="ep-table-event"><span>{(event.event_name||"E").slice(0,1).toUpperCase()}</span><div><strong>{event.event_name}</strong><small>EP-{String(event.event_id).padStart(4,"0")}</small></div></div></td><td>{money(event.event_price)}</td><td>{event.expected_participant_count ?? "—"}</td><td>{event.total_claims || 0}</td><td>{event.total_bank_transactions || 0}</td><td><b>{event.total_results || 0}</b></td><td>{shortDate(event.created_at)}</td><td><ArrowUpRight size={16}/></td></tr>)}</tbody></table></div>}
            </section>
          </>}

          {page === "new" && <>
            <section className="ep-page-heading"><div><div className="ep-kicker">PAYMENT WORKFLOW / {selectedEvent ? "02" : "01"}</div><h1>{selectedEvent ? "Collect & reconcile" : "Create an event"}<span className="ep-period">.</span></h1><p>{selectedEvent ? "Add screenshots and the recipient-side bank statement, then reconcile." : "Set the event details before collecting payment evidence."}</p></div>{selectedEvent && <div className="ep-event-tag"><span className="ep-live-dot"/> ACTIVE · EP-{String(selectedEvent.event_id).padStart(4,"0")}</div>}</section>
            {!selectedEvent ? <div className="ep-create-layout">
              <form className="ep-form-panel" onSubmit={createEvent}>
                <div className="ep-form-title"><span>01</span><div><h2>Event configuration</h2><p>Define the collection before importing any payment claims.</p></div></div>
                <label className="ep-field">EVENT NAME<input required maxLength="150" placeholder="e.g. TechFest 2026" value={eventName} onChange={e=>setEventName(e.target.value)}/></label>
                <div className="ep-field-grid"><label className="ep-field">REGISTRATION FEE (₹)<input required min="1" type="number" step="0.01" value={eventPrice} onChange={e=>setEventPrice(e.target.value)}/></label><label className="ep-field">EXPECTED PARTICIPANTS<input required min="1" type="number" value={participants} onChange={e=>setParticipants(e.target.value)}/></label></div>
                <div className="ep-form-note"><CircleAlert size={17}/> Use the exact amount each participant is expected to pay.</div>
                <button className="ep-button primary ep-submit" type="submit" disabled={busy==="create"}>{busy==="create" ? <LoaderCircle className="spin" size={17}/> : <Plus size={17}/>} Create event <ArrowRight size={16}/></button>
              </form>
              <aside className="ep-create-aside"><div className="ep-kicker">THE PROCESS</div><h2>From payment claim<br/>to confirmed credit.</h2><div className="ep-process-step"><span>01</span><div><strong>Collect proof</strong><small>Read payment details from screenshots.</small></div></div><div className="ep-process-step"><span>02</span><div><strong>Import bank data</strong><small>Load incoming credits from a CSV statement.</small></div></div><div className="ep-process-step"><span>03</span><div><strong>Reconcile</strong><small>Match claims and flag exceptions for review.</small></div></div></aside>
            </div> : <div className="ep-workspace">
              <section className="ep-work-main">
                <div className="ep-upload-panel"><div className="ep-panel-heading"><span className="ep-step">01</span><div><div className="ep-kicker">INPUT / SCREENSHOTS</div><h2>Payment proofs</h2><p>Upload multiple PNG, JPG or WebP screenshots · 10 MB max each.</p></div><span className="ep-step-state">{selectedEvent.total_claims || uploadSummary?.successful || 0} SAVED</span></div>
                  <label className="ep-drop"><input type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" multiple onChange={e=>setScreenshots(Array.from(e.target.files||[]))}/><CloudUpload size={25}/><strong>{screenshots.length ? screenshots.length+" file(s) selected" : "Choose screenshots to upload"}</strong><small>Drag files here or browse from your device</small></label>
                  {screenshots.length>0 && <div className="ep-file-list">{screenshots.map(file=><div key={file.name}><FileImage size={15}/><span>{file.name}</span><small>{(file.size/1024/1024).toFixed(1)} MB</small></div>)}</div>}
                  {uploadSummary && <div className="ep-inline-note"><CheckCircle2 size={16}/>{uploadSummary.successful} successful · {uploadSummary.failed} failed</div>}
                  <div className="ep-panel-footer"><span>OCR extracts amount, UTR and sender details.</span><button className="ep-button secondary" disabled={!screenshots.length||busy==="screenshots"} onClick={uploadScreenshots}>{busy==="screenshots"?<LoaderCircle className="spin" size={16}/>:<Upload size={16}/>} Upload files</button></div>
                </div>
                <div className="ep-upload-panel"><div className="ep-panel-heading"><span className="ep-step">02</span><div><div className="ep-kicker">INPUT / BANK STATEMENT</div><h2>Recipient-side statement</h2><p>Import the CSV from the account that received participant payments.</p></div><span className="ep-step-state">{selectedEvent.total_bank_transactions || statementSummary?.total_transactions || 0} ROWS</span></div>
                  <label className="ep-statement-pick"><input type="file" accept=".csv,text/csv" onChange={e=>setStatement(e.target.files?.[0]||null)}/><FileSpreadsheet size={23}/><span><strong>{statement ? statement.name : "Select bank statement CSV"}</strong><small>{statement ? (statement.size/1024).toFixed(0)+" KB selected" : "CSV file · 20 MB max"}</small></span><b>Browse</b></label>
                  {statementSummary && <div className="ep-inline-note"><CheckCircle2 size={16}/>{statementSummary.total_transactions} transactions · {statementSummary.credit_transactions} credits imported</div>}
                  <div className="ep-panel-footer"><span>Only incoming credits can verify a claim.</span><button className="ep-button secondary" disabled={!statement||busy==="statement"} onClick={uploadStatement}>{busy==="statement"?<LoaderCircle className="spin" size={16}/>:<Upload size={16}/>} Import CSV</button></div>
                </div>
                <div className="ep-reconcile-panel"><div><div className="ep-kicker">FINAL STEP</div><h2>Run reconciliation</h2><p>Compare every extracted claim against available bank credits.</p></div><button className="ep-button dark" onClick={reconcile} disabled={busy==="reconcile"||!(selectedEvent.total_claims||uploadSummary?.successful)||!(selectedEvent.total_bank_transactions||statementSummary?.total_transactions)}>{busy==="reconcile"?<LoaderCircle className="spin" size={16}/>:<Zap size={16}/>} Reconcile payments <ArrowRight size={16}/></button></div>
              </section>
              <aside className="ep-work-aside"><div className="ep-event-card"><div className="ep-kicker">CURRENT EVENT</div><h3>{selectedEvent.event_name}</h3><span className="ep-event-code">EP-{String(selectedEvent.event_id).padStart(4,"0")}</span><div className="ep-event-fact"><span>Registration fee</span><strong>{money(selectedEvent.event_price)}</strong></div><div className="ep-event-fact"><span>Expected headcount</span><strong>{selectedEvent.expected_participant_count ?? "—"}</strong></div><div className="ep-event-fact"><span>Screenshots</span><strong>{selectedEvent.total_claims || uploadSummary?.successful || 0}</strong></div><div className="ep-event-fact"><span>Statement rows</span><strong>{selectedEvent.total_bank_transactions || statementSummary?.total_transactions || 0}</strong></div><button className="ep-text-button" onClick={()=>setSelectedEvent(null)}>Edit event details <ArrowRight size={14}/></button></div><div className="ep-trust-card"><ShieldCheck size={19}/><div><strong>Verification boundary</strong><p>A screenshot is a claim, not confirmation. Without a matching bank credit, a payment remains unverified.</p></div></div>{results.length>0&&<button className="ep-button secondary ep-full" onClick={()=>openEvent(selectedEvent)}>View results <ArrowRight size={15}/></button>}</aside>
            </div>}
          </>}

          {page === "event" && selectedEvent && <>
            <section className="ep-page-heading"><div><div className="ep-kicker">EVENT DETAIL / EP-{String(selectedEvent.event_id).padStart(4,"0")}</div><h1>{selectedEvent.event_name}<span className="ep-period">.</span></h1><p>{money(selectedEvent.event_price)} registration · {selectedEvent.expected_participant_count ?? "—"} expected · Created {shortDate(selectedEvent.created_at)}</p></div><div className="ep-heading-actions"><button className="ep-button secondary" onClick={()=>{setPage("new");setNotice("");}}>Open workflow <ArrowRight size={15}/></button><button className="ep-icon-button" onClick={()=>loadEventData(selectedEvent)}><RefreshCw size={17}/></button></div></section>
            <section className="ep-detail-stats"><div><small>SCREENSHOT CLAIMS</small><strong>{claims.length}</strong></div><div><small>RECONCILIATION RESULTS</small><strong>{results.length}</strong></div><div><small>MATCHED</small><strong>{matchedCount}</strong></div><div><small>NEEDS ATTENTION</small><strong>{attentionCount}</strong></div></section>
            <section className="ep-table-panel ep-results-panel"><div className="ep-section-head"><div><div className="ep-kicker">BANK-LED VERIFICATION</div><h2>Reconciliation results</h2><p>Claim details compared against recipient-side credits.</p></div><button className="ep-button secondary" onClick={()=>{setPage("new");setNotice("");}}>Continue workflow</button></div>
              {results.length ? <div className="ep-table-scroll"><table className="ep-table"><thead><tr><th>SCREENSHOT</th><th>CLAIMED</th><th>UTR</th><th>BANK CREDIT</th><th>STATUS</th><th>REASONS</th></tr></thead><tbody>{results.map(result=><tr key={result.result_id}><td><strong>{result.screenshot_filename||"Claim #"+result.claim_id}</strong><small className="ep-subline">Claim #{result.claim_id}</small></td><td>{money(result.screenshot_amount)}</td><td className="ep-mono">{result.screenshot_utr||"—"}</td><td>{result.bank_transaction?money(result.bank_transaction.credit):"—"}</td><td><StatusPill value={result.status}/></td><td>{(result.reasons||[]).join(", ")||"—"}</td></tr>)}</tbody></table></div> : <div className="ep-empty"><div className="ep-empty-icon"><FileCheck2 size={24}/></div><h3>No results yet</h3><p>Upload screenshots and a bank statement, then run reconciliation.</p><button className="ep-button primary" onClick={()=>{setPage("new");setNotice("");}}>Continue workflow <ArrowRight size={15}/></button></div>}
            </section>
            <section className="ep-table-panel ep-claims-panel"><div className="ep-section-head"><div><div className="ep-kicker">OCR OUTPUT</div><h2>Extracted claims <span className="ep-count">{claims.length}</span></h2><p>Information read from submitted screenshots.</p></div></div>
              {claims.length ? <div className="ep-table-scroll"><table className="ep-table"><thead><tr><th>FILE</th><th>AMOUNT</th><th>UTR</th><th>TRANSACTION DATE</th><th>SENDER</th><th>EXTRACTION</th></tr></thead><tbody>{claims.map(claim=><tr key={claim.claim_id}><td>{claim.screenshot_filename}</td><td>{money(claim.amount)}</td><td className="ep-mono">{claim.utr||"—"}</td><td>{shortDate(claim.transaction_date)}</td><td>{claim.sender_name||"—"}</td><td><StatusPill value={claim.needs_review?"Needs review":"Extracted"}/></td></tr>)}</tbody></table></div> : <div className="ep-empty slim">No screenshots have been uploaded for this event.</div>}
            </section>
          </>}
          <footer className="ep-footer"><span>EVIDENTPAY © 2026</span><span>PAYMENT VERIFICATION, GROUNDED IN EVIDENCE <ShieldCheck size={14}/></span></footer>
        </div>
      </main>
    </div>
  );
}

function CalendarDaysIcon() {
  return <div className="calendar-glyph"><span /><span /><span /><span /></div>;
}

export default App;
