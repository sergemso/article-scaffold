import { PLUGIN_DIR, json, sharedSkills } from '../src/emit.mjs';

// Gemini installs a whole repo and needs gemini-extension.json and skills/ in the same root;
// support dirs are linked too so skills' ../../shared references resolve from the repo root.
export default (ctx) => ({
  ...sharedSkills(ctx),
  'gemini-extension.json': json({ name: ctx.meta.name, version: ctx.meta.version, description: ctx.meta.description }),
  skills: { symlink: `${PLUGIN_DIR}/skills` },
  ...Object.fromEntries(ctx.supportDirs.map(({ dir }) => [dir, { symlink: `${PLUGIN_DIR}/${dir}` }])),
});
