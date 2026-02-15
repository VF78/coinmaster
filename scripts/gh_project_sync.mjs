#!/usr/bin/env node
/**
 * GitHub Project v2 sync script for CoinMaster.
 *
 * Purpose:
 * - Update issue bodies with detailed continuation context
 * - Create a new P0 cutover issue (if missing) and add it to the project
 * - Enforce "single In Progress" status
 *
 * Usage:
 *   export GITHUB_TOKEN=...   # PAT classic
 *   node scripts/gh_project_sync.mjs --apply
 *
 * Safe mode (no mutations):
 *   node scripts/gh_project_sync.mjs
 */

const APPLY = process.argv.includes('--apply');

const OWNER = 'VF78';
const REPO = 'coinmaster';
const PROJECT_NUMBER = 2;

const CUTOVER_TITLE = 'P0: Cutover — move CoinMaster OpenClaw to VPS (single source of truth)';

const ISSUE_BODIES = {
  // Update when we fetch the real issue list; keep as mapping by issue number.
  11: `## Goal (P0)
Enforce launch-critical risk gates before increasing live size.

## Scope
1) owner-auth for live endpoints
2) idempotency/retry/dedupe submit path
3) enforcement hard-stop day 20%
4) enforcement portfolio leverage cap 10x

## Acceptance criteria
- Unauthorized access to live endpoints returns 401/403.
- Duplicate submit requests do not create duplicate orders (idempotency key + dedupe storage).
- When daily drawdown reaches 20%: system closes positions + blocks new opens.
- When aggregate portfolio leverage exceeds 10x: block new opens / force reduce per policy.

## Evidence required (truth mode)
- commit SHA + pushed to origin/main
- smoke test logs (positive+negative)
- production deploy artifact (restart + version)
- GitHub Project status updated before any "done" message.
`,
};

const CUTOVER_BODY = `## Goal (P0)
Move CoinMaster OpenClaw to VPS \`46.225.133.161\` (\`coinmaster24.com\`) as the **only** active bot to avoid context split.

## Plan
See: \`RUNBOOK_VPS_OPENCLAW_CUTOVER.md\` in repo root.

## Checklist
- [ ] VPS: OpenClaw gateway running (user-systemd), workspace ready
- [ ] VPS: Telegram configured but disabled until cutover
- [ ] VPS: Anthropic key added and **probe ok** (fallback works)
- [ ] VPS: GitHub PAT present (repo + Project v2 write)
- [ ] Update GitHub Project issue bodies with continuation instructions
- [ ] Cutover Telegram: disable Mac first, enable VPS second
- [ ] VPS sends: "CoinMaster VPS online (cutover ok)"
- [ ] Disable/stop Mac gateway + cron (cold reserve)
- [ ] Controlled fallback test (primary forced-fail → verify Opus)

## Notes
- Do not use server \`5.78.138.147\` for CoinMaster. It is a friend’s server.
- All progress reports must be artifact-backed (commit/push/deploy/project status).
`;

function mustEnv(name) {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env ${name}`);
  return v;
}

async function ghql(query, variables = {}) {
  const token = mustEnv('GITHUB_TOKEN');
  const res = await fetch('https://api.github.com/graphql', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'authorization': `bearer ${token}`,
      'user-agent': 'coinmaster-gh-project-sync',
    },
    body: JSON.stringify({ query, variables }),
  });
  const json = await res.json();
  if (json.errors?.length) {
    const msg = json.errors.map(e => e.message).join('; ');
    throw new Error(msg);
  }
  return json.data;
}

async function main() {
  const data = await ghql(`
    query($owner:String!, $repo:String!, $projectNumber:Int!) {
      repository(owner:$owner, name:$repo) { id }
      user(login:$owner) {
        projectV2(number:$projectNumber) {
          id
          title
          fields(first:50) {
            nodes {
              __typename
              ... on ProjectV2SingleSelectField { id name options { id name } }
            }
          }
          items(first:100) {
            nodes {
              id
              content {
                __typename
                ... on Issue { id number title body }
              }
            }
          }
        }
      }
    }
  `, { owner: OWNER, repo: REPO, projectNumber: PROJECT_NUMBER });

  const repoId = data.repository.id;
  const project = data.user.projectV2;
  if (!project) throw new Error('Project not found');

  const statusField = project.fields.nodes.find(f => f.__typename === 'ProjectV2SingleSelectField' && f.name === 'Status');
  if (!statusField) throw new Error('Status field not found');

  const statusOptionId = (name) => {
    const opt = statusField.options.find(o => o.name === name);
    return opt?.id;
  };

  const statusTodo = statusOptionId('Todo') || statusOptionId('To do');
  const statusInProgress = statusOptionId('In Progress');

  const items = project.items.nodes
    .map(it => ({ ...it, issue: it.content?.__typename === 'Issue' ? it.content : null }))
    .filter(it => it.issue);

  const byNumber = new Map(items.map(it => [it.issue.number, it]));

  // Determine cutover issue presence.
  let cutoverItem = items.find(it => it.issue.title === CUTOVER_TITLE);

  const planned = {
    updateBodies: Object.keys(ISSUE_BODIES).map(n => Number(n)).filter(n => byNumber.has(n)),
    missingBodies: Object.keys(ISSUE_BODIES).map(n => Number(n)).filter(n => !byNumber.has(n)),
    hasCutover: Boolean(cutoverItem),
    projectId: project.id,
  };

  console.log(JSON.stringify({ apply: APPLY, project: { id: project.id, title: project.title }, planned }, null, 2));
  if (!APPLY) {
    console.log('\nDry-run only. Re-run with --apply to mutate.');
    return;
  }

  // 1) Update issue bodies.
  for (const num of planned.updateBodies) {
    const it = byNumber.get(num);
    const issueId = it.issue.id;
    const body = ISSUE_BODIES[num];
    await ghql(`
      mutation($id:ID!, $body:String!) {
        updateIssue(input:{id:$id, body:$body}) { issue { id number } }
      }
    `, { id: issueId, body });
    console.log(`Updated body for issue #${num}`);
  }

  // 2) Create cutover issue if missing.
  let cutoverIssueId;
  if (!cutoverItem) {
    const created = await ghql(`
      mutation($repoId:ID!, $title:String!, $body:String!) {
        createIssue(input:{repositoryId:$repoId, title:$title, body:$body}) {
          issue { id number title }
        }
      }
    `, { repoId, title: CUTOVER_TITLE, body: CUTOVER_BODY });

    cutoverIssueId = created.createIssue.issue.id;
    console.log(`Created cutover issue #${created.createIssue.issue.number}`);

    const added = await ghql(`
      mutation($projectId:ID!, $contentId:ID!) {
        addProjectV2ItemById(input:{projectId:$projectId, contentId:$contentId}) {
          item { id }
        }
      }
    `, { projectId: project.id, contentId: cutoverIssueId });

    cutoverItem = { id: added.addProjectV2ItemById.item.id, issue: created.createIssue.issue };
    console.log('Added cutover issue to project');
  } else {
    cutoverIssueId = cutoverItem.issue.id;
  }

  // 3) Enforce single In Progress: set cutover to In Progress, set #11 to Todo.
  // NOTE: This assumes we are prioritizing cutover over development right now.
  if (!statusInProgress || !statusTodo) {
    console.log('Status options missing (Todo/In Progress). Skipping status enforcement.');
    return;
  }

  const setStatus = async (itemId, optionId) => {
    await ghql(`
      mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $optionId:String!) {
        updateProjectV2ItemFieldValue(input:{
          projectId:$projectId,
          itemId:$itemId,
          fieldId:$fieldId,
          value:{ singleSelectOptionId:$optionId }
        }) { projectV2Item { id } }
      }
    `, { projectId: project.id, itemId, fieldId: statusField.id, optionId });
  };

  // cutover -> In Progress
  await setStatus(cutoverItem.id, statusInProgress);
  console.log('Set cutover issue status = In Progress');

  // #11 -> Todo (if exists)
  if (byNumber.has(11)) {
    await setStatus(byNumber.get(11).id, statusTodo);
    console.log('Set issue #11 status = Todo (paused during cutover)');
  }
}

main().catch(err => {
  console.error('ERROR:', err.message);
  process.exit(1);
});
