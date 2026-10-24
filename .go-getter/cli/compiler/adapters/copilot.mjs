import { sharedSkills, agentPluginsManifest } from '../src/emit.mjs';

export default (ctx) => ({ ...sharedSkills(ctx), ...agentPluginsManifest(ctx) });
