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
  const screenshotOnlyResults = results.some((item) => item.checks?.analysis_type === "single_image_forensics");

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
        total_results: data.total_reconciled || 0
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

  const pageTitle = page === "overview" ? "Overview" : page === "events" ? "All events" : page === "new" ? (selectedEvent ? "Verification workspace" : "Create an event") : "Event report";

  return (
    <div className="app-shell">
      <header className="masthead">
        <button className="wordmark" onClick={() => go("overview")} aria-label="EvidentPay home">
          <span className="wordmark-symbol"><span /><span /><span /></span>
          <span>EVIDENT<span className="wordmark-light">PAY</span></span>
        </button>
        <nav className="main-nav" aria-label="Main navigation">
          <button className={page === "overview" ? "selected" : ""} onClick={() => go("overview")}>Overview</button>
          <button className={page === "events" || page === "event" ? "selected" : ""} onClick={() => go("events")}>Events <span className="nav-count">{events.length}</span></button>
        </nav>
        <div className="masthead-right"><span className="connection"><i /> Workspace live</span><button className="create-shortcut" onClick={startNewEvent}><Plus size={16}/> New event</button></div>
      </header>

      <main className="page-wrap">
        <div className="page-meta">
          <div><span className="eyebrow">EVIDENTPAY / PAYMENT OPERATIONS</span><h1>{pageTitle}</h1></div>
          <span className="date-mark">RECIPIENT-SIDE VERIFICATION <ArrowDownLeft size={14}/></span>
        </div>

        {(error || notice) && <div className={"notice-bar " + (error ? "is-error" : "is-success")}>
          {error ? <CircleAlert size={17}/> : <CheckCircle2 size={17}/>}<span>{error || notice}</span>
          <button onClick={() => { setError(""); setNotice(""); }} aria-label="Dismiss message"><X size={16}/></button>
        </div>}

        {page === "overview" && <>
          <section className="opening">
            <div className="opening-copy">
              <div className="eyebrow lime-label"><span/> THE PAYMENT PAPER TRAIL, MADE CLEAR</div>
              <h2>Proof is a claim.<br/><em>Credits are the truth.</em></h2>
              <p>Bring payment screenshots and bank credits into one place. EvidentPay checks what was claimed against what actually arrived.</p>
              <button className="ink-button" onClick={startNewEvent}>Start a verification <ArrowUpRight size={17}/></button>
            </div>
            <div className="opening-art" aria-hidden="true">
              <div className="receipt receipt-back"><span>UPI / CREDIT</span><b>₹500.00</b><small>TRANSACTION RECEIVED</small><i/><i/><i/></div>
              <div className="receipt receipt-front"><div className="receipt-top"><span>PAYMENT RECORD</span><Check size={16}/></div><b>₹500.00</b><small>UTR MATCH CONFIRMED</small><div className="receipt-code">EP · 00482 · 2026</div><div className="receipt-stamp"><ShieldCheck size={23}/><span>CHECKED<br/>AGAINST BANK</span></div></div>
              <div className="art-spark spark-a">✳</div><div className="art-spark spark-b">+</div>
            </div>
            <div className="opening-side-note">01 — EVIDENCE FIRST</div>
          </section>

          <section className="metric-strip">
            <div><span>EVENTS CREATED</span><strong>{loading ? "—" : events.length}</strong><small>Across this workspace</small></div>
            <div><span>PAYMENT CLAIMS</span><strong>{loading ? "—" : totalClaims}</strong><small>Screenshot records read</small></div>
            <div><span>VERIFICATION RESULTS</span><strong>{loading ? "—" : totalResults}</strong><small>Bank checks and screenshot reviews</small></div>
            <div><span>EVENTS PROCESSED</span><strong>{loading ? "—" : processedEvents}<small className="metric-total"> / {events.length}</small></strong><small>With results available</small></div>
          </section>

          <section className="overview-bottom">
            <div className="event-feed">
              <div className="section-heading"><div><span className="eyebrow">YOUR WORKSPACE</span><h2>Recent events</h2></div><button className="plain-link" onClick={() => go("events")}>See all events <ArrowRight size={15}/></button></div>
              <div className="feed-list">
                {loading ? <div className="empty-state"><LoaderCircle className="spin" size={22}/> Gathering event records…</div> :
                  events.length === 0 ? <div className="empty-state"><div className="empty-symbol"><Wallet size={25}/></div><h3>Nothing on the books yet.</h3><p>Create an event and the payment trail starts here.</p><button className="lime-button" onClick={startNewEvent}><Plus size={16}/> Create your first event</button></div> :
                  events.slice(0,5).map((event,index) => <button className="feed-row" key={event.event_id} onClick={() => loadEventData(event)}>
                    <span className="feed-index">{String(index + 1).padStart(2,"0")}</span><span className="feed-monogram">{(event.event_name || "E").slice(0,1).toUpperCase()}</span>
                    <span className="feed-name"><strong>{event.event_name}</strong><small>EP-{String(event.event_id).padStart(4,"0")} · {shortDate(event.created_at)}</small></span>
                    <span className="feed-value"><strong>{event.total_claims || 0}</strong><small>CLAIMS</small></span><span className="feed-value"><strong>{event.total_results || 0}</strong><small>CHECKS</small></span><ArrowUpRight className="feed-arrow" size={17}/>
                  </button>)}
              </div>
            </div>
            <aside className="principle-note">
              <div className="principle-icon"><Fingerprint size={23}/></div>
              <span className="eyebrow">THE EVIDENTPAY RULE</span>
              <h3>Evidence over appearance.</h3>
              <p>A screenshot tells us what someone says they paid. A matching incoming bank credit is what confirms it.</p>
              <div className="principle-foot"><ShieldCheck size={16}/> SCREENSHOTS ARE CLAIMS. BANK CREDITS CONFIRM.</div>
            </aside>
          </section>
        </>}

        {page === "events" && <>
          <section className="list-intro"><div><span className="eyebrow">THE COMPLETE REGISTER</span><h2>Every event.<br/><em>One clear record.</em></h2></div><p>Open an event to review its claims, imported bank data and reconciliation outcomes.</p></section>
          <section className="register">
            <div className="register-head"><div><strong>{events.length.toString().padStart(2,"0")}</strong><span>REGISTERED EVENTS</span></div><label className="search-field"><Search size={17}/><input value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="Search by event name or ID"/></label></div>
            {loading ? <div className="empty-state"><LoaderCircle className="spin" size={22}/> Loading events…</div> : filteredEvents.length === 0 ? <div className="empty-state"><h3>No events found.</h3><p>Try another search, or create a new event.</p><button className="lime-button" onClick={startNewEvent}><Plus size={16}/> New event</button></div> :
              <div className="register-list">{filteredEvents.map((event,index)=><button className="register-row" key={event.event_id} onClick={()=>loadEventData(event)}>
                <span className="register-number">{String(index+1).padStart(2,"0")}</span><span className="register-event"><strong>{event.event_name}</strong><small>EP-{String(event.event_id).padStart(4,"0")} · {shortDate(event.created_at)}</small></span>
                <span className="register-detail"><small>ENTRY FEE</small><strong>{money(event.event_price)}</strong></span><span className="register-detail"><small>PARTICIPANTS</small><strong>{event.expected_participant_count ?? "—"}</strong></span><span className="register-detail"><small>CLAIMS / RESULTS</small><strong>{event.total_claims || 0} / {event.total_results || 0}</strong></span><ArrowUpRight size={18}/>
              </button>)}</div>}
          </section>
        </>}

        {page === "new" && <>
          {!selectedEvent ? <section className="create-layout">
            <div className="create-story"><span className="eyebrow">A NEW COLLECTION STARTS HERE</span><h2>Set the scene.<br/><em>Then follow the money.</em></h2><p>Give this event a name, set its expected payment amount, and define the participant count. You can add payment evidence next.</p><div className="story-sequence"><div><b>01</b><span>Register the event</span></div><div><b>02</b><span>Collect payment proofs</span></div><div><b>03</b><span>Match incoming credits</span></div></div></div>
            <form className="create-form" onSubmit={createEvent}>
              <div className="form-overline"><span>EVENT SETUP</span><span>01 / 03</span></div>
              <label>What are we collecting for?<input required maxLength="150" placeholder="e.g. TechFest 2026" value={eventName} onChange={e=>setEventName(e.target.value)}/></label>
              <div className="form-pair"><label>Registration fee per participant (₹)<input required min="1" type="number" step="0.01" value={eventPrice} onChange={e=>setEventPrice(e.target.value)}/></label><label>Expected participants<input required min="1" type="number" value={participants} onChange={e=>setParticipants(e.target.value)}/></label></div>
              <div className="expected-collection"><span>EXPECTED AMOUNT TO BE RECEIVED</span><strong>{money((Number(eventPrice)||0)*(Number(participants)||0))}</strong><small>{participants || 0} participants × {money(eventPrice)}</small></div>
              <div className="form-hint"><CircleAlert size={16}/> Set the exact amount each participant is expected to pay.</div>
              <button className="ink-button form-submit" type="submit" disabled={busy==="create"}>{busy==="create" ? <LoaderCircle className="spin" size={17}/> : <Plus size={17}/>} Create event <ArrowRight size={17}/></button>
            </form>
          </section> : <section className="verification-layout">
            <div className="workflow-heading"><button className="back-link" onClick={()=>go("events")}><ChevronLeft size={16}/> All events</button><span className="eyebrow">EVENT EP-{String(selectedEvent.event_id).padStart(4,"0")}</span><h2>{selectedEvent.event_name}</h2><p>{money(selectedEvent.event_price)} per participant · {selectedEvent.expected_participant_count ?? "—"} expected</p><div className="expected-total"><span>EXPECTED AMOUNT TO BE RECEIVED</span><strong>{money(Number(selectedEvent.event_price || 0) * Number(selectedEvent.expected_participant_count || 0))}</strong><small>{selectedEvent.expected_participant_count ?? 0} expected payments</small></div></div>
            <div className="workflow-steps"><span className="current">01 <b>PAYMENT PROOFS</b></span><i/><span className={selectedEvent.total_bank_transactions || statementSummary ? "current" : ""}>02 <b>BANK RECORD</b></span><i/><span className={results.length ? "current" : ""}>03 <b>RESULT</b></span></div>
            <div className="verification-summary">
              <div><span>EXPECTED COLLECTION</span><strong>{money(Number(selectedEvent.event_price || 0) * Number(selectedEvent.expected_participant_count || 0))}</strong></div>
              <div><span>PER PARTICIPANT</span><strong>{money(selectedEvent.event_price)}</strong></div>
              <div><span>EXPECTED PARTICIPANTS</span><strong>{selectedEvent.expected_participant_count ?? "—"}</strong></div>
            </div>
            <div className="upload-columns">
              <section className="upload-section"><div className="upload-title"><span>01</span><div><span className="eyebrow">PARTICIPANT EVIDENCE</span><h3>Payment screenshots</h3><p>Select all payment proofs together. EvidentPay will read them automatically when you start verification.</p></div></div>
                <label className="drop-zone"><input type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" multiple onChange={e=>setScreenshots(Array.from(e.target.files||[]))}/><div className="drop-icon"><FileImage size={23}/></div><strong>{screenshots.length ? screenshots.length+" file(s) ready" : "Add payment screenshots"}</strong><span>or <u>browse your device</u></span><small>PNG · JPG · WEBP · MULTIPLE FILES</small></label>
                {screenshots.length>0 && <div className="selected-files">{screenshots.map(file=><div key={file.name}><FileImage size={15}/><span>{file.name}</span><small>{(file.size/1024/1024).toFixed(1)} MB</small></div>)}</div>}
                {uploadSummary && <div className="upload-result"><CheckCircle2 size={16}/>{uploadSummary.successful} processed · {uploadSummary.failed} failed</div>}
                <div className="upload-actions"><span>{selectedEvent.total_claims || uploadSummary?.successful || 0} claims already stored</span><span className="file-ready">{screenshots.length ? screenshots.length+" new selected" : "Ready when you are"}</span></div>
              </section>
              <section className="upload-section"><div className="upload-title"><span>02</span><div><span className="eyebrow">RECIPIENT ACCOUNT</span><h3>Bank statement</h3><p>Use the account that received the payments. CSV and text-based PDF statements are supported.</p></div></div>
                <label className="statement-zone"><input type="file" accept=".csv,.pdf,text/csv,application/pdf" onChange={e=>setStatement(e.target.files?.[0]||null)}/><FileSpreadsheet size={27}/><span><strong>{statement ? statement.name : "Choose a bank statement"}</strong><small>{statement ? (statement.size/1024).toFixed(0)+" KB selected" : "CSV or PDF · up to 20 MB"}</small></span><b>Browse</b></label>
                {statementSummary && <div className="upload-result"><CheckCircle2 size={16}/>{statementSummary.total_transactions} transactions · {statementSummary.credit_transactions} credits imported</div>}
                <div className="upload-actions"><span>{selectedEvent.total_bank_transactions || statementSummary?.total_transactions || 0} rows already imported</span><span className="file-ready">{statement ? "Statement selected" : "Optional only in screenshot review"}</span></div>
              </section>
            </div>
            <div className="no-statement-choice">
              <div><span className="eyebrow">DON'T HAVE THE RECIPIENT'S BANK STATEMENT?</span><strong>Run a screenshot-only review instead.</strong><p>We can inspect extracted details and repeated claims, but payments will remain unverified without bank credits.</p></div>
              <div className="mode-switch"><button className={reviewMode==="screenshots"?"choice-active":"choice-button"} onClick={()=>setReviewMode("screenshots")}>Use screenshot-only review</button><button className={reviewMode==="bank"?"choice-active":"choice-button"} onClick={()=>setReviewMode("bank")}>Use bank reconciliation</button></div>
            </div>
            <div className="verification-footer">
              <div className="verification-mode"><span className="eyebrow">VERIFICATION MODE</span><strong>{reviewMode==="bank"?"Bank statement reconciliation":"Screenshot-only · Unverified"}</strong><small>{reviewMode==="bank"?"Screenshots will be compared with incoming credits.":"No bank credit confirmation will be claimed."}</small></div>
              <button className="ink-button" onClick={runVerification} disabled={busy==="verification"||(!screenshots.length&&!selectedEvent.total_claims)||(reviewMode==="bank"&&!statement&&!selectedEvent.total_bank_transactions)}>{busy==="verification"?<><LoaderCircle className="spin" size={16}/> Processing files & checking records…</>:<><Zap size={16}/> {reviewMode==="bank"?"Verify all uploads":"Run screenshot review"} <ArrowRight size={17}/></>}</button>
            </div>
            <div className="trust-line"><ShieldCheck size={17}/> A screenshot is a payment claim. Only a matching recipient-side bank credit confirms receipt.</div>
            {results.length>0 && <button className="plain-link results-link" onClick={()=>loadEventData(selectedEvent)}>View latest results <ArrowUpRight size={15}/></button>}
          </section>}
        </>}

        {page === "event" && selectedEvent && <>
          <section className="report-heading"><button className="back-link" onClick={()=>go("events")}><ChevronLeft size={16}/> Event register</button><div className="report-title-row"><div><span className="eyebrow">EVENT REPORT / EP-{String(selectedEvent.event_id).padStart(4,"0")}</span><h2>{selectedEvent.event_name}</h2><p>{money(selectedEvent.event_price)} entry fee · {selectedEvent.expected_participant_count ?? "—"} expected · Created {shortDate(selectedEvent.created_at)}</p><div className="expected-total report-expected"><span>EXPECTED AMOUNT TO BE RECEIVED</span><strong>{money(Number(selectedEvent.event_price || 0) * Number(selectedEvent.expected_participant_count || 0))}</strong></div></div><button className="outline-button" onClick={()=>{setPage("new");setNotice("");}}><Upload size={15}/> Open workflow</button></div></section>
          <section className="report-metrics"><div><span>CLAIMS</span><strong>{claims.length}</strong></div><div><span>RESULT RECORDS</span><strong>{results.length}</strong></div><div><span>CONFIRMED MATCHES</span><strong>{matchedCount}</strong></div><div><span>NEEDS REVIEW</span><strong>{attentionCount}</strong></div></section>
          <section className="report-section"><div className="section-heading"><div><span className="eyebrow">{screenshotOnlyResults ? "SCREENSHOT EVIDENCE REVIEW" : "BANK-LED VERIFICATION"}</span><h2>{screenshotOnlyResults ? "Image assessment results" : "Reconciliation results"}</h2><p>{screenshotOnlyResults ? "Image metadata and visual indicators only. No bank credit was checked; these results do not establish authenticity." : "Claims compared with recipient-side incoming credits."}</p></div><button className="icon-action" onClick={()=>loadEventData(selectedEvent)} aria-label="Refresh results"><RefreshCw size={17}/></button></div>
            {results.length ? <div className="report-table-wrap"><table className="report-table"><thead><tr>{screenshotOnlyResults ? <><th>SCREENSHOT</th><th>ASSESSMENT</th><th>INDICATORS</th><th>BANK STATUS</th></> : <><th>SCREENSHOT</th><th>CLAIMED</th><th>UTR</th><th>BANK CREDIT</th><th>STATUS</th><th>REASONS</th></>}</tr></thead><tbody>{results.map(result=><tr key={result.result_id}><td><strong>{result.screenshot_filename||"Claim #"+result.claim_id}</strong><small>Claim #{result.claim_id}</small></td>{screenshotOnlyResults ? <><td><StatusTag value={result.status}/></td><td>{(result.reasons||[]).join(", ")||"No clear editing indicators detected"}</td><td>Not checked</td></> : <><td>{money(result.screenshot_amount)}</td><td className="mono">{result.screenshot_utr||"—"}</td><td>{result.bank_transaction?money(result.bank_transaction.credit):"—"}</td><td><StatusTag value={result.status}/></td><td>{(result.reasons||[]).join(", ")||"—"}</td></>}</tr>)}</tbody></table></div> : <div className="empty-state"><div className="empty-symbol"><Banknote size={25}/></div><h3>No verification results yet.</h3><p>Upload the evidence and choose a verification mode to continue.</p><button className="lime-button" onClick={()=>setPage("new")}>Continue workflow <ArrowRight size={16}/></button></div>}
          </section>
          <section className="report-section"><div className="section-heading"><div><span className="eyebrow">OCR OUTPUT</span><h2>Extracted claims <span className="inline-count">{claims.length}</span></h2><p>Details read from the submitted payment screenshots.</p></div></div>
            {claims.length ? <div className="report-table-wrap"><table className="report-table"><thead><tr><th>FILE</th><th>AMOUNT</th><th>UTR</th><th>TRANSACTION DATE</th><th>SENDER</th><th>EXTRACTION</th></tr></thead><tbody>{claims.map(claim=><tr key={claim.claim_id}><td>{claim.screenshot_filename}</td><td>{money(claim.amount)}</td><td className="mono">{claim.utr||"—"}</td><td>{shortDate(claim.transaction_date)}</td><td>{claim.sender_name||"—"}</td><td><StatusTag value={claim.needs_review?"Needs review":"Extracted"}/></td></tr>)}</tbody></table></div> : <div className="empty-state compact">No screenshots have been uploaded for this event.</div>}
          </section>
        </>}
        <footer className="site-footer"><span>EVIDENTPAY / 2026</span><span>BUILT AROUND THE RECEIVING ACCOUNT <ShieldCheck size={15}/></span></footer>
      </main>
    </div>
  );
}

export default App;
