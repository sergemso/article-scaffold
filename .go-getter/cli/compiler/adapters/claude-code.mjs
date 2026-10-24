import { PLUGIN_DIR, json, sharedSkills } from '../src/emit.mjs';

export default (ctx) => ({
  ...sharedSkills(ctx),
  '.claude-plugin/marketplace.json': json({
    name: 'go-getter',
    owner: { name: 'vivantel' },
    description: ctx.meta.description,
    plugins: [{ name: 'go-getter', description: ctx.meta.description, source: `./${PLUGIN_DIR}` }],
  }),
  [`${PLUGIN_DIR}/.claude-plugin/plugin.json`]: json({ ...ctx.meta, displayName: 'go-getter' }),
});
