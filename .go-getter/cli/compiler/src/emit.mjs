// Helpers shared by the per-host adapters in compiler/adapters/ (decision 0021).
export const PLUGIN_DIR = 'plugins/go-getter';

export function json(value) {
  return { content: `${JSON.stringify(value, null, 2)}\n` };
}

// Skills plus the plugin-root support dirs they reference, identical for every host.
export function sharedSkills(ctx) {
  const out = {};
  for (const skill of ctx.skills) {
    for (const f of skill.files) out[`${PLUGIN_DIR}/skills/${skill.name}/${f}`] = { content: skill.read(f) };
  }
  for (const { dir, files, read } of ctx.supportDirs) {
    for (const f of files) out[`${PLUGIN_DIR}/${dir}/${f}`] = { content: read(f) };
  }
  return out;
}

// Agent Plugins 1.0 manifest, shared by hosts that read it.
export function agentPluginsManifest(ctx) {
  return { [`${PLUGIN_DIR}/plugin.json`]: json({ $schema: 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json', ...ctx.meta }) };
}
