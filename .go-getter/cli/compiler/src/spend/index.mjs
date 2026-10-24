// Records the spend a hook event can see (decision 0144), by the host's capability `telemetry.spendSource`.
import { packageCapabilities } from '../governance.mjs';
import { detect } from '../detect.mjs';
import { recordTranscriptSpend } from './transcript.mjs';
import { recordSessionSpend } from './sessions.mjs';

// Never throws: spend recording must not break the step it observes.
export function recordHostSpend(project, host, payload, caps = packageCapabilities()) {
  try {
    if (caps[host]?.telemetry?.spendSource === 'transcript') return recordTranscriptSpend(project, host, payload.transcript_path);
  } catch {
    // fail open
  }
  return { records: 0, skipped: 0 };
}

// At a step boundary: reads the spend of hosts that keep sessions in their own store (they have no hook that names a file).
export function recordRunSpend(project, run, caps = packageCapabilities(), exec) {
  try {
    for (const host of detect(project).hostAgents) {
      if (caps[host]?.telemetry?.spendSource === 'sessions') recordSessionSpend(project, host, run.startedAt, exec ? { exec } : {});
    }
  } catch {
    // fail open
  }
}
