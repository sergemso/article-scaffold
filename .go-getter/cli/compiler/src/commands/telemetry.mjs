// go-getter telemetry summary [--project <dir>]: totals from the local metadata log.
import path from 'node:path';
import { readLog, summarize, telemetryConfig } from '../telemetry/record.mjs';

export default function telemetryCommand({ args }) {
  const [sub, ...rest] = args;
  let project = process.cwd();
  for (let i = 0; i < rest.length; i++) if (rest[i] === '--project') project = path.resolve(rest[++i]);
  if (sub !== 'summary') {
    console.error('usage: go-getter telemetry summary [--project <dir>]');
    return 2;
  }
  const { recording, retentionDays } = telemetryConfig(project);
  console.log(JSON.stringify({ recording, retentionDays, ...summarize(readLog(project)) }, null, 2));
  return 0;
}
