// Host OpenTelemetry settings (decision 0087): written for the `host-otel` recording or the `otlp` export answer,
// only where the host's project config accepts them. Setting names come from vendor docs; any other host is reported
// unavailable with the reason, and nothing is written for it.
import { adoptedData } from '../governance.mjs';

export const DEFAULT_ENDPOINT = 'http://localhost:4318';

// Gemini CLI: https://geminicli.com/docs/cli/telemetry (workspace .gemini/settings.json). Prompts are never exported.
const GEMINI = {
  file: '.gemini/settings.json',
  settings: (endpoint) => ({ enabled: true, target: 'local', otlpEndpoint: endpoint, otlpProtocol: 'http', logPrompts: false }),
  key: 'telemetry',
};

export const OTEL_TARGETS = {
  'gemini-cli': GEMINI,
};

// https://code.claude.com/docs/en/monitoring-usage; https://learn.chatgpt.com/docs/config-file/config-advanced; facts 0005, 0006, 0008.
export const OTEL_UNAVAILABLE = {
  'claude-code': 'user or managed settings only; project settings ignore the OpenTelemetry variables',
  codex: 'user config only; project config ignores [otel]',
  kilo: 'no OpenTelemetry export documented',
  opencode: 'no OpenTelemetry export documented',
  cursor: 'no OpenTelemetry export documented',
  copilot: 'no OpenTelemetry export documented',
};

export function otelConfig(project) {
  const wanted = adoptedData(project, 'telemetry-recording') === 'host-otel' || adoptedData(project, 'telemetry-export') === 'otlp';
  return { wanted, endpoint: adoptedData(project, 'telemetry-otlp-endpoint') ?? DEFAULT_ENDPOINT };
}

// { host: { status: 'emitted', file } | { status: 'unavailable', reason } } for the target hosts, or null when not wanted.
export function otelReport(project, hosts) {
  if (!otelConfig(project).wanted) return null;
  return Object.fromEntries(
    hosts.map((h) =>
      OTEL_TARGETS[h]
        ? [h, { status: 'emitted', file: OTEL_TARGETS[h].file }]
        : [h, { status: 'unavailable', reason: OTEL_UNAVAILABLE[h] ?? 'unconfirmed' }],
    ),
  );
}

// Merges a host's settings into its parsed config file.
export function withOtel(host, base, endpoint) {
  const t = OTEL_TARGETS[host];
  return { ...base, [t.key]: { ...base[t.key], ...t.settings(endpoint) } };
}
