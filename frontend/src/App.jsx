
import { useState } from "react";
import "./index.css";

const API_BASE_URL = "http://localhost:8000";

function App() {
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

  const expectedCollection =
    Number(payment || 0) * Number(people || 0);

  const canContinue =
    eventName.trim() !== "" &&
    Number(payment) > 0 &&
    Number(people) > 0;

  const canReview =
    screenshots.length > 0 &&
    (mode === "screenshot" || statement !== null);

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

  const formatCurrency = (amount) =>
    Number(amount).toLocaleString("en-IN");

  const startAnalysis = async () => {
    setIsUploading(true);
    setApiError("");
    setUploadResult(null);

    try {
      // STEP 1: Create the event in the backend.

      const eventResponse = await fetch(
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

      const eventData = await eventResponse.json();

      if (!eventResponse.ok) {
        throw new Error(
          eventData.detail || "Could not create the event."
        );
      }

      const eventId = eventData.event_id;

      // STEP 2: Upload all selected screenshots.

      const formData = new FormData();

      screenshots.forEach((file) => {
        formData.append("files", file);
      });

      const uploadResponse = await fetch(
        `${API_BASE_URL}/api/events/${eventId}/screenshots`,
        {
          method: "POST",
          body: formData,
        }
      );

      const uploadData = await uploadResponse.json();

      if (!uploadResponse.ok) {
        throw new Error(
          uploadData.detail || "Screenshot upload failed."
        );
      }

      // STEP 3: Save the response for displaying in the UI.

      setUploadResult({
        event: eventData,
        upload: uploadData,
      });

    } catch (error) {
      setApiError(error.message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">E</div>
          <span>EvidentPay</span>
        </div>

        <div className="sidebar-label">WORKSPACE</div>

        <div className="sidebar-link active">
          <span className="sidebar-icon">▣</span>
          New verification
        </div>

        <div className="sidebar-link">
          <span className="sidebar-icon">◷</span>
          History
        </div>

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
            <span className="breadcrumb">/ New verification</span>
          </span>

          <span className="secure-status">
            <span className="status-dot"></span>
            Secure workspace
          </span>
        </header>

        <div className="content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">PAYMENT MANAGEMENT</p>
              <h1>New verification</h1>
              <p className="page-description">
                Verify event payments using screenshots and bank records.
              </p>
            </div>
          </div>

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

          <div className="content-card">

            {/* STEP 1: EVENT DETAILS */}

            {step === 1 && (
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
                      onChange={(e) =>
                        setEventName(e.target.value)
                      }
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
                          onChange={(e) =>
                            setPayment(e.target.value)
                          }
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
                        onChange={(e) =>
                          setPeople(e.target.value)
                        }
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
                  <span className="footer-hint">
                    Step 1 of 3
                  </span>

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

            {/* STEP 2: UPLOAD FILES */}

            {step === 2 && (
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
                              onClick={() =>
                                removeScreenshot(index)
                              }
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
                        Upload a CSV statement or select screenshot-only analysis.
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

            {/* STEP 3: REVIEW AND UPLOAD */}

            {step === 3 && (
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
                        <strong>
                          ₹{formatCurrency(expectedCollection)}
                        </strong>
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
                        ? "Payment screenshots will be uploaded first. Bank statement processing is not connected yet."
                        : "Only screenshot characteristics will be examined. Bank verification will not be performed."}
                    </p>
                  </div>

                  {/* API ERROR */}

                  {apiError && (
                    <div className="api-error">
                      <strong>Something went wrong</strong>
                      <p>{apiError}</p>
                    </div>
                  )}

                  {/* API SUCCESS RESULT */}

                  {uploadResult && (
                    <div className="api-result">
                      <h3>Screenshot upload completed</h3>

                      <p>
                        Event ID:{" "}
                        <strong>{uploadResult.event.event_id}</strong>
                      </p>

                      <p>
                        Successfully uploaded:{" "}
                        <strong>
                          {uploadResult.upload.successful}
                        </strong>
                      </p>

                      <p>
                        Failed uploads:{" "}
                        <strong>
                          {uploadResult.upload.failed}
                        </strong>
                      </p>

                      <div>
                        {uploadResult.upload.results.map(
                          (result, index) => (
                            <div
                              key={`${result.filename}-${index}`}
                              className="api-file-result"
                            >
                              <strong>{result.filename}</strong>

                              <p>
                                Status: {result.status}
                              </p>

                              {result.status === "success" && (
                                <>
                                  <p>
                                    Claim ID: {result.claim_id}
                                  </p>

                                  <p>
                                    Amount:{" "}
                                    {result.ocr_data.amount ?? "Not detected"}
                                  </p>

                                  <p>
                                    UTR:{" "}
                                    {result.ocr_data.utr ?? "Not detected"}
                                  </p>

                                  <p>
                                    Date:{" "}
                                    {result.ocr_data.transaction_date ??
                                      "Not detected"}
                                  </p>

                                  <p>
                                    Needs review:{" "}
                                    {result.ocr_data.needs_review
                                      ? "Yes"
                                      : "No"}
                                  </p>
                                </>
                              )}

                              {result.status === "failed" && (
                                <p>Error: {result.error}</p>
                              )}
                            </div>
                          )
                        )}
                      </div>

                      <p className="inline-hint">
                        OCR extraction is complete. Payment receipt
                        verification requires bank statement reconciliation.
                      </p>
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
                    disabled={isUploading || !!uploadResult}
                  >
                    {isUploading
                      ? "Uploading..."
                      : uploadResult
                        ? "Upload completed"
                        : "Start analysis"}
                    {!isUploading && !uploadResult && (
                      <span>→</span>
                    )}
                  </button>
                </div>
              </>
            )}
          </div>

          <div className="page-footer">
            EvidentPay <span>·</span> Evidence-based payment verification
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
