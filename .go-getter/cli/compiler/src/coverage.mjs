// Harness coverage report (plan 4.6, fitness function of decision 0008): for each of the 12 harness
// components (fact 0002), the adopted packs covering it and the strongest tier reached on each host.
import { readArtifacts } from './artifacts.mjs';
import { HOSTS } from './capabilities.mjs';

export const COMPONENTS = {
  1: 'Orchestration loop',
  2: 'Tool registry',
  3: 'Execution sandbox',
  4: 'Context management',
  5: 'Memory',
  6: 'Verification loops',
  7: 'Guardrails & DLP',
  8: 'Human-in-the-loop',
  9: 'Checkpointing',
  10: 'Multi-agent orchestration',
  11: 'Cost & model routing',
  12: 'Observability',
};

// packs: { id: packJson }; caps: { host: capabilities }.
export function coverage(project, packs, caps, hosts = HOSTS) {
  const guardrails = readArtifacts(project, ['guardrails']).filter((g) => g.data.status === 'active');
  const adopted = new Map();
  for (const a of readArtifacts(project)) {
    const by = a.data['go-getter']?.['generated-by'];
    if (a.data.status === 'active' && by) adopted.set(by.split('@')[0], by);
  }
  return Object.entries(COMPONENTS).map(([num, name]) => {
    const c = Number(num);
    const covering = [...adopted.keys()].filter((id) => packs[id]?.components?.includes(c)).sort();
    const entries = guardrails
      .filter((g) => covering.includes(String(g.data['go-getter']?.['generated-by'] ?? '').split('@')[0]))
      .flatMap((g) => g.data['go-getter'].enforcement ?? []);
    const tiers = Object.fromEntries(
      hosts.map((h) => {
        if (!entries.length) return [h, null];
        const reach = caps[h]?.tiers?.[String(c)] ?? 2;
        return [h, Math.max(...entries.map((e) => (e.tier === 3 ? 3 : e.tier === 2 ? (reach >= 2 ? 2 : 1) : 1)))];
      }),
    );
    // In-host enforcement apart from CI: a host that cannot reach tier 2 is advisory there.
    const inHost = Object.fromEntries(
      hosts.map((h) => [h, entries.some((e) => e.tier === 2) && (caps[h]?.tiers?.[String(c)] ?? 2) >= 2 ? 2 : null]),
    );
    const row = { component: c, name, packs: covering.map((id) => adopted.get(id)), tiers, inHost };
    // The host's own restore command for what its native checkpoint covers (file edits), beside `go-getter checkpoint restore`.
    // Tool-output masking (component 7, decision 0106): where the host can replace tool output, and what is masked there.
    if (c === 7) {
      const canReplace = hosts.filter((h) => caps[h]?.hooks?.rewriteOutput === true);
      // Hosts that replace MCP results only (capability hooks.rewriteMcpOutput): masked there for MCP tools, not for others.
      const mcpOnly = hosts.filter((h) => !canReplace.includes(h) && caps[h]?.hooks?.rewriteMcpOutput === true);
      const inHostEntries = entries.filter((e) => e.tier === 2);
      row.outputMasking = {
        secrets: inHostEntries.length ? canReplace : [],
        pii: inHostEntries.some((e) => /^builtin:redact-pii\b/.test(e.run ?? '')) ? canReplace : [],
        none: inHostEntries.length ? hosts.filter((h) => !canReplace.includes(h)) : [],
        mcpOnly: inHostEntries.some((e) => /^builtin:mcp-(allow|scan)\b/.test(e.run ?? '')) ? mcpOnly : [],
      };
    }
    if (c === 9) row.nativeRestore = Object.fromEntries(hosts.filter((h) => caps[h]?.checkpointRestore).map((h) => [h, caps[h].checkpointRestore]));
    return row;
  });
}

const LABEL = { 3: 'ci', 2: 'hook', 1: 'advisory' };

export function formatCoverage(rows, hosts = HOSTS) {
  const header = ['component', 'packs', ...hosts];
  // A host that blocks in-host and is also checked in CI reads "hook+ci".
  const cell = (r, h) => (r.tiers[h] === 3 && r.inHost?.[h] === 2 ? 'hook+ci' : r.tiers[h] ? LABEL[r.tiers[h]] : '-');
  const body = rows.map((r) => [`${r.component} ${r.name}`, r.packs.length ? r.packs.join(', ') : 'none', ...hosts.map((h) => cell(r, h))]);
  const widths = header.map((_, i) => Math.max(...[header, ...body].map((row) => row[i].length)));
  const table = [header, ...body].map((row) => row.map((cell, i) => cell.padEnd(widths[i])).join('  ').trimEnd()).join('\n');
  const lines = [table];
  const masking = rows.find((r) => r.component === 7)?.outputMasking;
  if (masking?.secrets.length) {
    const parts = [`secrets on ${masking.secrets.join(', ')}`];
    if (masking.pii.length) parts.push(`personal data on ${masking.pii.join(', ')}`);
    if (masking.none.length) parts.push(`not on ${masking.none.join(', ')} (the host cannot replace tool output)`);
    if (masking.mcpOnly?.length) parts.push(`MCP results alone on ${masking.mcpOnly.join(', ')} (the host replaces only those)`);
    lines.push(`Tool-output masking (component 7): ${parts.join('; ')}.`);
  }
  const checkpoints = rows.find((r) => r.component === 9);
  if (!checkpoints?.packs.length) return lines.join('\n\n');
  const native = Object.entries(checkpoints.nativeRestore ?? {}).map(([h, cmd]) => `${h} ${cmd}`);
  lines.push(`Restore (component 9): go-getter checkpoint restore on every host${native.length ? `; native, for file edits: ${native.join(', ')}` : ''}.`);
  return lines.join('\n\n');
}
