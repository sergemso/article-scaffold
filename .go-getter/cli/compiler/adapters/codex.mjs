import { PLUGIN_DIR, json, sharedSkills } from '../src/emit.mjs';

export default (ctx) => ({
  ...sharedSkills(ctx),
  [`${PLUGIN_DIR}/.codex-plugin/plugin.json`]: json({
    name: ctx.meta.name,
    version: ctx.meta.version,
    description: ctx.meta.description,
    skills: './skills',
  }),
  // Entry shape per third-party descriptions of Codex marketplaces; verified in plan step 6.3.
  '.agents/plugins/marketplace.json': json({
    name: 'go-getter',
    interface: { displayName: 'go-getter' },
    plugins: [
      {
        name: 'go-getter',
        source: { source: 'local', path: `./${PLUGIN_DIR}` },
        policy: { installation: 'AVAILABLE', authentication: 'ON_INSTALL' },
        category: 'Developer Tools',
      },
    ],
  }),
});
