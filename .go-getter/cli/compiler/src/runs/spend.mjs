// Whether a run's spend cap can bind (decision 0144, fact 0037): spend is read from telemetry records, and only a host whose
// capability row names a `spendSource` has a reader that writes them.
const STOPS_THAT_STILL_APPLY = 'the timeout, red fix attempts, repeated denials and steps that need a person';

// { metered, notice } for a cap on the given hosts. `metered` is false when no host can meter; `notice` is the plain text
// to print (null when every host can meter, or when there is no cap).
export function spendCoverage(hosts, caps, spendCapUsd) {
  if (!spendCapUsd) return { metered: true, notice: null };
  const sourceOf = (h) => caps[h]?.telemetry?.spendSource ?? 'none';
  const blind = hosts.filter((h) => sourceOf(h) === 'none');
  const metered = hosts.length > 0 && blind.length < hosts.length;
  if (metered && !blind.length) return { metered, notice: null };
  const where = hosts.length ? `on ${blind.join(', ')}` : 'here (no host agent detected)';
  const stops = `${STOPS_THAT_STILL_APPLY} still apply`;
  const notice = metered
    ? `warning: the spend cap of $${spendCapUsd} cannot bind ${where}, which records no spend; ${stops}`
    : `warning: the spend cap of $${spendCapUsd} cannot bind ${where}: no spend is recorded for this host; ${stops}`;
  return { metered, notice };
}
