export function ConfigError() {
  return (
    <main className="main">
      <div className="banner banner-error" role="alert">
        <div className="banner-body">
          <strong>The app isn’t configured</strong>
          <span>
            <code>VITE_API_URL</code> is not set. Copy <code>frontend/.env.example</code> to{' '}
            <code>frontend/.env</code>, set it to your backend URL, and restart the dev server (or
            rebuild).
          </span>
        </div>
      </div>
    </main>
  );
}
