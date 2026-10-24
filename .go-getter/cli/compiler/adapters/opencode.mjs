import { sharedSkills } from '../src/emit.mjs';

// OpenCode scans skills from its own and the shared skill directories; it has no remote skills manifest (fact 0005).
export default (ctx) => sharedSkills(ctx);
