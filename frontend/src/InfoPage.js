import React, { useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './InfoPage.css';

function InfoPage({ appMode, scrollToSection }) {
  const navigate = useNavigate();
  const serviceRef = useRef(null);
  const readmeRef = useRef(null);
  const onboardingRef = useRef(null);

  const scrollTo = (ref) => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  useEffect(() => {
    if (scrollToSection === 'readme') {
      setTimeout(() => readmeRef.current?.scrollIntoView({ block: 'start' }), 50);
    } else if (scrollToSection === 'onboarding') {
      setTimeout(() => onboardingRef.current?.scrollIntoView({ block: 'start' }), 50);
    }
  }, [scrollToSection]);

  return (
    <div className="info-page">
      <header className="info-page-header" style={{ backgroundImage: `url(${process.env.PUBLIC_URL}/uchicago-aerial.png)` }}>
        <button className="info-back-btn" onClick={() => navigate('/')} type="button">
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M13 4l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back
        </button>
        <h1 className="info-page-title">Info</h1>
        <div className="info-header-spacer" />
      </header>

      <nav className="info-nav">
        <button className="info-nav-item" onClick={() => scrollTo(serviceRef)}>Service Info</button>
        <button className="info-nav-item" onClick={() => scrollTo(readmeRef)}>README</button>
        <button className="info-nav-item" onClick={() => scrollTo(onboardingRef)}>Onboarding</button>
      </nav>

      <main className="info-page-content">
        {/* Service Info */}
        <section className="info-section" ref={serviceRef}>
          <h2 className="info-section-title">Service Info</h2>
          {appMode === 'lyft' && (
            <p className="info-section-tagline">Get Free Lyft Rides</p>
          )}
          <div className="info-list-card">
            <div className="info-list-item">
              <span className="info-list-label">Service Hours</span>
              <span className="info-list-value">
                {appMode === 'lyft' ? '5:00 PM – 4:00 AM' : '5:00 PM – 4:00 AM on weekdays'}
              </span>
            </div>
            <div className="info-list-item">
              <span className="info-list-label">Boundaries</span>
              <span className="info-list-value">You must book within RideSmart boundaries, or this app will show errors</span>
            </div>
            <div className="info-list-item">
              <span className="info-list-label">Important</span>
              <span className="info-list-value">Do not leave or refresh site while booking in progress</span>
            </div>
            <div className="info-list-item">
              <span className="info-list-label">Contact</span>
              <span className="info-list-value">+447754666843 on WhatsApp</span>
            </div>
          </div>
        </section>

        {/* README */}
        <section className="info-section" ref={readmeRef}>
          <h2 className="info-section-title">README</h2>

          <div className="info-prose">
            <h3>RideSmart</h3>
            <p>A web app that automates getting free Lyft rides through the University of Chicago's RideSmart shuttle service. It fills shuttle capacity using multiple accounts to trigger Lyft as an alternative, then books the Lyft for the original user and cancels all filler bookings.</p>

            <h4>How It Works</h4>
            <p>RideSmart vehicles are shared shuttles holding 3–6 passengers. When enough seats are filled, the service offers a Lyft instead. The orchestrator exploits this by:</p>
            <ol>
              <li><strong>Phase 1</strong> — Search for available rides across all filler accounts simultaneously</li>
              <li><strong>Phase 2</strong> — Book all filler accounts in parallel (fills shuttle capacity)</li>
              <li><strong>Phase 3</strong> — Search as the original user to check if Lyft appeared</li>
              <li><strong>Phase 4</strong> — Book the Lyft if available</li>
              <li><strong>Phase 5</strong> — Cancel all filler bookings simultaneously</li>
            </ol>
            <p>Running all phases in parallel reduces total time from ~4.5 minutes (sequential) to ~60 seconds.</p>

            <h4>Tech Stack</h4>
            <ul>
              <li><strong>Backend:</strong> Python, Flask, SQLite/PostgreSQL</li>
              <li><strong>Frontend:</strong> React, Leaflet (interactive maps)</li>
              <li><strong>Deployment:</strong> Vercel (frontend), Railway (backend)</li>
            </ul>

            <h4>Setup</h4>
            <h5>Prerequisites</h5>
            <ul>
              <li>Python 3.10+</li>
              <li>Node.js 18+</li>
              <li>2–7 RideSmart accounts with auth tokens</li>
            </ul>

            <h5>Backend</h5>
            <pre><code>{`cd backend
pip install -r requirements.txt
cp .env.example .env
# Fill in credentials (see Configuration below)
python api.py
# Runs on http://localhost:5000`}</code></pre>

            <h5>Frontend</h5>
            <pre><code>{`cd frontend
npm install
npm start
# Runs on http://localhost:3000`}</code></pre>

            <h5>CLI (no frontend needed)</h5>
            <pre><code>{`cd backend
python main.py`}</code></pre>

            <h4>Configuration</h4>
            <p>Copy <code>backend/.env.example</code> to <code>backend/.env</code> and fill in your credentials:</p>
            <pre><code>{`DEFAULT_USER=matthew

USER_MATTHEW_NAME=Matthew
USER_MATTHEW_AUTH_TOKEN=<token from RideSmart app>
USER_MATTHEW_USER_ID=<your user ID>

USER_TOMAS_NAME=Tomas
USER_TOMAS_AUTH_TOKEN=<token>
USER_TOMAS_USER_ID=<id>

# Add up to 7 users total (1 original + 6 fillers)`}</code></pre>
            <p>Auth tokens can be extracted from the RideSmart mobile app using a proxy or browser DevTools.</p>

            <h5>Routes</h5>
            <p>Preset routes are defined in <code>backend/src/destination_config.py</code>. The default route is I-House → Cathey Dining Commons. Add routes by defining origin/destination lat-lng pairs.</p>

            <h5>Global Settings</h5>
            <p>Edit <code>backend/src/config.py</code> to adjust:</p>
            <pre><code>{`n_passengers = 2        # Number of passengers to book for
charging = False        # Whether device is charging (sent to API)`}</code></pre>

            <h4>API Endpoints</h4>
            <div className="info-table-wrapper">
              <table className="info-table">
                <thead>
                  <tr><th>Method</th><th>Path</th><th>Description</th></tr>
                </thead>
                <tbody>
                  <tr><td><code>GET</code></td><td><code>/api/users</code></td><td>List configured users</td></tr>
                  <tr><td><code>GET</code></td><td><code>/api/routes</code></td><td>List available routes</td></tr>
                  <tr><td><code>POST</code></td><td><code>/api/search</code></td><td>Search for available rides</td></tr>
                  <tr><td><code>POST</code></td><td><code>/api/book</code></td><td>Book a ride</td></tr>
                  <tr><td><code>POST</code></td><td><code>/api/cancel</code></td><td>Cancel a ride</td></tr>
                  <tr><td><code>GET</code></td><td><code>/api/status</code></td><td>Current booking status (all users)</td></tr>
                  <tr><td><code>GET</code></td><td><code>/api/status/stream</code></td><td>SSE stream of booking status</td></tr>
                  <tr><td><code>POST</code></td><td><code>/api/lyft/run</code></td><td>Run the Lyft orchestrator (SSE stream)</td></tr>
                  <tr><td><code>POST</code></td><td><code>/api/lyft/check</code></td><td>Check if Lyft is currently available</td></tr>
                  <tr><td><code>GET</code></td><td><code>/api/developer/stream</code></td><td>SSE stream of developer logs</td></tr>
                  <tr><td><code>GET</code></td><td><code>/api/developer/snapshot</code></td><td>Snapshot of developer logs</td></tr>
                </tbody>
              </table>
            </div>

            <h4>Deployment</h4>
            <h5>Frontend (Vercel)</h5>
            <pre><code>{`cd frontend
vercel`}</code></pre>
            <p>Set environment variable in Vercel dashboard:</p>
            <pre><code>REACT_APP_API_URL=https://your-backend.railway.app</code></pre>

            <h5>Backend (Railway)</h5>
            <pre><code>{`cd backend
railway login
railway init
railway up`}</code></pre>
            <p>Railway auto-detects Python and serves via Gunicorn.</p>

            <h5>Database</h5>
            <p>By default, developer logs are stored in SQLite (<code>backend/data/</code>). For persistent storage on Railway or Vercel, provision a PostgreSQL database and set:</p>
            <pre><code>DATABASE_URL=postgresql://...</code></pre>
            <p>The backend auto-detects and uses Postgres when available.</p>

            <h4>Project Structure</h4>
            <pre><code>{`backend/
├── api.py                      # Flask API server
├── main.py                     # Standalone CLI
├── src/
│   ├── lyft_orchestrator.py    # Core orchestration logic
│   ├── search_ride.py          # Via.com search API
│   ├── book_ride.py            # Via.com booking API
│   ├── cancel_ride.py          # Via.com cancel API
│   ├── users.py                # Credential loading
│   ├── destination_config.py   # Route definitions
│   ├── developer_logs.py       # Real-time log streaming
│   └── booking_state.py        # Live booking state tracking
frontend/
├── src/
│   ├── App.js                  # App shell
│   ├── LyftBooker.js           # Lyft orchestration UI
│   ├── DeveloperPanel.js       # Admin/developer view
│   ├── MapSelector.js          # Map-based location picker
│   └── BookingStatusPanel.js   # Live booking status`}</code></pre>

            <h4>Notes</h4>
            <ul>
              <li>Each API call to the RideSmart backend takes ~10–15 seconds. The parallel approach is essential for reasonable UX.</li>
              <li>The <code>.env</code> file contains sensitive auth tokens — never commit it (already in <code>.gitignore</code>).</li>
              <li>All filler bookings are always cancelled at the end, whether or not a Lyft was found.</li>
              <li>The "stop" button lets you abort mid-orchestration; in-flight requests finish before cleanup begins.</li>
            </ul>
          </div>
        </section>

        {/* Onboarding */}
        <section className="info-section" ref={onboardingRef}>
          <h2 className="info-section-title">Onboarding: Adding a New Account</h2>

          <div className="info-prose">
            <h4>Step 1: Install Proxyman</h4>
            <p>Download <strong>Proxyman</strong> from the App Store on your iPhone and complete the initial setup, including:</p>
            <ul>
              <li>Downloading and installing the Proxyman certificate</li>
              <li>Enabling root certificate trust: <strong>Settings → General → About → Certificate Trust Settings</strong>, then toggle on full trust for Proxyman</li>
            </ul>

            <h4>Step 2: Start the VPN</h4>
            <p>In Proxyman, start the VPN. This routes your phone's traffic through Proxyman so it can be inspected.</p>

            <h4>Step 3: Find the RideSmart Domain</h4>
            <p>Navigate to the domain (in the Proxyman app):</p>
            <pre><code>router-ucaca.live.ridewithvia.com</code></pre>
            <p>Then enable <strong>SSL Proxying</strong> on it. This lets Proxyman decrypt and read the request bodies for that domain.</p>

            <h4>Step 4: Capture the Request</h4>
            <ol>
              <li>Open the <strong>RideSmart app</strong> and book any ride, then cancel it</li>
              <li>Go back to Proxyman and find the request URL ending in: <code>/prescheduled/recurring/get</code></li>
              <li>Tap it, go to <strong>Request → Body</strong>, and copy the entire contents</li>
            </ol>
            <p>Send that to me (+447754666843 on WhatsApp) to add the account. You can now turn off the VPN in Proxyman.</p>
            <p>Once you're confirmed onboarded, you can uninstall Proxyman entirely — it's only needed for the initial setup.</p>
          </div>
        </section>
      </main>
    </div>
  );
}

export default InfoPage;
