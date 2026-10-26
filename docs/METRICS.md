# Metrics Specification and Validation

Every metric is computed in code from daily adjusted closing prices; the LLM never calculates them.

## Assumptions

| Item | Default |
| --- | --- |
| Lookback | 2 years of daily prices (user can pick 1 to 5) |
| Trading days per year | 252 |
| Portfolio model | Buy-and-hold of the current quantities over the window, no rebalancing |
| Returns | Simple daily returns of portfolio value in the base currency |
| Risk-free rate | Configurable; placeholder defaults 0.07 for INR and 0.04 for USD, set in config |
| Benchmark | ^NSEI (Nifty 50) if most value is Indian, ^GSPC (S&P 500) if most is US; user can override |
| FX | USDINR=X daily close, forward-filled over holidays |
| Missing data | Forward-fill gaps up to 5 days; drop stocks with under 60 days of history and warn |

The model answers "how would today's portfolio have behaved", not "what did the user actually earn". The UI must say so next to the risk numbers.

## Formulas

**Portfolio value and daily return**, with q the quantity, P the price and F the FX rate:

$$V_t = \sum_i q_i P_{i,t} F_t, \qquad r_t = \frac{V_t}{V_{t-1}} - 1$$

**Annualized volatility** (sample standard deviation):

$$\sigma = \operatorname{std}(r)\,\sqrt{252}$$

**Beta** against the benchmark:

$$\beta = \frac{\operatorname{Cov}(r_p, r_b)}{\operatorname{Var}(r_b)}$$

**Sharpe ratio**, with r_f the annual risk-free rate converted to a daily rate by compounding (the quantstats convention):

$$r_{f,d} = (1 + r_f)^{1/252} - 1, \qquad S = \frac{\bar{r} - r_{f,d}}{\operatorname{std}(r)}\sqrt{252}$$

**1-day historical VaR at 95%**:

$$\mathrm{VaR}_{95} = -\,\mathrm{percentile}_{5}(r)$$

**Drawdown and maximum drawdown**:

$$DD_t = \frac{V_t}{\max_{s \le t} V_s} - 1, \qquad \mathrm{MDD} = \min_t DD_t$$

**Weights and concentration**, with MV the market value:

$$w_i = \frac{MV_i}{\sum_j MV_j}, \qquad HHI = \sum_i w_i^2, \qquad N_{eff} = \frac{1}{HHI}$$

Sector exposure is the sum of w_i over the holdings in each sector.

**Risk contribution** (used by the chat agent), with Sigma the covariance matrix built from each holding's annualized volatility and the correlation matrix, at current weights:

$$RC_i = rac{w_i\,(\Sigma w)_i}{w^{	op}\Sigma w}, \qquad \sum_i RC_i = 1$$

It is a share of variance at today's weights and can differ slightly from the realized buy-and-hold volatility above.

## Validation plan

Align the periods and risk-free rate with the reference before comparing, and record any remaining gap in docs/VALIDATION.md.

| Metric | Reference | Tolerance |
| --- | --- | --- |
| Volatility | quantstats volatility, 252 periods | Relative error 0.5% or less |
| Sharpe ratio | quantstats sharpe, same risk-free rate and periods | Relative error 0.5% or less |
| Max drawdown | quantstats max_drawdown | Relative error 0.5% or less |
| Beta | numpy covariance on the same two series | Relative error 0.5% or less |
| VaR | numpy percentile on the same series (quantstats may use a different method) | 1e-6 |
| Weights, HHI, P&L | Hand-calculated fixtures | 1e-6 |

## Hand-calculated fixtures

- One stock priced 100, 110, 99, 120: max drawdown is 99/110 - 1, which is -10%.
- Constant price series: volatility 0 and drawdown 0.
- Price doubles then halves: max drawdown -50%.
- Two equal-value stocks: weights 0.5 each, HHI 0.5, effective N 2.
- Portfolio identical to the benchmark: beta 1.
- Two holdings, weights 0.5 each, volatilities 0.2 and 0.1, correlation 0: risk contributions 0.8 and 0.2.
- Same, correlation 1: risk contributions 2/3 and 1/3.
