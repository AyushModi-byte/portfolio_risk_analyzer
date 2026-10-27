import type { RiskMetrics } from '../api/types';
import { formatNumber, formatPercent, observationsToYears } from '../lib/format';
import { benchmarkName, RISK_HELP } from '../lib/labels';
import { InfoTip } from './InfoTip';

interface CardProps {
  title: string;
  topic: string;
  value: string;
  sub?: string;
  help: string;
}

function RiskCard({ title, topic, value, sub, help }: CardProps) {
  return (
    <div className="risk-card">
      <dt>
        {title} <InfoTip topic={topic}>{help}</InfoTip>
      </dt>
      <dd>
        <span className="risk-value">{value}</span>
        {sub && <span className="risk-sub">{sub}</span>}
      </dd>
    </div>
  );
}

export function RiskCards({ risk }: { risk: RiskMetrics }) {
  const window = observationsToYears(risk.observations, risk.trading_days);
  const bench = benchmarkName(risk.benchmark);
  return (
    <section className="card" aria-labelledby="risk-heading">
      <h2 id="risk-heading">Risk</h2>
      <p className="assumption" role="note">
        These figures show how today’s holdings would have behaved over the past {window}. They are
        not what you actually earned and they are not a forecast.
      </p>
      <dl className="risk-grid">
        <RiskCard
          title="Volatility"
          topic="volatility"
          value={formatPercent(risk.volatility)}
          sub="per year"
          help={RISK_HELP.volatility}
        />
        <RiskCard
          title="Beta"
          topic="beta"
          value={formatNumber(risk.beta)}
          sub={`vs ${bench}`}
          help={RISK_HELP.beta}
        />
        <RiskCard
          title="Sharpe ratio"
          topic="the Sharpe ratio"
          value={formatNumber(risk.sharpe)}
          sub={`risk-free ${formatPercent(risk.risk_free_rate)}`}
          help={RISK_HELP.sharpe}
        />
        <RiskCard
          title="Value at risk"
          topic="value at risk"
          value={formatPercent(risk.var_95)}
          sub="1 day, 95% confidence"
          help={RISK_HELP.var95}
        />
        <RiskCard
          title="Max drawdown"
          topic="max drawdown"
          value={formatPercent(risk.max_drawdown)}
          sub="worst peak to trough"
          help={RISK_HELP.maxDrawdown}
        />
      </dl>
      <p className="muted">
        Concentration: the top 5 holdings make up {formatPercent(risk.top5_concentration, 1)} of the
        portfolio, which behaves like about {formatNumber(risk.effective_n, 1)} equal-sized
        holdings.
      </p>
    </section>
  );
}
