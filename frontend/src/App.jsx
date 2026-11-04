
import React, { useState } from "react";
import {
  LayoutDashboard,
  History,
  ShieldCheck,
  CreditCard,
  Search,
  Bell,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  UserRound,
  CalendarDays,
  CheckCircle2,
  Clock,
  List,
  UploadCloud,
  FileImage,
  CircleHelp,
  ArrowRight,
  Menu,
  X,
} from "lucide-react";

import "./index.css";

function App() {
  const [activePage, setActivePage] = useState("Dashboard");
  const [search, setSearch] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedFile, setSelectedFile] = useState(null);
  const [notificationOpen, setNotificationOpen] = useState(false);

  const events = [
    {
      id: 7,
      name: "demo9",
      price: "₹14,000.00",
      participants: 12,
      date: "04 Nov 2026",
      status: "Verified",
    },
    {
      id: 6,
      name: "demoID",
      price: "₹10,000.00",
      participants: 2,
      date: "04 Nov 2026",
      status: "Verified",
    },
    {
      id: 5,
      name: "demoID",
      price: "₹10,000.00",
      participants: 2,
      date: "03 Nov 2026",
      status: "Pending",
    },
    {
      id: 4,
      name: "demoID",
      price: "₹500.00",
      participants: 12,
      date: "03 Nov 2026",
      status: "Verified",
    },
    {
      id: 3,
      name: "EvidentPay Demo",
      price: "₹500.00",
      participants: 100,
      date: "03 Nov 2026",
      status: "Verified",
    },
  ];

  const filteredEvents = events.filter((event) =>
    `${event.name} ${event.id} ${event.price}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const navigation = [
    {
      title: "Dashboard",
      icon: LayoutDashboard,
    },
    {
      title: "History",
      icon: History,
    },
    {
      title: "New verification",
      icon: CreditCard,
    },
  ];

  const handleFileChange = (e) => {
    setSelectedFile(e.target.files[0] || null);
  };

  return (
    <div className="app-layout">

      {/* SIDEBAR */}

      <aside className={`sidebar ${sidebarOpen ? "" : "sidebar-hidden"}`}>

        <div className="brand">
          <div className="brand-logo">
            <ShieldCheck size={27} />
          </div>

          <div>
            <h2>EVIDENTPAY</h2>
            <p>PAYMENT VERIFICATION</p>
          </div>
        </div>

        <div className="sidebar-menu">

          <p className="menu-label">WORKSPACE</p>

          {navigation.map((item) => {
            const Icon = item.icon;

            return (
              <button
                key={item.title}
                className={`menu-item ${
                  activePage === item.title ? "selected" : ""
                }`}
                onClick={() => {
                  setActivePage(item.title);
                  setSearch("");
                }}
              >
                <Icon size={19} />
                <span>{item.title}</span>

                {activePage === item.title && (
                  <ChevronRight className="menu-arrow" size={17} />
                )}
              </button>
            );
          })}

          <div className="menu-divider"></div>

          <p className="menu-label">MANAGEMENT</p>

          <button
            className="menu-item"
            onClick={() => setActivePage("Dashboard")}
          >
            <CalendarDays size={19} />
            <span>Event management</span>
          </button>

          <button
            className="menu-item"
            onClick={() => setActivePage("History")}
          >
            <CreditCard size={19} />
            <span>Payment records</span>
          </button>

        </div>

        <div className="sidebar-bottom">

          <div className="help-card">
            <CircleHelp size={23} />

            <h3>Need assistance?</h3>

            <p>
              Keep your event payments clear and verified.
            </p>

            <button onClick={() => setActivePage("History")}>
              View records <ArrowRight size={15} />
            </button>
          </div>

          <div className="sidebar-footer">
            <ShieldCheck size={16} />
            <span>EvidentPay · Secure workspace</span>
          </div>

        </div>

      </aside>

      {/* MAIN AREA */}

      <main className="main-area">

        {/* TOP HEADER */}

        <header className="topbar">

          <div className="topbar-left">

            <button
              className="sidebar-toggle"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              {sidebarOpen ? <Menu size={21} /> : <Menu size={21} />}
            </button>

            <div className="top-brand">
              <ShieldCheck size={24} />
              <span>EvidentPay</span>
            </div>

          </div>

          <div className="search-box">
            <Search size={19} />

            <input
              type="text"
              placeholder="Search here..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />

            {search && (
              <button onClick={() => setSearch("")}>
                <X size={16} />
              </button>
            )}
          </div>

          <div className="topbar-right">

            <button
              className="notification-button"
              onClick={() => setNotificationOpen(!notificationOpen)}
            >
              <Bell size={20} />
              <span className="notification-dot"></span>
            </button>

            {notificationOpen && (
              <div className="notification-popup">
                <strong>Notifications</strong>
                <p>You are viewing your local workspace.</p>
                <p>Check pending payment reviews.</p>
              </div>
            )}

            <button className="profile-button">
              <div className="profile-avatar">
                <UserRound size={20} />
              </div>

              <span>Admin</span>
              <ChevronDown size={17} />
            </button>

          </div>

        </header>

        {/* DASHBOARD PAGE */}

        {activePage === "Dashboard" && (

          <section className="page-content">

            <div className="breadcrumb">
              <span>Workspace</span>
              <ChevronRight size={15} />
              <strong>Dashboard</strong>
            </div>

            <div className="page-heading">

              <div>
                <p className="section-label">OVERVIEW</p>

                <h1>Your verification workspace</h1>

                <p className="page-description">
                  Track event payments and review incoming payment claims.
                </p>
              </div>

              <button
                className="primary-button"
                onClick={() => setActivePage("New verification")}
              >
                <CreditCard size={18} />
                New verification
                <ArrowRight size={17} />
              </button>

            </div>

            {/* STATISTICS */}

            <div className="stats-grid">

              <div className="stat-card">
                <div className="stat-icon icon-beige">
                  <CalendarDays size={25} />
                </div>

                <div className="stat-details">
                  <span>Total events</span>
                  <h2>3</h2>
                </div>

                <ChevronRight className="stat-arrow" size={18} />
              </div>

              <div className="stat-card">
                <div className="stat-icon icon-green">
                  <CheckCircle2 size={25} />
                </div>

                <div className="stat-details">
                  <span>Events processed</span>
                  <h2>2</h2>
                </div>

                <ChevronRight className="stat-arrow" size={18} />
              </div>

              <div className="stat-card">
                <div className="stat-icon icon-orange">
                  <Clock size={25} />
                </div>

                <div className="stat-details">
                  <span>Pending review</span>
                  <h2>1</h2>
                </div>

                <ChevronRight className="stat-arrow" size={18} />
              </div>

            </div>

            {/* RECENT EVENTS */}

            <div className="content-panel">

              <div className="panel-heading">

                <div className="panel-title">
                  <div className="panel-icon">
                    <List size={23} />
                  </div>

                  <div>
                    <h2>Recent events</h2>
                    <p>Your latest payment verification activity.</p>
                  </div>
                </div>

                <button
                  className="secondary-button"
                  onClick={() => setActivePage("History")}
                >
                  View history
                  <ArrowRight size={17} />
                </button>

              </div>

              <div className="table-container">

                <table className="events-table">

                  <thead>
                    <tr>
                      <th>Event</th>
                      <th>Event price</th>
                      <th>Participants</th>
                      <th>Created</th>
                      <th>Status</th>
                      <th></th>
                    </tr>
                  </thead>

                  <tbody>

                    {filteredEvents.map((event) => (

                      <tr key={event.id}>

                        <td>
                          <strong>{event.name}</strong>
                          <small>ID: {event.id}</small>
                        </td>

                        <td>{event.price}</td>

                        <td>{event.participants}</td>

                        <td>{event.date}</td>

                        <td>
                          <span
                            className={`status ${
                              event.status === "Verified"
                                ? "verified"
                                : "pending"
                            }`}
                          >
                            {event.status}
                          </span>
                        </td>

                        <td>
                          <button
                            className="table-action"
                            aria-label={`View event ${event.id}`}
                          >
                            <ChevronRight size={19} />
                          </button>
                        </td>

                      </tr>

                    ))}

                    {filteredEvents.length === 0 && (
                      <tr>
                        <td colSpan="6" className="empty-message">
                          No matching events found.
                        </td>
                      </tr>
                    )}

                  </tbody>

                </table>

              </div>

            </div>

          </section>
        )}

        {/* HISTORY PAGE */}

        {activePage === "History" && (

          <section className="page-content">

            <div className="breadcrumb">
              <span>Workspace</span>
              <ChevronRight size={15} />
              <strong>History</strong>
            </div>

            <div className="page-heading">
              <div>
                <p className="section-label">PAYMENT RECORDS</p>
                <h1>Payment history</h1>
                <p className="page-description">
                  Review your previous payment verification activity.
                </p>
              </div>
            </div>

            <div className="content-panel">

              <div className="panel-heading">
                <div className="panel-title">
                  <div className="panel-icon">
                    <History size={23} />
                  </div>

                  <div>
                    <h2>All events</h2>
                    <p>Payment records and their current status.</p>
                  </div>
                </div>
              </div>

              <div className="table-container">
                <table className="events-table">

                  <thead>
                    <tr>
                      <th>Event</th>
                      <th>Event price</th>
                      <th>Participants</th>
                      <th>Created</th>
                      <th>Status</th>
                    </tr>
                  </thead>

                  <tbody>
                    {filteredEvents.map((event) => (
                      <tr key={event.id}>
                        <td>
                          <strong>{event.name}</strong>
                          <small>ID: {event.id}</small>
                        </td>

                        <td>{event.price}</td>
                        <td>{event.participants}</td>
                        <td>{event.date}</td>

                        <td>
                          <span
                            className={`status ${
                              event.status === "Verified"
                                ? "verified"
                                : "pending"
                            }`}
                          >
                            {event.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>

                </table>
              </div>

            </div>

          </section>
        )}

        {/* NEW VERIFICATION PAGE */}

        {activePage === "New verification" && (

          <section className="page-content">

            <div className="breadcrumb">
              <span>Workspace</span>
              <ChevronRight size={15} />
              <strong>New verification</strong>
            </div>

            <div className="page-heading">
              <div>
                <p className="section-label">PAYMENT VERIFICATION</p>
                <h1>Upload payment proof</h1>
                <p className="page-description">
                  Upload a payment screenshot to verify it against bank records.
                </p>
              </div>
            </div>

            <div className="content-panel upload-panel">

              <div className="upload-heading">
                <h2>Payment screenshot</h2>
                <p>
                  Select the screenshot you want to verify.
                </p>
              </div>

              <div className="upload-layout">

                <div className="upload-left">

                  <label className="upload-box">

                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/jpg"
                      onChange={handleFileChange}
                    />

                    <div className="upload-icon">
                      <UploadCloud size={38} />
                    </div>

                    <h3>
                      Choose a file or drag and drop
                    </h3>

                    <p>PNG, JPG or JPEG</p>

                    <span className="browse-button">
                      Browse file
                    </span>

                    <small>
                      {selectedFile
                        ? selectedFile.name
                        : "No file chosen"}
                    </small>

                  </label>

                  <div className="upload-info">
                    <ShieldCheck size={17} />
                    <p>
                      Make sure the screenshot is clear and contains
                      the payment details.
                    </p>
                  </div>

                  <div className="upload-actions">

                    <button
                      className="secondary-button"
                      onClick={() => setActivePage("Dashboard")}
                    >
                      Go back
                    </button>

                    <button
                      className="primary-button"
                      disabled={!selectedFile}
                      onClick={() =>
                        alert("Connect this button to your verification backend.")
                      }
                    >
                      <ArrowRight size={17} />
                      Submit for verification
                    </button>

                  </div>

                </div>

                <div className="upload-preview">

                  <div className="preview-icon">
                    <FileImage size={75} />
                    <ShieldCheck size={35} />
                  </div>

                  <h3>Secure payment review</h3>

                  <p>
                    Your payment screenshot will be checked
                    against the actual bank statement data.
                  </p>

                </div>

              </div>

            </div>

          </section>

        )}

        {/* FOOTER */}

        <footer className="page-footer">
          <span>© 2026 EvidentPay. All rights reserved.</span>
          <span>Payment verification workspace</span>
        </footer>

      </main>

    </div>
  );
}

export default App;
