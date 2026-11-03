import { useState } from "react";
import "./index.css";

const API_BASE_URL = "http://localhost:8000";

async function apiRequest(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.detail || data.message || `Request failed (${response.status})`
    );
  }

  return data;
}

function App() {
  const [view, setView] = useState("new");
  const [step, setStep] = useState(1);

  const [eventName, setEventName] = useState("");
  const [payment, setPayment] = useState("");
  const [people, setPeople] = useState("");

  const [screenshots, setScreenshots] = useState([]);
  const [statement, setStatement] = useState(null);
  const [mode, setMode] = useState("bank");

  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [apiError, setApiError] = useState("");

  const [history, setHistory] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState("");

  const expectedCollection =
    Number(payment || 0) * Number(people || 0);

  const canContinue =
    eventName.trim() !== "" &&
    Number(payment) > 0 &&
    Number(people) > 0;

  const canReview =
    screenshots.length > 0 &&
    (mode === "screenshot" || statement !== null);

  const formatCurrency = (amount) =>
    Number(amount || 0).toLocaleString("en-IN");

  const addScreenshots = (files) => {
    const images = Array.from(files).filter((file) =>
      file.type.startsWith("image/")
    );

    setScreenshots((current) => {
      const combined = [...current, ...images];

      return combined.filter(
        (file, index) =>
          combined.findIndex(
            (item) =>
              item.name === file.name &&
              item.size === file.size
          ) === index
      );
    });
  };

  const removeScreenshot = (index) => {
    setScreenshots((current) =>
      current.filter((_, i) => i !== index)
    );
  };

  const resetNewVerification = () => {
    setStep(1);
    setEventName("");
    setPayment("");
    setPeople("");
    setScreenshots([]);
    setStatement(null);
    setMode("bank");
    setUploadResult(null);
    setApiError("");
    setView("new");
  };

  const loadHistory = async () => {
    setView("history");
    setHistoryError("");
    setIsLoadingHistory(true);

    try {
      const data = await apiRequest(`${API_BASE_URL}/api/events`);
      setHistory(data.events || []);
    } catch (error) {
      setHistoryError(error.message);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const startAnalysis = async () => {
    setIsUploading(true);
    setApiError("");
    setUploadResult(null);

    try {
      // STEP 1: Create the event.

      const eventData = await apiRequest(
        `${API_BASE_URL}/api/events`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            event_name: eventName.trim(),
            event_price: Number(payment),
            expected_participant_count: Number(people),
          }),
        }
      );

      const eventId = eventData.event_id;

      // STEP 2: Upload screenshots.

      const screenshotForm = new FormData();

      screenshots.forEach((file) => {
        screenshotForm.append("files", file);
      });

      const uploadData = await apiRequest(
        `${API_BASE_URL}/api/events/${eventId}/screenshots`,
        {
          method: "POST",
          body: screenshotForm,
        }
      );

      if (uploadData.successful === 0) {
        throw new Error(
          "None of the screenshots could be processed. Check the uploaded files and try again."
        );
      }

      // STEP 3A: Screenshot-only analysis.

      if (mode === "screenshot") {
        const claimsData = await apiRequest(
          `${API_BASE_URL}/api/events/${eventId}/claims`
        );

        setUploadResult({
          event: eventData,
          upload: uploadData,
          mode: "screenshot",
          claims: claimsData.claims || [],
        });

        return;
      }

      // STEP 3B: Upload the bank statement.

      const statementForm = new FormData();
      statementForm.append("file", statement);

      const statementData = await apiRequest(
        `${API_BASE_URL}/api/events/${eventId}/statement`,
        {
          method: "POST",
          body: statementForm,
        }
      );

      // STEP 4: Reconcile screenshots against bank records.

      const reconciliationData = await apiRequest(
        `${API_BASE_URL}/api/events/${eventId}/reconcile`,
        {
          method: "POST",
        }
      );

      // STEP 5: Retrieve the detailed reconciliation results.

      const resultsData = await apiRequest(
        `${API_BASE_URL}/api/events/${eventId}/results`
      );

      setUploadResult({
        event: eventData,
        upload: uploadData,
        mode: "bank",
        statement: statementData,
        reconciliation: reconciliationData,
        results: resultsData.results || [],
      });
    } catch (error) {
      setApiError(error.message);
    } finally {
      setIsUploading(false);
    }
  };

  const renderHistory = () => (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">PAYMENT MANAGEMENT</p>
          <h1>Verification history</h1>
          <p className="page-description">
            View events previously submitted for payment analysis.
          </p>
        </div>

        <button
          className="primary-button"
          onClick={resetNewVerification}
        >
          + New verification
        </button>
      </div>

      <div className="content-card">
        <div className="card-heading">
          <div>
            <h2>Previous events</h2>
            <p>Events saved in your EvidentPay database.</p>
          </div>

          <button
            className="secondary-button"
            onClick={loadHistory}
            disabled={isLoadingHistory}
          >
            {isLoadingHistory ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        <div className="form-body">
          {historyError && (
            <div className="api-error">
              <strong>Could not load history</strong>
              <p>{historyError}</p>
            </div>
          )}

          {isLoadingHistory && (
            <p className="inline-hint">Loading events...</p>
          )}

          {!isLoadingHistory &&
            !historyError &&
            history.length === 0 && (
              <p className="inline-hint">
                No events found. Create your first verification to see it here.
              </p>
            )}

          {history.map((event) => (
            <div className="review-block" key={event.event_id}>
              <div className="review-header">
                <h3>{event.event_name}</h3>
                <span className="optional-tag">
                  Event #{event.event_id}
                </span>
              </div>

              <div className="review-grid">
                <div>
                  <span>Payment per person</span>
                  <strong>₹{formatCurrency(event.event_price)}</strong>
                </div>

                <div>
                  <span>Expected participants</span>
                  <strong>
                    {event.expected_participant_count ?? "—"}
                  </strong>
                </div>

                <div>
                  <span>Screenshots</span>
                  <strong>{event.total_claims}</strong>
                </div>

                <div>
                  <span>Bank transactions</span>
                  <strong>{event.total_bank_transactions}</strong>
                </div>

                <div>
                  <span>Reconciliation results</span>
                  <strong>{event.total_results}</strong>
                </div>

                <div>
                  <span>Created</span>
                  <strong>
                    {event.created_at
                      ? new Date(event.created_at).toLocaleString()
                      : "—"}
                  </strong>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );

  const renderAnalysisResult = () => {
    if (!uploadResult) return null;

    const isBankMode = uploadResult.mode === "bank";

    return (
      <div className="api-result">
        <h3>
          {isBankMode
            ? "Payment reconciliation completed"
            : "Screenshot analysis completed"}
        </h3>

        <p>
          Event ID: <strong>{uploadResult.event.event_id}</strong>
        </p>

        <p>
          Successfully uploaded:{" "}
          <strong>{uploadResult.upload.successful}</strong>
        </p>

        <p>
          Failed uploads:{" "}
          <strong>{uploadResult.upload.failed}</strong>
        </p>

        {isBankMode && (
          <>
            <p>
              Bank transactions imported:{" "}
              <strong>
                {uploadResult.statement.total_transactions}
              </strong>
            </p>

            <p>
              Reconciliation results created:{" "}
              <strong>
                {uploadResult.reconciliation.total_reconciled}
              </strong>
            </p>

            <h4>Reconciliation summary</h4>

            {Object.entries(
              uploadResult.reconciliation.summary || {}
            ).map(([status, count]) => (
              <p key={status}>
                {status.replaceAll("_", " ")}:{" "}
                <strong>{count}</strong>
              </p>
            ))}

            <h4>Individual payment results</h4>

            {uploadResult.results.map((result) => (
              <div
                className="api-file-result"
                key={result.result_id}
              >
                <strong>{result.screenshot_filename}</strong>

                <p>
                  Status:{" "}
                  <strong>
                    {result.status.replaceAll("_", " ")}
                  </strong>
                </p>

                <p>
                  Screenshot amount:{" "}
                  {result.screenshot_amount ?? "Not detected"}
                </p>

                <p>
                  Screenshot UTR:{" "}
                  {result.screenshot_utr ?? "Not detected"}
                </p>

                {result.bank_transaction && (
                  <>
                    <p>
                      Bank credit:{" "}
                      {result.bank_transaction.credit}
                    </p>

                    <p>
                      Bank UTR:{" "}
                      {result.bank_transaction.utr ?? "Not available"}
                    </p>

                    <p>
                      Statement row:{" "}
                      {result.bank_transaction.statement_row}
                    </p>
                  </>
                )}

                {result.reasons?.length > 0 && (
                  <p>
                    Notes: {result.reasons.join(", ")}
                  </p>
                )}
              </div>
            ))}
          </>
        )}

        {!isBankMode && (
          <>
            <p>
              <strong>Screenshot-only mode</strong>
            </p>

            <p className="inline-hint">
              These are OCR-extracted payment claims. They have not been
              verified against recipient-side bank records.
            </p>

            <h4>Extracted payment information</h4>

            {uploadResult.claims.map((claim) => (
              <div
                className="api-file-result"
                key={claim.claim_id}
              >
                <strong>{claim.screenshot_filename}</strong>

                <p>
                  Amount: {claim.amount ?? "Not detected"}
                </p>

                <p>
                  UTR: {claim.utr ?? "Not detected"}
                </p>

                <p>
                  Date: {claim.transaction_date ?? "Not detected"}
                </p>

                <p>
                  Payment app: {claim.payment_app ?? "Not detected"}
                </p>

                <p>
                  Needs review: {claim.needs_review ? "Yes" : "No"}
                </p>

                {claim.flags?.length > 0 && (
                  <p>Review notes: {claim.flags.join(", ")}</p>
                )}
              </div>
            ))}
          </>
        )}

        <button
          className="primary-button"
          onClick={resetNewVerification}
        >
          Start a new verification
        </button>

        <button
          className="secondary-button"
          onClick={loadHistory}
        >
          View history
        </button>
      </div>
    );
  };

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">E</div>
          <span>EvidentPay</span>
        </div>

        <div className="sidebar-label">WORKSPACE</div>

        <button
          type="button"
          className={`sidebar-link ${view === "new" ? "active" : ""}`}
          onClick={() => setView("new")}
        >
          <span className="sidebar-icon">▣</span>
          New verification
        </button>

        <button
          type="button"
          className={`sidebar-link ${view === "history" ? "active" : ""}`}
          onClick={loadHistory}
        >
          <span className="sidebar-icon">◷</span>
          History
        </button>

        <div className="sidebar-bottom">
          <div className="profile-avatar">EP</div>
          <div>
            <strong>Event Organizer</strong>
            <small>Workspace</small>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <span>
            Workspace{" "}
            <span className="breadcrumb">
              / {view === "history" ? "History" : "New verification"}
            </span>
          </span>

          <span className="secure-status">
            <span className="status-dot"></span>
            Secure workspace
          </span>
        </header>

        <div className="content">
          {view === "history" ? (
            renderHistory()
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">PAYMENT MANAGEMENT</p>
                  <h1>New verification</h1>
                  <p className="page-description">
                    Verify event payments using screenshots and bank records.
                  </p>
                </div>
              </div>

              {!uploadResult && (
                <div className="stepper">
                  {[
                    "Event details",
                    "Upload files",
                    "Review & analyse",
                  ].map((label, index) => {
                    const number = index + 1;

                    return (
                      <button
                        type="button"
                        key={label}
                        className={`stepper-item ${
                          step === number ? "active" : ""
                        } ${step > number ? "done" : ""}`}
                        onClick={() => {
                          if (number < step) setStep(number);
                        }}
                        disabled={number >= step}
                      >
                        <span className="step-number">
                          {step > number ? "✓" : number}
                        </span>
                        <span>{label}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              <div className="content-card">
                {step === 1 && !uploadResult && (
                  <>
                    <div className="card-heading">
                      <div>
                        <h2>Event details</h2>
                        <p>
                          Enter the basic information about the event
                          you want to verify.
                        </p>
                      </div>
                    </div>

                    <div className="form-body">
                      <label className="field">
                        <span>Event name</span>
                        <input
                          type="text"
                          placeholder="e.g. Annual Tech Fest 2026"
                          value={eventName}
                          onChange={(e) => setEventName(e.target.value)}
                        />
                      </label>

                      <div className="field-row">
                        <label className="field">
                          <span>Payment per person</span>
                          <div className="currency-input">
                            <span>₹</span>
                            <input
                              type="number"
                              min="1"
                              placeholder="500"
                              value={payment}
                              onChange={(e) => setPayment(e.target.value)}
                            />
                          </div>
                        </label>

                        <label className="field">
                          <span>Estimated participants</span>
                          <input
                            type="number"
                            min="1"
                            placeholder="e.g. 100"
                            value={people}
                            onChange={(e) => setPeople(e.target.value)}
                          />
                        </label>
                      </div>

                      <div className="summary-strip">
                        <div>
                          <span>Expected collection</span>
                          <strong>
                            ₹
                            {expectedCollection
                              ? formatCurrency(expectedCollection)
                              : "—"}
                          </strong>
                        </div>

                        <span className="summary-note">
                          Based on estimated participants
                        </span>
                      </div>
                    </div>

                    <div className="card-footer">
                      <span className="footer-hint">Step 1 of 3</span>

                      <button
                        className="primary-button"
                        disabled={!canContinue}
                        onClick={() => setStep(2)}
                      >
                        Continue <span>→</span>
                      </button>
                    </div>
                  </>
                )}

                {step === 2 && !uploadResult && (
                  <>
                    <div className="card-heading">
                      <div>
                        <h2>Upload payment evidence</h2>
                        <p>
                          Add participant screenshots and the recipient's
                          bank statement.
                        </p>
                      </div>
                    </div>

                    <div className="form-body">
                      <div className="upload-section">
                        <div className="section-title">
                          <div>
                            <h3>Payment screenshots</h3>
                            <p>
                              Upload one or more payment confirmation images.
                            </p>
                          </div>

                          <span className="required-tag">Required</span>
                        </div>

                        <label className="drop-zone">
                          <input
                            type="file"
                            accept="image/*"
                            multiple
                            onChange={(e) => {
                              addScreenshots(e.target.files);
                              e.target.value = "";
                            }}
                          />

                          <span className="upload-icon">↑</span>
                          <strong>Choose screenshots to upload</strong>
                          <small>or drag and drop images here</small>
                          <small className="file-hint">
                            PNG, JPG and JPEG supported
                          </small>
                        </label>

                        {screenshots.length > 0 && (
                          <div className="file-list">
                            <div className="file-list-header">
                              <strong>
                                Selected files ({screenshots.length})
                              </strong>

                              <button
                                type="button"
                                className="link-button"
                                onClick={() => setScreenshots([])}
                              >
                                Remove all
                              </button>
                            </div>

                            {screenshots.map((file, index) => (
                              <div
                                className="file-row"
                                key={`${file.name}-${index}`}
                              >
                                <span className="file-type image-type">
                                  IMG
                                </span>

                                <div className="file-info">
                                  <strong>{file.name}</strong>
                                  <small>
                                    {(file.size / 1024).toFixed(1)} KB
                                  </small>
                                </div>

                                <button
                                  type="button"
                                  className="remove-button"
                                  onClick={() => removeScreenshot(index)}
                                >
                                  ×
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="upload-section statement-section">
                        <div className="section-title">
                          <div>
                            <h3>Bank statement</h3>
                            <p>
                              Upload the account statement containing incoming
                              payment transactions.
                            </p>
                          </div>

                          <span className="optional-tag">CSV</span>
                        </div>

                        <label className="statement-upload">
                          <span className="file-type csv-type">CSV</span>

                          <div className="file-info">
                            <strong>
                              {statement
                                ? statement.name
                                : "Choose bank statement"}
                            </strong>

                            <small>
                              {statement
                                ? `${(statement.size / 1024).toFixed(1)} KB`
                                : "Recipient-side transaction records"}
                            </small>
                          </div>

                          <span className="browse-link">Browse</span>

                          <input
                            type="file"
                            accept=".csv,text/csv"
                            onChange={(e) => {
                              const file = e.target.files?.[0] || null;
                              setStatement(file);

                              if (file) setMode("bank");
                            }}
                          />
                        </label>

                        {statement && (
                          <button
                            type="button"
                            className="link-button remove-statement"
                            onClick={() => setStatement(null)}
                          >
                            Remove statement
                          </button>
                        )}

                        <button
                          type="button"
                          className={`screenshot-option ${
                            mode === "screenshot" ? "selected" : ""
                          }`}
                          onClick={() => {
                            setMode("screenshot");
                            setStatement(null);
                          }}
                        >
                          <span className="radio-indicator">
                            {mode === "screenshot" ? "●" : ""}
                          </span>

                          <span>
                            <strong>
                              I don't have a bank statement
                            </strong>

                            <small>
                              Continue with screenshot-only analysis.
                              Payment receipt cannot be verified in this mode.
                            </small>
                          </span>
                        </button>

                        {mode === "bank" && !statement && (
                          <p className="inline-hint">
                            Upload a CSV statement or select screenshot-only
                            analysis.
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="card-footer">
                      <button
                        className="secondary-button"
                        onClick={() => setStep(1)}
                      >
                        ← Back
                      </button>

                      <button
                        className="primary-button"
                        disabled={!canReview}
                        onClick={() => setStep(3)}
                      >
                        Continue <span>→</span>
                      </button>
                    </div>
                  </>
                )}

                {step === 3 && !uploadResult && (
                  <>
                    <div className="card-heading">
                      <div>
                        <h2>Review your submission</h2>
                        <p>
                          Check the details below before starting the analysis.
                        </p>
                      </div>
                    </div>

                    <div className="form-body">
                      <div className="review-block">
                        <div className="review-header">
                          <h3>Event information</h3>

                          <button
                            className="link-button"
                            onClick={() => setStep(1)}
                          >
                            Edit
                          </button>
                        </div>

                        <div className="review-grid">
                          <div>
                            <span>Event name</span>
                            <strong>{eventName}</strong>
                          </div>

                          <div>
                            <span>Payment per person</span>
                            <strong>₹{formatCurrency(payment)}</strong>
                          </div>

                          <div>
                            <span>Estimated participants</span>
                            <strong>{people}</strong>
                          </div>

                          <div>
                            <span>Expected collection</span>
                            <strong>₹{formatCurrency(expectedCollection)}</strong>
                          </div>
                        </div>
                      </div>

                      <div className="review-block">
                        <div className="review-header">
                          <h3>Uploaded files</h3>

                          <button
                            className="link-button"
                            onClick={() => setStep(2)}
                          >
                            Edit
                          </button>
                        </div>

                        <div className="review-file">
                          <span className="file-type image-type">IMG</span>

                          <div className="file-info">
                            <strong>Payment screenshots</strong>
                            <small>
                              {screenshots.length} image(s) selected
                            </small>
                          </div>

                          <span className="file-check">✓</span>
                        </div>

                        <div className="review-file">
                          <span className="file-type csv-type">CSV</span>

                          <div className="file-info">
                            <strong>Bank statement</strong>
                            <small>
                              {statement ? statement.name : "Not provided"}
                            </small>
                          </div>

                          <span className="file-check">
                            {statement ? "✓" : "—"}
                          </span>
                        </div>
                      </div>

                      <div className="mode-summary">
                        <span>SELECTED ANALYSIS MODE</span>

                        <strong>
                          {mode === "bank"
                            ? "Payment verification"
                            : "Screenshot-only analysis"}
                        </strong>

                        <p>
                          {mode === "bank"
                            ? "Screenshots will be checked against the uploaded recipient-side bank statement."
                            : "Only OCR-extracted screenshot information will be displayed. Bank verification will not be performed."}
                        </p>
                      </div>

                      {apiError && (
                        <div className="api-error">
                          <strong>Something went wrong</strong>
                          <p>{apiError}</p>
                        </div>
                      )}
                    </div>

                    <div className="card-footer">
                      <button
                        className="secondary-button"
                        onClick={() => setStep(2)}
                        disabled={isUploading}
                      >
                        ← Back
                      </button>

                      <button
                        className="primary-button"
                        onClick={startAnalysis}
                        disabled={isUploading}
                      >
                        {isUploading ? "Processing..." : "Start analysis"}
                        {!isUploading && <span>→</span>}
                      </button>
                    </div>
                  </>
                )}

                {uploadResult && (
                  <div className="form-body">
                    {renderAnalysisResult()}
                  </div>
                )}
              </div>

              <div className="page-footer">
                EvidentPay <span>·</span> Evidence-based payment verification
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;