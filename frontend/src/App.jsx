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
  if (value.includes("duplicate") || value.includes("review") || value.includes("mismatch")) return "review";
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
  const attentionCount = results.filter((item) => statusTone(item.status) === "review").length;

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
      setSelectedEvent((current) => current ? { ...current, total_claims: Number(current.total_claims || 0) + Number(data.successful || 0) } : current);
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
      setSelectedEvent((current) => current ? { ...current, total_bank_transactions: Number(data.total_transactions || current.total_bank_transactions || 0) } : current);
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
      const data = await apiRequest("/api/events/" + selectedEvent.event_id + "/reconcile", { method: "POST" });
      setNotice(data.message || "Reconciliation completed.");
      await loadEvents();
      await loadEventData({ ...selectedEvent, total_results: data.total_reconciled });
    } catch (err) {
      setError(err.message);
      try {
        const refreshed = await apiRequest("/api/events/" + selectedEvent.event_id + "/results");
        setResults(refreshed.results || []);
      } catch {}
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
            <div><span>BANK COMPARISONS</span><strong>{loading ? "—" : totalResults}</strong><small>Reconciliation records</small></div>
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
              <div className="form-pair"><label>Registration fee (₹)<input required min="1" type="number" step="0.01" value={eventPrice} onChange={e=>setEventPrice(e.target.value)}/></label><label>Expected participants<input required min="1" type="number" value={participants} onChange={e=>setParticipants(e.target.value)}/></label></div>
              <div className="form-hint"><CircleAlert size={16}/> Set the exact amount each participant is expected to pay.</div>
              <button className="ink-button form-submit" type="submit" disabled={busy==="create"}>{busy==="create" ? <LoaderCircle className="spin" size={17}/> : <Plus size={17}/>} Create event <ArrowRight size={17}/></button>
            </form>
          </section> : <section className="verification-layout">
            <div className="workflow-heading"><button className="back-link" onClick={()=>go("events")}><ChevronLeft size={16}/> All events</button><span className="eyebrow">EVENT EP-{String(selectedEvent.event_id).padStart(4,"0")}</span><h2>{selectedEvent.event_name}</h2><p>{money(selectedEvent.event_price)} per participant · {selectedEvent.expected_participant_count ?? "—"} expected</p></div>
            <div className="workflow-steps"><span className="current">01 <b>SCREENSHOTS</b></span><i/><span className={selectedEvent.total_bank_transactions || statementSummary ? "current" : ""}>02 <b>BANK STATEMENT</b></span><i/><span className={results.length ? "current" : ""}>03 <b>RECONCILIATION</b></span></div>
            <div className="upload-columns">
              <section className="upload-section"><div className="upload-title"><span>01</span><div><span className="eyebrow">PARTICIPANT EVIDENCE</span><h3>Payment screenshots</h3><p>Upload multiple PNG, JPG or WebP files · 10 MB max each.</p></div></div>
                <label className="drop-zone"><input type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" multiple onChange={e=>setScreenshots(Array.from(e.target.files||[]))}/><div className="drop-icon"><FileImage size={23}/></div><strong>{screenshots.length ? screenshots.length+" file(s) selected" : "Drop payment screenshots here"}</strong><span>or <u>browse your device</u></span><small>PNG · JPG · WEBP</small></label>
                {screenshots.length>0 && <div className="selected-files">{screenshots.map(file=><div key={file.name}><FileImage size={15}/><span>{file.name}</span><small>{(file.size/1024/1024).toFixed(1)} MB</small></div>)}</div>}
                {uploadSummary && <div className="upload-result"><CheckCircle2 size={16}/>{uploadSummary.successful} processed · {uploadSummary.failed} failed</div>}
                <div className="upload-actions"><span>{selectedEvent.total_claims || uploadSummary?.successful || 0} claims stored</span><button className="lime-button" disabled={!screenshots.length||busy==="screenshots"} onClick={uploadScreenshots}>{busy==="screenshots"?<LoaderCircle className="spin" size={16}/>:<Upload size={16}/>} Upload proofs</button></div>
              </section>
              <section className="upload-section"><div className="upload-title"><span>02</span><div><span className="eyebrow">RECIPIENT ACCOUNT</span><h3>Bank statement</h3><p>Import the CSV from the account that received the payments.</p></div></div>
                <label className="statement-zone"><input type="file" accept=".csv,text/csv" onChange={e=>setStatement(e.target.files?.[0]||null)}/><FileSpreadsheet size={27}/><span><strong>{statement ? statement.name : "Choose a statement file"}</strong><small>{statement ? (statement.size/1024).toFixed(0)+" KB selected" : "CSV format · 20 MB max"}</small></span><b>Browse</b></label>
                {statementSummary && <div className="upload-result"><CheckCircle2 size={16}/>{statementSummary.total_transactions} transactions · {statementSummary.credit_transactions} credits imported</div>}
                <div className="upload-actions"><span>{selectedEvent.total_bank_transactions || statementSummary?.total_transactions || 0} rows imported</span><button className="outline-button" disabled={!statement||busy==="statement"} onClick={uploadStatement}>{busy==="statement"?<LoaderCircle className="spin" size={16}/>:<Upload size={16}/>} Import CSV</button></div>
              </section>
            </div>
            <div className="reconcile-band"><div><span className="eyebrow">THE FINAL CROSS-CHECK</span><h3>Ready to compare the records?</h3><p>Every extracted claim will be checked against incoming bank credits.</p></div><button className="ink-button" onClick={reconcile} disabled={busy==="reconcile"||!(selectedEvent.total_claims||uploadSummary?.successful)||!(selectedEvent.total_bank_transactions||statementSummary?.total_transactions)}>{busy==="reconcile"?<LoaderCircle className="spin" size={16}/>:<Zap size={16}/>} Run reconciliation <ArrowRight size={17}/></button></div>
            <div className="trust-line"><ShieldCheck size={17}/> A screenshot is a claim, not confirmation. A matching incoming bank credit is the confirmation signal.</div>
            {results.length>0 && <button className="plain-link results-link" onClick={()=>loadEventData(selectedEvent)}>View latest results <ArrowUpRight size={15}/></button>}
          </section>}
        </>}

        {page === "event" && selectedEvent && <>
          <section className="report-heading"><button className="back-link" onClick={()=>go("events")}><ChevronLeft size={16}/> Event register</button><div className="report-title-row"><div><span className="eyebrow">EVENT REPORT / EP-{String(selectedEvent.event_id).padStart(4,"0")}</span><h2>{selectedEvent.event_name}</h2><p>{money(selectedEvent.event_price)} entry fee · {selectedEvent.expected_participant_count ?? "—"} expected · Created {shortDate(selectedEvent.created_at)}</p></div><button className="outline-button" onClick={()=>{setPage("new");setNotice("");}}><Upload size={15}/> Open workflow</button></div></section>
          <section className="report-metrics"><div><span>CLAIMS</span><strong>{claims.length}</strong></div><div><span>RECONCILIATION RECORDS</span><strong>{results.length}</strong></div><div><span>CONFIRMED MATCHES</span><strong>{matchedCount}</strong></div><div><span>NEEDS REVIEW</span><strong>{attentionCount}</strong></div></section>
          <section className="report-section"><div className="section-heading"><div><span className="eyebrow">BANK-LED VERIFICATION</span><h2>Reconciliation results</h2><p>Claims compared with recipient-side incoming credits.</p></div><button className="icon-action" onClick={()=>loadEventData(selectedEvent)} aria-label="Refresh results"><RefreshCw size={17}/></button></div>
            {results.length ? <div className="report-table-wrap"><table className="report-table"><thead><tr><th>SCREENSHOT</th><th>CLAIMED</th><th>UTR</th><th>BANK CREDIT</th><th>STATUS</th><th>REASONS</th></tr></thead><tbody>{results.map(result=><tr key={result.result_id}><td><strong>{result.screenshot_filename||"Claim #"+result.claim_id}</strong><small>Claim #{result.claim_id}</small></td><td>{money(result.screenshot_amount)}</td><td className="mono">{result.screenshot_utr||"—"}</td><td>{result.bank_transaction?money(result.bank_transaction.credit):"—"}</td><td><StatusTag value={result.status}/></td><td>{(result.reasons||[]).join(", ")||"—"}</td></tr>)}</tbody></table></div> : <div className="empty-state"><div className="empty-symbol"><Banknote size={25}/></div><h3>No reconciliation results yet.</h3><p>Upload the evidence and bank statement, then run the cross-check.</p><button className="lime-button" onClick={()=>setPage("new")}>Continue workflow <ArrowRight size={16}/></button></div>}
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
