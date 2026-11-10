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

  const pageTitle = page === "overview" ? "Overview" : page === "events" ? "Events" : page === "new" ? (selectedEvent ? "Verification" : "New event") : "Event report";
  const navItem = (id,label,Icon,count) => <button className={"top-nav-link "+(page===id||(id==="events"&&page==="event")?"active":"")} onClick={()=>go(id)}><Icon size={15}/>{label}{count!==undefined&&<small>{count}</small>}</button>;

  return (
    <div className="app-shell">
      <header className="global-header">
        <button className="brand-lockup" onClick={()=>go("overview")}><span className="brand-mark"><Fingerprint size={20}/></span><span><b>EVIDENTPAY</b><small>PAYMENT INTELLIGENCE</small></span></button>
        <nav className="top-navigation">{navItem("overview","Overview",Wallet)}{navItem("events","Event register",FileSpreadsheet,events.length)}</nav>
        <div className="header-actions"><span className="live-indicator"><i/> SYSTEM CONNECTED</span><button className="topbar-create" onClick={startNewEvent}><Plus size={15}/> New event</button></div>
      </header>
      <main className="page-wrap">
        <div className="page-context"><span>WORKSPACE</span><span>/</span><b>{pageTitle}</b><span className="context-spacer"/><span className="context-date">EVIDENCE-LED PAYMENT REVIEW</span></div>
        {(error||notice)&&<div className={"notice-bar "+(error?"is-error":"is-success")}>{error?<CircleAlert size={17}/>:<CheckCircle2 size={17}/>}<span>{error||notice}</span><button onClick={()=>{setError("");setNotice("");}} aria-label="Dismiss message"><X size={16}/></button></div>}

        {page==="overview"&&<>
          <section className="editorial-hero">
            <div className="hero-copy"><span className="eyebrow">THE EVENT PAYMENT WORKSPACE</span><h1>Proof, not<br/><em>promises.</em></h1><p>Bring payment screenshots and incoming credits into one clear review process. Spot inconsistencies. Keep the evidence visible.</p><button className="primary-action" onClick={startNewEvent}><Plus size={16}/> Start a verification <ArrowUpRight size={15}/></button></div>
            <div className="hero-art"><div className="hero-index">01 <span>/ EVIDENCE CONTROL</span></div><div className="hero-art-main"><div className="art-ring ring-a"/><div className="art-ring ring-b"/><div className="art-center"><Fingerprint size={54}/><span>TRACE<br/>THE PROOF</span></div><div className="art-tag tag-top">SCREENSHOT<br/>ANALYSIS</div><div className="art-tag tag-bottom">BANK CREDIT<br/>RECONCILIATION</div></div><div className="hero-art-foot"><span>INDEPENDENT SCREENING</span><span>REFERENCE COMPARISON</span><span>TRANSACTION MATCHING</span></div></div>
          </section>
          <section className="metric-ribbon"><div><span>EVENTS CREATED</span><b>{loading?"—":events.length.toString().padStart(2,"0")}</b></div><div><span>PAYMENT CLAIMS</span><b>{loading?"—":totalClaims.toString().padStart(2,"0")}</b></div><div><span>ANALYSIS RECORDS</span><b>{loading?"—":totalResults.toString().padStart(2,"0")}</b></div><div><span>AWAITING REVIEW</span><b>{loading?"—":events.filter(e=>Number(e.total_results||0)===0).length.toString().padStart(2,"0")}</b></div></section>
          <section className="workflow-story"><div className="workflow-story-heading"><span className="eyebrow">HOW EVIDENTPAY WORKS</span><h2>From payment claim<br/>to <em>clearer evidence.</em></h2><p>Three connected checks. Each one adds context without pretending a screenshot alone proves payment.</p></div><div className="workflow-story-steps"><div className="story-step"><span className="story-step-number">01</span><div className="story-step-icon"><FileImage size={22}/></div><div><b>Screen the screenshot</b><p>Every uploaded image gets independent checks for visual and data inconsistencies.</p></div><small>ALWAYS RUNS</small></div><div className="story-step"><span className="story-step-number">02</span><div className="story-step-icon"><Fingerprint size={22}/></div><div><b>Compare when possible</b><p>A credible reference adds a side-by-side comparison. Unknown images are not skipped.</p></div><small>WHEN AVAILABLE</small></div><div className="story-step"><span className="story-step-number">03</span><div className="story-step-icon"><Banknote size={22}/></div><div><b>Confirm the bank credit</b><p>Recipient-side transactions help establish whether the money actually arrived.</p></div><small>WITH STATEMENT</small></div></div></section>
          <section className="overview-lower"><div className="ledger-panel"><div className="section-heading"><div><span className="eyebrow">YOUR WORKSPACE</span><h2>Recent events</h2><p>Jump back into an event or open the full register.</p></div><button className="text-action" onClick={()=>go("events")}>All events <ArrowRight size={15}/></button></div>
            {loading?<div className="empty-state"><LoaderCircle className="spin" size={22}/> Loading workspace…</div>:events.length===0?<div className="empty-state"><div className="empty-symbol"><Wallet size={24}/></div><h3>Your first event starts here.</h3><p>Create an event to begin reviewing payment evidence.</p><button className="primary-action" onClick={startNewEvent}><Plus size={16}/> Create event</button></div>:<div className="ledger-list"><div className="ledger-head"><span>EVENT</span><span>CREATED</span><span>CLAIMS</span><span>RESULTS</span><span/></div>{events.slice(0,7).map((event,index)=><button className="ledger-row" key={event.event_id} onClick={()=>loadEventData(event)}><span className="ledger-event"><i>{String(index+1).padStart(2,"0")}</i><b>{event.event_name}</b><small>EP-{String(event.event_id).padStart(4,"0")}</small></span><span>{shortDate(event.created_at)}</span><span>{event.total_claims||0}</span><span>{event.total_results||0}</span><ArrowUpRight size={16}/></button>)}</div>}
          </div><aside className="manifesto-panel"><span className="eyebrow">THE EVIDENCE RULE</span><h2>A screenshot<br/>is a <em>claim.</em></h2><div className="manifesto-divider"/><h2>A bank credit<br/>is <em>confirmation.</em></h2><p>Visual analysis can identify suspicious signals. A matching incoming transaction confirms receipt of funds.</p><span className="manifesto-mark">EP / 01</span></aside></section>
        </>}

        {page==="events"&&<>
          <section className="page-title-row"><div><span className="eyebrow">WORKSPACE / REGISTER</span><h1>Event register<span className="title-period">.</span></h1><p>A running record of every event and its verification activity.</p></div><button className="primary-action" onClick={startNewEvent}><Plus size={16}/> Create event</button></section>
          <section className="ledger-panel register-ledger"><div className="register-toolbar"><div><b>{events.length.toString().padStart(2,"0")}</b><span>EVENTS ON FILE</span></div><label className="search-field"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Find an event or ID"/></label></div>
          {loading?<div className="empty-state"><LoaderCircle className="spin" size={22}/> Loading events…</div>:filteredEvents.length===0?<div className="empty-state"><h3>No events found.</h3><p>Try a different search or create a new event.</p><button className="primary-action" onClick={startNewEvent}><Plus size={16}/> New event</button></div>:<div className="ledger-list"><div className="ledger-head register-head"><span>EVENT</span><span>ENTRY FEE</span><span>EXPECTED</span><span>CLAIMS</span><span>STATUS</span></div>{filteredEvents.map(event=><button className="ledger-row register-row" key={event.event_id} onClick={()=>loadEventData(event)}><span className="ledger-event"><i>EP-{String(event.event_id).padStart(4,"0")}</i><b>{event.event_name}</b><small>Created {shortDate(event.created_at)}</small></span><span>{money(event.event_price)}</span><span>{event.expected_participant_count??"—"}</span><span>{event.total_claims||0}</span><span><StatusTag value={Number(event.total_results||0)>0?"Processed":"Pending"}/></span></button>)}</div>}
          </section>
        </>}

        {page==="new"&&<>
          {!selectedEvent?<section className="new-event-layout"><div className="new-event-intro"><span className="eyebrow">NEW EVENT / CONFIGURATION</span><h1>Set the<br/><em>ground rules.</em></h1><p>Tell EvidentPay what participants should pay. You can add screenshots and recipient-side bank data once the event is created.</p><div className="step-rail"><span className="step-current">01 <b>Event details</b></span><span>02 <b>Upload evidence</b></span><span>03 <b>Review findings</b></span></div></div><form className="event-form" onSubmit={createEvent}><div className="form-heading"><span className="eyebrow">EVENT PROFILE</span><span className="form-step">STEP 01 / 03</span></div><h2>What are we verifying?</h2><label>Event name<input required maxLength="150" placeholder="e.g. TechFest 2026" value={eventName} onChange={e=>setEventName(e.target.value)}/></label><div className="form-pair"><label>Payment per participant (₹)<input required min="1" type="number" step="0.01" value={eventPrice} onChange={e=>setEventPrice(e.target.value)}/></label><label>Expected participants<input required min="1" type="number" value={participants} onChange={e=>setParticipants(e.target.value)}/></label></div><div className="expected-collection"><span>PROJECTED COLLECTION</span><strong>{money((Number(eventPrice)||0)*(Number(participants)||0))}</strong><small>{participants||0} participants × {money(eventPrice)}</small></div><button className="primary-action wide" type="submit" disabled={busy==="create"}>{busy==="create"?<LoaderCircle className="spin" size={17}/>:<Plus size={17}/>} Create event <ArrowRight size={16}/></button></form></section>:
          <section className="verification-layout"><div className="verification-title"><button className="back-link" onClick={()=>go("events")}><ChevronLeft size={16}/> Event register</button><span className="eyebrow">EVENT EP-{String(selectedEvent.event_id).padStart(4,"0")}</span><h1>{selectedEvent.event_name}</h1><p>{money(selectedEvent.event_price)} per participant <span>·</span> {selectedEvent.expected_participant_count??"—"} expected</p></div>
            <div className="upload-columns"><section className="upload-module"><div className="module-heading"><span>01</span><div><span className="eyebrow">PARTICIPANT EVIDENCE</span><h3>Payment screenshots</h3><p>Every image is screened independently. Reference comparison is additional evidence, when available.</p></div></div><label className="drop-zone"><input type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" multiple onChange={e=>setScreenshots(Array.from(e.target.files||[]))}/><div className="drop-icon"><FileImage size={23}/></div><strong>{screenshots.length?screenshots.length+" file(s) ready":"Drop screenshots here"}</strong><span>or <u>browse your device</u></span><small>PNG · JPG · WEBP · MULTIPLE FILES</small></label>{screenshots.length>0&&<div className="selected-files">{screenshots.map(file=><div key={file.name}><FileImage size={15}/><span>{file.name}</span><small>{(file.size/1024/1024).toFixed(1)} MB</small></div>)}</div>}{uploadSummary&&<div className="upload-result"><CheckCircle2 size={16}/>{uploadSummary.successful} processed · {uploadSummary.failed} failed</div>}<div className="upload-actions"><span>{selectedEvent.total_claims||uploadSummary?.successful||0} claims stored</span><span>{screenshots.length?screenshots.length+" selected":"Ready to upload"}</span></div></section>
            <section className="upload-module"><div className="module-heading"><span>02</span><div><span className="eyebrow">RECIPIENT ACCOUNT</span><h3>Bank statement</h3><p>Optional. Add the account that received the payments to reconcile incoming credits.</p></div></div><label className="statement-zone"><input type="file" accept=".csv,.pdf,text/csv,application/pdf" onChange={e=>setStatement(e.target.files?.[0]||null)}/><FileSpreadsheet size={27}/><span><strong>{statement?statement.name:"Choose a bank statement"}</strong><small>{statement?(statement.size/1024).toFixed(0)+" KB selected":"CSV or PDF · up to 20 MB"}</small></span><b>Browse</b></label>{statementSummary&&<div className="upload-result"><CheckCircle2 size={16}/>{statementSummary.total_transactions} transactions · {statementSummary.credit_transactions} credits imported</div>}<div className="upload-actions"><span>{selectedEvent.total_bank_transactions||statementSummary?.total_transactions||0} rows imported</span><span>{statement?"Statement selected":"Optional for image review"}</span></div></section></div>
            <section className="workflow-choice"><div><span className="eyebrow">ANALYSIS WORKFLOW</span><h3>Choose the checks to run</h3><p>Screenshot screening always runs. Bank reconciliation adds a recipient-side transaction check.</p></div><div className="mode-options"><button className={reviewMode==="screenshots"?"mode-option selected":"mode-option"} onClick={()=>setReviewMode("screenshots")}><Fingerprint size={18}/><span><b>Screenshot analysis</b><small>Review images independently</small></span>{reviewMode==="screenshots"&&<CheckCircle2 size={17}/>}</button><button className={reviewMode==="bank"?"mode-option selected":"mode-option"} onClick={()=>setReviewMode("bank")}><Banknote size={18}/><span><b>Bank reconciliation</b><small>Screen images + match credits</small></span>{reviewMode==="bank"&&<CheckCircle2 size={17}/>}</button></div></section>
            <div className="run-strip"><div><span className="eyebrow">READY WHEN YOU ARE</span><strong>{reviewMode==="bank"?"Image screening + bank reconciliation":"Independent screenshot screening"}</strong><small>Unmatched or suspicious items remain available for review.</small></div><button className="primary-action" onClick={runVerification} disabled={busy==="verification"||(!screenshots.length&&!selectedEvent.total_claims)||(reviewMode==="bank"&&!statement&&!selectedEvent.total_bank_transactions)}>{busy==="verification"?<><LoaderCircle className="spin" size={16}/> Analysing evidence…</>:<><Zap size={16}/> Run analysis <ArrowRight size={16}/></>}</button></div>
            {results.length>0&&<button className="text-action results-link" onClick={()=>loadEventData(selectedEvent)}>View latest results <ArrowUpRight size={15}/></button>}
          </section>}
        </>}

        {page==="event"&&selectedEvent&&<>
          <section className="report-masthead"><button className="back-link" onClick={()=>go("events")}><ChevronLeft size={16}/> Event register</button><div className="report-mast-row"><div><span className="eyebrow">EVENT REPORT / EP-{String(selectedEvent.event_id).padStart(4,"0")}</span><h1>{selectedEvent.event_name}<span className="title-period">.</span></h1><p>{money(selectedEvent.event_price)} entry fee · {selectedEvent.expected_participant_count??"—"} expected · Created {shortDate(selectedEvent.created_at)}</p></div><button className="secondary-action" onClick={()=>{setPage("new");setNotice("");}}><Upload size={15}/> Open workflow</button></div><div className="report-stats"><div><small>CLAIMS</small><b>{claims.length}</b></div><div><small>RESULTS</small><b>{results.length}</b></div><div><small>MATCHED CREDITS</small><b>{matchedCount}</b></div><div><small>NEEDS REVIEW</small><b>{attentionCount}</b></div></div></section>
          <section className="ledger-panel report-section"><div className="section-heading"><div><span className="eyebrow">{screenshotOnlyResults?"SCREENSHOT INTEGRITY REVIEW":"BANK-LED VERIFICATION"}</span><h2>{screenshotOnlyResults?"Screenshot assessments":"Reconciliation results"}</h2><p>Open an item to inspect evidence, extracted fields and review reasons.</p></div><button className="icon-action" onClick={()=>loadEventData(selectedEvent)} aria-label="Refresh results"><RefreshCw size={17}/></button></div>
          {results.length?<div className="report-table-wrap"><table className="report-table"><thead><tr><th>SCREENSHOT</th>{screenshotOnlyResults?<><th>ASSESSMENT</th><th>FINDINGS</th><th>BANK STATUS</th></>:<><th>CLAIMED</th><th>UTR</th><th>BANK CREDIT</th><th>STATUS</th><th>REASONS</th></>}</tr></thead><tbody>{results.map(result=><tr key={result.result_id}><td><strong>{result.screenshot_filename||"Claim #"+result.claim_id}</strong><small>Claim #{result.claim_id}</small></td>{screenshotOnlyResults?<><td><StatusTag value={result.status}/></td><td>{(result.reasons||[]).join(", ")||"No clear editing indicators"}</td><td>Not checked</td></>:<><td>{money(result.screenshot_amount)}</td><td className="mono">{result.screenshot_utr||"—"}</td><td>{result.bank_transaction?money(result.bank_transaction.credit):"—"}</td><td><StatusTag value={result.status}/></td><td>{(result.reasons||[]).join(", ")||"—"}</td></>}</tr>)}</tbody></table></div>:<div className="empty-state"><div className="empty-symbol"><Banknote size={25}/></div><h3>No results yet</h3><p>Upload evidence and run the verification workflow.</p><button className="primary-action" onClick={()=>setPage("new")}>Continue workflow <ArrowRight size={16}/></button></div>}
          </section>
          {screenshotOnlyResults&&results.length>0&&<section className="ledger-panel report-section"><div className="section-heading"><div><span className="eyebrow">IMAGE FORENSICS</span><h2>Evidence breakdown</h2><p>Independent screening is the default. Reference comparison is extra evidence when available.</p></div></div><div className="evidence-card-list">{results.map(result=><EvidenceDetails result={result} key={result.result_id}/>)}</div></section>}
          <section className="ledger-panel report-section"><div className="section-heading"><div><span className="eyebrow">OCR / EXTRACTED DATA</span><h2>Payment claims <span className="inline-count">{claims.length}</span></h2><p>Values read from participant screenshots. Missing fields should be reviewed.</p></div></div>{claims.length?<div className="report-table-wrap"><table className="report-table"><thead><tr><th>FILE</th><th>AMOUNT</th><th>UTR</th><th>DATE</th><th>SENDER</th><th>EXTRACTION</th></tr></thead><tbody>{claims.map(claim=><tr key={claim.claim_id}><td>{claim.screenshot_filename}</td><td>{money(claim.amount)}</td><td className="mono">{claim.utr||"—"}</td><td>{shortDate(claim.transaction_date)}</td><td>{claim.sender_name||"—"}</td><td><StatusTag value={claim.needs_review?"Needs review":"Extracted"}/></td></tr>)}</tbody></table></div>:<div className="empty-state compact">No screenshots uploaded yet.</div>}</section>
        </>}
        <footer className="site-footer"><span>EVIDENTPAY — PAYMENT INTELLIGENCE</span><span>SCREENING ≠ PAYMENT CONFIRMATION <ShieldCheck size={14}/></span></footer>
      </main>
    </div>
  );
}

export default App;
