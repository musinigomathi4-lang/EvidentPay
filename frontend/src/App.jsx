import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownLeft, ArrowRight, ArrowUpRight, BadgeCheck, Banknote,
  Check, CheckCircle2, ChevronLeft, CircleAlert, Clock3, FileImage,
  FileSpreadsheet, Fingerprint, LoaderCircle, Plus, RefreshCw,
  Search, ShieldCheck, Sparkles, Upload, Wallet, X, Zap
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
  return new Intl.NumberFormat("en-IN", {
    style: "currency", currency: "INR", maximumFractionDigits: 0
  }).format(Number(value || 0));
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
  if (value === "matched" || value === "verified") return "verified";
  if (value.includes("duplicate") || value.includes("review") || value.includes("mismatch") || value.includes("unverified") || value.includes("potentially_altered")) return "review";
  if (value.includes("outside") || value.includes("not_found") || value === "unmatched") return "pending";
  return "plain";
}

function StatusTag({ value }) {
  return <span className={"status-tag " + statusTone(value)}><i />{String(value || "Pending").replaceAll("_", " ")}</span>;
}

function EvidenceDetails({ result }) {
  const checks = result.checks || {};
  const paired = checks.analysis_type === "paired_image_forensics";
  const comparison = checks.reference_comparison || {};
  const referenceSearch = checks.reference_search || {};
  const ocr = checks.ocr_comparison?.comparisons || {};
  const images = checks.analysis_images || {};
  const metadata = checks.metadata_analysis || {};
  const noise = checks.noise_analysis || {};
  const reasons = result.reasons || [];
  const formatValue = (value) => value === null || value === undefined || value === "" ? "—" :
    Array.isArray(value) ? value.join(" × ") : typeof value === "object" ? JSON.stringify(value) : String(value);

  return (
    <article className="evidence-card" key={result.result_id}>
      <div className="evidence-card-heading">
        <div>
          <span className="eyebrow">{paired ? "REFERENCE COMPARISON" : "INDEPENDENT IMAGE SCREENING"}</span>
          <h3>{result.screenshot_filename || "Screenshot claim"}</h3>
        </div>
        <StatusTag value={result.status} />
      </div>

      <div className={"reference-banner " + (paired ? "reference-found" : "reference-missing")}>
        <div className="reference-banner-icon">{paired ? <CheckCircle2 size={18}/> : <Search size={18}/>}</div>
        <div>
          <strong>{paired ? "A likely genuine reference was found" : "No credible reference was found"}</strong>
          <p>{paired
            ? "The uploaded image was compared with " + (referenceSearch.filename || comparison.original_filename || "a reference image") + "."
            : (referenceSearch.reason || "This screenshot was screened on its own. Direct image comparison was not possible.")}</p>
          <small>{referenceSearch.candidate_count ?? 0} visual candidate(s) shortlisted</small>
        </div>
      </div>

      {paired ? <>
        <div className="evidence-subheading"><strong>Image comparison</strong><span>Signals to support manual review — not proof by themselves</span></div>
        <div className="evidence-metrics">
          <div><span>pHASH DISTANCE</span><strong>{comparison.phash_distance ?? "—"}</strong><small>Lower usually means more visually similar</small></div>
          <div><span>CHANGED PIXELS</span><strong>{comparison.changed_pixel_percent ?? "—"}%</strong><small>Pixels differing after alignment</small></div>
          <div><span>EDGE DIFFERENCE</span><strong>{comparison.edge_difference_percent ?? "—"}%</strong><small>Difference in detected boundaries</small></div>
          <div><span>CHANGED REGIONS</span><strong>{comparison.regions_detected ?? "—"}</strong><small>Local areas marked for inspection</small></div>
        </div>
        <div className="evidence-ocr">
          <div className="evidence-subheading"><strong>Payment field comparison</strong><span>Text read from both images</span></div>
          <div className="evidence-ocr-grid">
            {Object.entries(ocr).map(([field, item]) => (
              <div key={field}>
                <span>{item.label || field}</span>
                <b className={item.matches === false ? "different" : item.matches === true ? "same" : ""}>{(item.status || "NOT_COMPARABLE").replaceAll("_", " ")}</b>
                <small>Reference: {item.original_value ?? "Not read"}</small>
                <small>Uploaded: {item.modified_value ?? "Not read"}</small>
              </div>
            ))}
          </div>
        </div>
      </> : <>
        <div className="evidence-subheading"><strong>Single-image checks</strong><span>These checks cannot confirm whether editing occurred</span></div>
        <div className="evidence-metrics">
          <div><span>ELA MEAN DIFFERENCE</span><strong>{checks.ela_analysis?.mean_difference ?? "—"}</strong><small>Recompression difference signal</small></div>
          <div><span>ELA MAX DIFFERENCE</span><strong>{checks.ela_analysis?.max_difference ?? "—"}</strong><small>Highest local difference signal</small></div>
          <div><span>IMAGE FORMAT</span><strong>{metadata.format || "—"}</strong><small>{formatValue(metadata.dimensions)}</small></div>
          <div><span>EMBEDDED SOFTWARE</span><strong>{metadata.software || "Not found"}</strong><small>{(metadata.detected_editors || []).length ? "Editor keyword detected" : "No editor keyword detected"}</small></div>
        </div>
        {Object.keys(noise).length > 0 && <div className="noise-summary">
          <strong>Noise consistency measurements</strong>
          <div>{Object.entries(noise).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><b>{formatValue(value)}</b></div>)}</div>
        </div>}
      </>}

      {reasons.length > 0 && <div className="indicator-list">
        <strong>Why this image was flagged</strong>
        <ul>{reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul>
      </div>}

      <div className="evidence-images">
        {Object.entries(images).map(([label, path]) => (
          <a href={API + path} target="_blank" rel="noreferrer" key={label}>
            <img src={API + path} alt={label.replaceAll("_", " ")} loading="lazy" />
            <span>{label.replaceAll("_", " ")}</span>
          </a>
        ))}
      </div>
      <p className="evidence-disclaimer">Important: screenshot analysis can identify differences and suspicious signals, but it cannot prove that a payment was received. A matching incoming bank credit is still required to confirm payment.</p>
      {checks.limitations && <p className="evidence-note">{checks.limitations}</p>}
    </article>
  );
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
  const [reviewMode, setReviewMode] = useState("bank");

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
    ((event.event_name || "") + " " + event.event_id).toLowerCase().includes(search.toLowerCase())
  ), [events, search]);

  const totalClaims = events.reduce((sum, event) => sum + Number(event.total_claims || 0), 0);
  const totalResults = events.reduce((sum, event) => sum + Number(event.total_results || 0), 0);
  const processedEvents = events.filter((event) => Number(event.total_results || 0) > 0).length;
  const matchedCount = results.filter((item) => String(item.status).toLowerCase() === "matched").length;
  const attentionCount = results.filter((item) => statusTone(item.status) === "review" || String(item.status).toLowerCase().includes("unverified")).length;
  const screenshotOnlyResults = results.some((item) => ["single_image_forensics", "paired_image_forensics"].includes(item.checks?.analysis_type));

  function startNewEvent() {
    setEventName("");
    setEventPrice("500");
    setParticipants("100");
    setScreenshots([]);
    setStatement(null);
    setUploadSummary(null);
    setStatementSummary(null);
    setReviewMode("bank");
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

  async function uploadSelectedFiles() {
    if (!selectedEvent) throw new Error("Create an event first.");
    let uploadedClaims = Number(selectedEvent.total_claims || 0);
    let importedTransactions = Number(selectedEvent.total_bank_transactions || 0);

    if (screenshots.length) {
      const body = new FormData();
      screenshots.forEach((file) => body.append("files", file));
      const data = await apiRequest("/api/events/" + selectedEvent.event_id + "/screenshots", {
        method: "POST", body
      });
      setUploadSummary(data);
      uploadedClaims += Number(data.successful || 0);
      setScreenshots([]);
      if (data.failed) {
        const failed = (data.results || []).filter((item) => item.status === "failed");
        if (failed.length) throw new Error(
          data.successful + " screenshot(s) processed, " + data.failed +
          " failed: " + failed.map((item) => item.filename + " — " + item.error).join("; ")
        );
      }
      if (!data.successful && screenshots.length) throw new Error("No screenshots could be processed.");
    }

    if (reviewMode === "bank" && statement) {
      const body = new FormData();
      body.append("file", statement);
      const data = await apiRequest("/api/events/" + selectedEvent.event_id + "/statement", {
        method: "POST", body
      });
      setStatementSummary(data);
      importedTransactions += Number(data.total_transactions || 0);
      setStatement(null);
    }

    setSelectedEvent((current) => current ? {
      ...current,
      total_claims: uploadedClaims,
      total_bank_transactions: importedTransactions
    } : current);
    return { uploadedClaims, importedTransactions };
  }

  async function runVerification() {
    if (!selectedEvent) return;
    if (!screenshots.length && !Number(selectedEvent.total_claims || 0)) {
      setError("Add at least one payment screenshot to begin.");
      return;
    }
    if (reviewMode === "bank" && !statement && !Number(selectedEvent.total_bank_transactions || 0)) {
      setError("Choose a bank statement, or use the No bank statement option below.");
      return;
    }

    setBusy("verification");
    setError("");
    setNotice("");
    try {
      const { uploadedClaims, importedTransactions } = await uploadSelectedFiles();
      const endpoint = reviewMode === "bank"
        ? "/api/events/" + selectedEvent.event_id + "/reconcile"
        : "/api/events/" + selectedEvent.event_id + "/analyze-without-statement";
      const data = await apiRequest(endpoint, { method: "POST" });
      const [claimData, resultData] = await Promise.all([
        apiRequest("/api/events/" + selectedEvent.event_id + "/claims"),
        apiRequest("/api/events/" + selectedEvent.event_id + "/results")
      ]);
      setClaims(claimData.claims || []);
      setResults(resultData.results || []);
      setSelectedEvent((current) => current ? {
        ...current,
        total_claims: uploadedClaims,
        total_bank_transactions: importedTransactions,
        total_results: data.total_reconciled || data.total_analyzed || 0
      } : current);
      await loadEvents();
      setNotice(reviewMode === "bank"
        ? "Verification complete. " + (data.summary?.MATCHED || data.summary?.matched || 0) + " payment(s) matched against bank credits."
        : "Screenshot-only review complete. These claims remain UNVERIFIED because no bank statement was supplied.");
      setPage("event");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  function go(nextPage) {
    setPage(nextPage);
    setError("");
    setNotice("");
    if (nextPage !== "event" && nextPage !== "new") setSelectedEvent(null);
  }

  const pageTitle = page === "overview" ? "Workspace" : page === "events" ? "Event register" : page === "new" ? (selectedEvent ? "Verification desk" : "Create event") : "Event intelligence";
  const navItem = (id, label, Icon, count) => (
    <button className={"side-nav-item " + (page === id || (id === "events" && page === "event") ? "active" : "")} onClick={() => go(id)}>
      <Icon size={17}/><span>{label}</span>{count !== undefined && <small>{count}</small>}
    </button>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand-lockup" onClick={() => go("overview")} aria-label="EvidentPay home">
          <span className="brand-mark"><Fingerprint size={21}/></span>
          <span><b>EVIDENTPAY</b><small>PAYMENT INTELLIGENCE</small></span>
        </button>
        <div className="side-label">WORKSPACE</div>
        <nav className="side-navigation">
          {navItem("overview","Dashboard",Wallet)}
          {navItem("events","Events",FileSpreadsheet,events.length)}
        </nav>
        <div className="sidebar-bottom">
          <div className="side-security"><ShieldCheck size={18}/><div><b>Evidence-led checks</b><small>Claims are not confirmations.</small></div></div>
          <button className="side-new-button" onClick={startNewEvent}><Plus size={17}/> Create event</button>
          <div className="sidebar-foot">EVIDENTPAY <span>·</span> 2026</div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><ArrowRight size={13}/><b>{pageTitle}</b></div>
          <div className="topbar-right"><span className="live-indicator"><i/> API CONNECTION</span><button className="topbar-create" onClick={startNewEvent}><Plus size={15}/> New event</button></div>
        </header>

        <main className="page-wrap">
          {(error || notice) && <div className={"notice-bar " + (error ? "is-error" : "is-success")}>
            {error ? <CircleAlert size={17}/> : <CheckCircle2 size={17}/>}<span>{error || notice}</span>
            <button onClick={() => { setError(""); setNotice(""); }} aria-label="Dismiss message"><X size={16}/></button>
          </div>}

          {page === "overview" && <>
            <section className="dashboard-intro">
              <div><span className="eyebrow">PAYMENT OPERATIONS / OVERVIEW</span><h1>Know what came in.<br/><em>Not just what was sent.</em></h1><p>One workspace for payment claims, screenshot analysis and incoming-credit reconciliation.</p></div>
              <button className="primary-action" onClick={startNewEvent}><Plus size={17}/> Start a verification</button>
              <div className="intro-orbit orbit-one"/><div className="intro-orbit orbit-two"/><div className="intro-stamp"><Fingerprint size={30}/><span>TRACE<br/>THE PROOF</span></div>
            </section>

            <section className="stats-grid">
              <div className="stat-card"><span>EVENTS</span><strong>{loading?"—":events.length}</strong><small>Created in workspace</small><div className="stat-icon"><Wallet size={18}/></div></div>
              <div className="stat-card"><span>PAYMENT CLAIMS</span><strong>{loading?"—":totalClaims}</strong><small>Uploaded screenshots</small><div className="stat-icon"><FileImage size={18}/></div></div>
              <div className="stat-card"><span>ANALYSIS RECORDS</span><strong>{loading?"—":totalResults}</strong><small>Checks completed</small><div className="stat-icon"><Fingerprint size={18}/></div></div>
              <div className="stat-card"><span>EVENTS IN PROGRESS</span><strong>{loading?"—":events.filter(e=>Number(e.total_results||0)===0).length}</strong><small>Awaiting a verification run</small><div className="stat-icon"><Clock3 size={18}/></div></div>
            </section>

            <section className="dashboard-grid">
              <div className="panel event-panel">
                <div className="panel-heading"><div><span className="eyebrow">RECENT ACTIVITY</span><h2>Your events</h2><p>Pick up where you left off.</p></div><button className="text-action" onClick={()=>go("events")}>View register <ArrowRight size={15}/></button></div>
                {loading ? <div className="empty-state"><LoaderCircle className="spin" size={22}/> Loading workspace…</div> : events.length===0 ? <div className="empty-state"><div className="empty-symbol"><Wallet size={25}/></div><h3>Your workspace is ready.</h3><p>Create your first event to start collecting and checking payment evidence.</p><button className="primary-action" onClick={startNewEvent}><Plus size={16}/> Create first event</button></div> :
                  <div className="activity-list">{events.slice(0,6).map((event,index)=><button className="activity-row" key={event.event_id} onClick={()=>loadEventData(event)}><span className="activity-number">{String(index+1).padStart(2,"0")}</span><span className="activity-avatar">{(event.event_name||"E").slice(0,1).toUpperCase()}</span><span className="activity-copy"><b>{event.event_name}</b><small>EP-{String(event.event_id).padStart(4,"0")} · {shortDate(event.created_at)}</small></span><span className="activity-count"><b>{event.total_claims||0}</b><small>CLAIMS</small></span><span className="activity-count"><b>{event.total_results||0}</b><small>RESULTS</small></span><ArrowUpRight size={16}/></button>)}</div>}
              </div>
              <aside className="insight-panel"><div className="insight-top"><span className="eyebrow">THE CORE PRINCIPLE</span><Fingerprint size={25}/></div><h2>A screenshot is a claim.<br/><em>A credit is confirmation.</em></h2><p>Visual checks can flag suspicious evidence. Only a matching incoming transaction confirms that money reached the recipient account.</p><div className="insight-rule"><span/><span/><span/></div><small>SCREENSHOT ANALYSIS + BANK RECONCILIATION</small></aside>
            </section>
          </>}

          {page === "events" && <>
            <section className="page-heading-row"><div><span className="eyebrow">WORKSPACE / EVENT REGISTER</span><h1>All events</h1><p>Every event, claim and verification run in one place.</p></div><button className="primary-action" onClick={startNewEvent}><Plus size={16}/> Create event</button></section>
            <section className="panel register-panel"><div className="register-toolbar"><div><b>{events.length.toString().padStart(2,"0")}</b><span>EVENTS IN REGISTER</span></div><label className="search-field"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search events or IDs"/></label></div>
              {loading?<div className="empty-state"><LoaderCircle className="spin" size={22}/> Loading events…</div>:filteredEvents.length===0?<div className="empty-state"><h3>No matching events</h3><p>Try another search or create a new event.</p><button className="primary-action" onClick={startNewEvent}><Plus size={16}/> New event</button></div>:
              <div className="event-grid">{filteredEvents.map(event=><button className="event-tile" key={event.event_id} onClick={()=>loadEventData(event)}><div className="tile-top"><span className="tile-avatar">{(event.event_name||"E").slice(0,1).toUpperCase()}</span><StatusTag value={Number(event.total_results||0)>0?"Processed":"Pending"}/></div><h3>{event.event_name}</h3><small>EP-{String(event.event_id).padStart(4,"0")} · {shortDate(event.created_at)}</small><div className="tile-stats"><span><b>{money(event.event_price)}</b><small>ENTRY FEE</small></span><span><b>{event.expected_participant_count??"—"}</b><small>EXPECTED</small></span><span><b>{event.total_claims||0}</b><small>CLAIMS</small></span></div><div className="tile-bottom">Open event <ArrowUpRight size={15}/></div></button>)}</div>}
            </section>
          </>}

          {page === "new" && <>
            {!selectedEvent ? <section className="setup-layout"><div className="setup-aside"><span className="eyebrow">NEW EVENT / SETUP</span><h1>Start with<br/><em>the details.</em></h1><p>Set up the event once. Then bring in participant screenshots and the recipient-side statement when you're ready.</p><div className="setup-steps"><span><b>01</b> Event details</span><span><b>02</b> Evidence upload</span><span><b>03</b> Review results</span></div></div><form className="panel setup-form" onSubmit={createEvent}><div className="panel-heading"><div><span className="eyebrow">EVENT CONFIGURATION</span><h2>Event details</h2><p>These values help validate the claims you receive.</p></div><span className="step-count">01 / 03</span></div><label>Event name<input required maxLength="150" placeholder="e.g. TechFest 2026" value={eventName} onChange={e=>setEventName(e.target.value)}/></label><div className="form-pair"><label>Payment per participant (₹)<input required min="1" type="number" step="0.01" value={eventPrice} onChange={e=>setEventPrice(e.target.value)}/></label><label>Expected participants<input required min="1" type="number" value={participants} onChange={e=>setParticipants(e.target.value)}/></label></div><div className="expected-collection"><span>EXPECTED COLLECTION</span><strong>{money((Number(eventPrice)||0)*(Number(participants)||0))}</strong><small>{participants||0} participants × {money(eventPrice)}</small></div><button className="primary-action wide" type="submit" disabled={busy==="create"}>{busy==="create"?<LoaderCircle className="spin" size={17}/>:<Plus size={17}/>} Create event <ArrowRight size={16}/></button></form></section> :
              <section className="verification-layout"><div className="workspace-event-head"><button className="back-link" onClick={()=>go("events")}><ChevronLeft size={16}/> Event register</button><span className="eyebrow">EVENT EP-{String(selectedEvent.event_id).padStart(4,"0")}</span><h1>{selectedEvent.event_name}</h1><p>{money(selectedEvent.event_price)} per participant · {selectedEvent.expected_participant_count??"—"} expected</p><div className="expected-total"><span>EXPECTED COLLECTION</span><strong>{money(Number(selectedEvent.event_price||0)*Number(selectedEvent.expected_participant_count||0))}</strong></div></div>
                <div className="upload-columns"><section className="panel upload-section"><div className="upload-title"><span>01</span><div><span className="eyebrow">PARTICIPANT EVIDENCE</span><h3>Payment screenshots</h3><p>Upload multiple screenshots together. Every image is screened independently; reference comparison is added only when a credible original is found.</p></div></div><label className="drop-zone"><input type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" multiple onChange={e=>setScreenshots(Array.from(e.target.files||[]))}/><div className="drop-icon"><FileImage size={23}/></div><strong>{screenshots.length?screenshots.length+" file(s) ready":"Drop payment screenshots here"}</strong><span>or <u>browse your device</u></span><small>PNG · JPG · WEBP · MULTIPLE FILES</small></label>{screenshots.length>0&&<div className="selected-files">{screenshots.map(file=><div key={file.name}><FileImage size={15}/><span>{file.name}</span><small>{(file.size/1024/1024).toFixed(1)} MB</small></div>)}</div>}{uploadSummary&&<div className="upload-result"><CheckCircle2 size={16}/>{uploadSummary.successful} processed · {uploadSummary.failed} failed</div>}<div className="upload-actions"><span>{selectedEvent.total_claims||uploadSummary?.successful||0} claims stored</span><span className="file-ready">{screenshots.length?screenshots.length+" new selected":"Ready to upload"}</span></div></section>
                <section className="panel upload-section"><div className="upload-title"><span>02</span><div><span className="eyebrow">RECIPIENT ACCOUNT</span><h3>Bank statement</h3><p>Import the account that received the payments. CSV and text-based PDF statements are supported.</p></div></div><label className="statement-zone"><input type="file" accept=".csv,.pdf,text/csv,application/pdf" onChange={e=>setStatement(e.target.files?.[0]||null)}/><FileSpreadsheet size={27}/><span><strong>{statement?statement.name:"Choose a bank statement"}</strong><small>{statement?(statement.size/1024).toFixed(0)+" KB selected":"CSV or PDF · up to 20 MB"}</small></span><b>Browse</b></label>{statementSummary&&<div className="upload-result"><CheckCircle2 size={16}/>{statementSummary.total_transactions} transactions · {statementSummary.credit_transactions} credits imported</div>}<div className="upload-actions"><span>{selectedEvent.total_bank_transactions||statementSummary?.total_transactions||0} rows imported</span><span className="file-ready">{statement?"Statement selected":"Optional for image review"}</span></div></section></div>
                <section className="review-mode-panel"><div><span className="eyebrow">CHOOSE THE VERIFICATION WORKFLOW</span><h3>What evidence do you have?</h3><p>Image screening always runs. Bank reconciliation is an additional check when you provide a statement.</p></div><div className="mode-options"><button className={reviewMode==="screenshots"?"mode-option selected":"mode-option"} onClick={()=>setReviewMode("screenshots")}><Fingerprint size={18}/><span><b>Screenshot analysis</b><small>Review images without bank data</small></span>{reviewMode==="screenshots"&&<CheckCircle2 size={17}/>}</button><button className={reviewMode==="bank"?"mode-option selected":"mode-option"} onClick={()=>setReviewMode("bank")}><Banknote size={18}/><span><b>Bank reconciliation</b><small>Screen images and match incoming credits</small></span>{reviewMode==="bank"&&<CheckCircle2 size={17}/>}</button></div></section>
                <div className="verification-footer"><div><span className="eyebrow">READY TO RUN</span><strong>{reviewMode==="bank"?"Image screening + bank reconciliation":"Independent screenshot screening"}</strong><small>Unmatched or suspicious items remain available for manual review.</small></div><button className="primary-action" onClick={runVerification} disabled={busy==="verification"||(!screenshots.length&&!selectedEvent.total_claims)||(reviewMode==="bank"&&!statement&&!selectedEvent.total_bank_transactions)}>{busy==="verification"?<><LoaderCircle className="spin" size={16}/> Analysing evidence…</>:<><Zap size={16}/> Run analysis <ArrowRight size={16}/></>}</button></div>
                {results.length>0&&<button className="text-action results-link" onClick={()=>loadEventData(selectedEvent)}>View latest results <ArrowUpRight size={15}/></button>}
              </section>}
          </>}

          {page === "event" && selectedEvent && <>
            <section className="report-hero"><button className="back-link" onClick={()=>go("events")}><ChevronLeft size={16}/> Event register</button><div className="report-hero-row"><div><span className="eyebrow">EVENT REPORT / EP-{String(selectedEvent.event_id).padStart(4,"0")}</span><h1>{selectedEvent.event_name}</h1><p>{money(selectedEvent.event_price)} entry fee · {selectedEvent.expected_participant_count??"—"} expected · Created {shortDate(selectedEvent.created_at)}</p></div><button className="secondary-action" onClick={()=>{setPage("new");setNotice("");}}><Upload size={15}/> Open workflow</button></div><div className="report-stats"><div><small>CLAIMS</small><b>{claims.length}</b></div><div><small>RESULTS</small><b>{results.length}</b></div><div><small>MATCHED CREDITS</small><b>{matchedCount}</b></div><div><small>NEEDS REVIEW</small><b>{attentionCount}</b></div></div></section>
            <section className="panel report-section"><div className="panel-heading"><div><span className="eyebrow">{screenshotOnlyResults?"SCREENSHOT INTEGRITY REVIEW":"BANK-LED VERIFICATION"}</span><h2>{screenshotOnlyResults?"Screenshot assessments":"Reconciliation results"}</h2><p>Open an item to inspect its evidence, extracted fields and review reasons.</p></div><button className="icon-action" onClick={()=>loadEventData(selectedEvent)} aria-label="Refresh results"><RefreshCw size={17}/></button></div>
              {results.length?<div className="report-table-wrap"><table className="report-table"><thead><tr><th>SCREENSHOT</th>{screenshotOnlyResults?<><th>ASSESSMENT</th><th>FINDINGS</th><th>BANK STATUS</th></>:<><th>CLAIMED</th><th>UTR</th><th>BANK CREDIT</th><th>STATUS</th><th>REASONS</th></>}</tr></thead><tbody>{results.map(result=><tr key={result.result_id}><td><strong>{result.screenshot_filename||"Claim #"+result.claim_id}</strong><small>Claim #{result.claim_id}</small></td>{screenshotOnlyResults?<><td><StatusTag value={result.status}/></td><td>{(result.reasons||[]).join(", ")||"No clear editing indicators"}</td><td>Not checked</td></>:<><td>{money(result.screenshot_amount)}</td><td className="mono">{result.screenshot_utr||"—"}</td><td>{result.bank_transaction?money(result.bank_transaction.credit):"—"}</td><td><StatusTag value={result.status}/></td><td>{(result.reasons||[]).join(", ")||"—"}</td></>}</tr>)}</tbody></table></div>:<div className="empty-state"><div className="empty-symbol"><Banknote size={25}/></div><h3>No results yet</h3><p>Upload evidence and run the verification workflow.</p><button className="primary-action" onClick={()=>setPage("new")}>Continue workflow <ArrowRight size={16}/></button></div>}
            </section>
            {screenshotOnlyResults&&results.length>0&&<section className="panel report-section"><div className="panel-heading"><div><span className="eyebrow">IMAGE FORENSICS</span><h2>Evidence breakdown</h2><p>Independent screening is the default. Reference comparison is additional evidence when available.</p></div></div><div className="evidence-card-list">{results.map(result=><EvidenceDetails result={result} key={result.result_id}/>)}</div></section>}
            <section className="panel report-section"><div className="panel-heading"><div><span className="eyebrow">OCR / EXTRACTED DATA</span><h2>Payment claims <span className="inline-count">{claims.length}</span></h2><p>Values read from participant screenshots. Missing fields should be reviewed.</p></div></div>{claims.length?<div className="report-table-wrap"><table className="report-table"><thead><tr><th>FILE</th><th>AMOUNT</th><th>UTR</th><th>DATE</th><th>SENDER</th><th>EXTRACTION</th></tr></thead><tbody>{claims.map(claim=><tr key={claim.claim_id}><td>{claim.screenshot_filename}</td><td>{money(claim.amount)}</td><td className="mono">{claim.utr||"—"}</td><td>{shortDate(claim.transaction_date)}</td><td>{claim.sender_name||"—"}</td><td><StatusTag value={claim.needs_review?"Needs review":"Extracted"}/></td></tr>)}</tbody></table></div>:<div className="empty-state compact">No screenshots uploaded yet.</div>}</section>
          </>}
          <footer className="site-footer"><span>EVIDENTPAY / PAYMENT INTELLIGENCE</span><span>SCREENING ≠ PAYMENT CONFIRMATION <ShieldCheck size={15}/></span></footer>
        </main>
      </div>
    </div>
  );
}

export default App;
