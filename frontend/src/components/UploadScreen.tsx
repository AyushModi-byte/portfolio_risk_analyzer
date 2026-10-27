import { DropZone } from './DropZone';
import { Spinner } from './Feedback';

const SAMPLES = [
  { name: 'india', label: 'India', detail: '13 NSE large caps · INR' },
  { name: 'us', label: 'US', detail: '12 US large caps · USD' },
  { name: 'mixed', label: 'Mixed', detail: '6 Indian + 6 US stocks · INR' },
] as const;

interface UploadScreenProps {
  busy: boolean;
  busyLabel: string;
  onFile: (file: File) => void;
  onSample: (name: string) => void;
}

export function UploadScreen({ busy, busyLabel, onFile, onSample }: UploadScreenProps) {
  return (
    <section className="upload" aria-labelledby="upload-heading">
      <h1 id="upload-heading">See the risk in your portfolio</h1>
      <p className="lead">
        Upload the holdings export from your broker to see volatility, drawdown, sector exposure and
        concentration in one place.
      </p>

      <DropZone onFile={onFile} disabled={busy} />
      <p className="privacy">
        Your file is read in memory to build the analysis and is never stored or logged.
      </p>

      {busy ? (
        <div className="busy">
          <Spinner label={busyLabel} />
        </div>
      ) : (
        <>
          <div className="divider">
            <span>or try a sample portfolio</span>
          </div>
          <ul className="sample-grid">
            {SAMPLES.map((sample) => (
              <li key={sample.name}>
                <button
                  type="button"
                  className="sample-button"
                  onClick={() => {
                    onSample(sample.name);
                  }}
                >
                  <span className="sample-title">Try sample portfolio: {sample.label}</span>
                  <span className="sample-detail">{sample.detail}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
