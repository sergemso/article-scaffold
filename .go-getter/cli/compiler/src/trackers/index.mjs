// The WorkSource `plan` reads (decisions 0117 and 0118): the plan file, with the state of every issue its steps name overlaid from
// that issue's tracker. Each adapter claims only the steps whose `Issue:` is its own, so a plan with no issue calls nothing.
import { fileSource } from './file-source.mjs';
import { githubAdapter } from './github.mjs';
import { jiraAdapter } from './jira.mjs';
import { overlay } from './overlay.mjs';
import { ok } from './worksource.mjs';

export function trackerSource(file, { project, name = file, now = () => new Date(), jira = {} } = {}) {
  const base = fileSource(file, { name });
  const adapters = [githubAdapter(project), jiraAdapter(project, jira)];
  const apply = async (steps) => {
    let out = steps;
    for (const adapter of adapters) out = await overlay({ project, steps: out, adapter, now });
    return out;
  };
  return {
    id: 'tracker',
    ops: base.ops,
    async handle(op, args) {
      const answer = await base.handle(op, args);
      if (!answer.ok) return answer;
      if (op === 'list') return ok({ steps: await apply(answer.result.steps) });
      if (answer.result.step) return ok({ step: (await apply([answer.result.step]))[0] });
      return answer;
    },
  };
}
