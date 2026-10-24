import { PLUGIN_DIR, json, sharedSkills } from '../src/emit.mjs';

export default (ctx) => ({
  ...sharedSkills(ctx),
  [`${PLUGIN_DIR}/skills/index.json`]: json({
    skills: ctx.skills.map((s) => ({ name: s.name, version: ctx.meta.version, files: s.files })),
  }),
});
