import { useEffect, useState } from "react";
import { parseStatus, type ApplicationStatus } from "./status";

type Connection =
  { state: "loading" | "offline" } | { state: "connected"; status: ApplicationStatus };

export function App() {
  const [connection, setConnection] = useState<Connection>({ state: "loading" });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    let nextPoll: ReturnType<typeof setTimeout>;
    let controller: AbortController;
    let timeout: ReturnType<typeof setTimeout>;
    setConnection({ state: "loading" });
    async function refresh() {
      controller = new AbortController();
      timeout = setTimeout(() => controller.abort(), 4000);
      try {
        const response = await fetch("/api/status", {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok) throw new Error("Status unavailable");
        const status = parseStatus(await response.json());
        if (active) setConnection({ state: "connected", status });
      } catch {
        if (active) setConnection({ state: "offline" });
      } finally {
        clearTimeout(timeout);
        if (active) nextPoll = setTimeout(refresh, 5000);
      }
    }
    void refresh();
    return () => {
      active = false;
      controller?.abort();
      clearTimeout(timeout);
      clearTimeout(nextPoll);
    };
  }, [retry]);
  const connected = connection.state === "connected";
  const databaseReady = connected && connection.status.database === "ready";
  const offline = connection.state === "offline" || (connected && !databaseReady);
  const label = connection.state === "loading" ? "Connecting" : offline ? "Offline" : "Connected";
  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Wallet Observer home">
          <span className="brand-mark" aria-hidden="true">
            ◎
          </span>
          <span>
            Wallet Observer
            <span className="brand-subtitle">A quieter view of on-chain activity</span>
          </span>
        </a>
        <span className={`connection ${offline ? "is-offline" : ""}`} role="status">
          <span className="status-dot" aria-hidden="true" />
          {label}
        </span>
      </header>
      <main>
        <div className="page-heading">
          <div>
            <p className="eyebrow">YOUR OBSERVATION DESK</p>
            <h1>Wallet activity</h1>
            <p className="intro">Follow the activity that matters, with room to see it clearly.</p>
          </div>
          <span className="network">
            <span aria-hidden="true">≋</span> Solana
          </span>
        </div>
        {connected && connection.status.mode === "fixture" && (
          <div className="notice">
            <span className="notice-label">Fixture mode</span>
            <span>Development workspace. Live collection and alerts are off.</span>
          </div>
        )}
        <div className="workspace">
          <section className="activity-panel" aria-labelledby="activity-title">
            <div className="panel-heading">
              <h2 id="activity-title">Activity feed</h2>
              <span>Read-only</span>
            </div>
            <div className="empty-state" aria-live="polite">
              <div className={`orbit ${offline ? "orbit-offline" : ""}`} aria-hidden="true">
                <span>◎</span>
              </div>
              <p className="eyebrow">{offline ? "CONNECTION PAUSED" : "A CLEAR START"}</p>
              <h3>
                {connection.state === "loading"
                  ? "Connecting to your workspace"
                  : offline
                    ? "Your workspace is offline"
                    : "No collected activity yet"}
              </h3>
              <p>
                {connection.state === "loading"
                  ? "Checking your connection and workspace availability."
                  : connection.state === "offline"
                    ? "We can’t reach the service. We’ll check again automatically."
                    : offline
                      ? "The service is reachable, but its database is unavailable. We’ll check again automatically."
                      : "Wallet collection is not enabled in this build. Transactions will appear here once collection is available."}
              </p>
              {offline && (
                <button onClick={() => setRetry((value) => value + 1)}>
                  Try again <span aria-hidden="true">↗</span>
                </button>
              )}
            </div>
            <div className="panel-footer">
              <span className="small-dot" />
              {databaseReady ? "Workspace available · Collection off" : "Waiting for the workspace"}
            </div>
          </section>
          <aside aria-label="Workspace overview">
            <section className="overview">
              <p className="eyebrow">AT A GLANCE</p>
              <h2>Built for observation</h2>
              <dl>
                <div>
                  <dt>Network</dt>
                  <dd>Solana</dd>
                </div>
                <div>
                  <dt>Collection</dt>
                  <dd>Not enabled</dd>
                </div>
                <div>
                  <dt>Alerts</dt>
                  <dd>Not enabled</dd>
                </div>
              </dl>
              <p className="aside-note">
                Monitoring is read-only. No signing keys or trading access are needed.
              </p>
            </section>
            <div className="footnote">
              <span aria-hidden="true">↳</span>
              <p>
                A transaction appearing near a wallet does not always mean that wallet made a trade.
                Verified activity comes first.
              </p>
            </div>
          </aside>
        </div>
      </main>
      <footer className="site-footer">
        <span>Wallet Observer</span>
        <span>Personal. Read-only. Deliberate.</span>
      </footer>
    </div>
  );
}
