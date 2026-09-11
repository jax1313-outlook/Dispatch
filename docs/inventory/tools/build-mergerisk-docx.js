const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  LevelFormat, convertInchesToTwip, PageOrientation
} = require('docx');

// ---------------------------------------------------------------- palette ---
const INK      = '1A2129';
const INK2     = '55626F';
const INK3     = '7C8894';
const ACCENT   = '1D4E77';
const PROVEN   = '146043';
const RISK     = '8A5A07';
const ABSENT   = '8C2529';
const RULE     = 'C9D2DB';
const HEADFILL = 'EDF1F5';
const SOFTFILL = 'F6F8FA';

const CONTENT_W = 9360;          // 12240 letter - 2 x 1440 margin
const MONO = 'Consolas';
const BODY = 'Calibri';
const DISP = 'Calibri Light';

// ---------------------------------------------------------------- helpers ---
const t = (text, o = {}) => new TextRun({ text, font: o.font || BODY, size: o.size || 21,
  bold: o.bold, italics: o.italics, color: o.color || INK, allCaps: o.caps,
  characterSpacing: o.spacing });

const mono = (text, o = {}) => t(text, { ...o, font: MONO, size: o.size || 18 });

const p = (children, o = {}) => new Paragraph({
  children: Array.isArray(children) ? children : [children],
  spacing: { before: o.before ?? 0, after: o.after ?? 140, line: o.line ?? 276 },
  alignment: o.align,
  indent: o.indent,
  border: o.border,
  shading: o.shading,
  keepNext: o.keepNext,
});

const body = (text, o = {}) => p(t(text, o), o);

const h1 = (text) => new Paragraph({
  text, heading: HeadingLevel.HEADING_1,
  spacing: { before: 360, after: 60 }, keepNext: true,
});
const h2 = (text) => new Paragraph({
  text, heading: HeadingLevel.HEADING_2,
  spacing: { before: 260, after: 80 }, keepNext: true,
});

const eyebrow = (text) => new Paragraph({
  children: [t(text, { size: 15, bold: true, color: INK3, caps: true, spacing: 30 })],
  spacing: { before: 300, after: 40 }, keepNext: true,
});

const rule = () => new Paragraph({
  children: [t('')],
  spacing: { before: 60, after: 160 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 1 } },
});

// evidence / code block
const ev = (lines) => new Paragraph({
  children: lines.flatMap((l, i) => (i ? [new TextRun({ break: 1 }), mono(l, { color: INK2 })]
                                       : [mono(l, { color: INK2 })])),
  spacing: { before: 60, after: 180, line: 260 },
  shading: { type: ShadingType.CLEAR, fill: SOFTFILL },
  indent: { left: 170, right: 170 },
  border: {
    top:    { style: BorderStyle.SINGLE, size: 2, color: RULE, space: 8 },
    bottom: { style: BorderStyle.SINGLE, size: 2, color: RULE, space: 8 },
  },
});

const quote = (text, cite, color = ACCENT) => [
  new Paragraph({
    children: [t(text, { italics: true, size: 21, color: INK })],
    spacing: { before: 120, after: 40, line: 280 },
    indent: { left: 340 },
    border: { left: { style: BorderStyle.SINGLE, size: 12, color, space: 12 } },
  }),
  new Paragraph({
    children: [mono(cite, { size: 16, color: INK3 })],
    spacing: { before: 0, after: 200 },
    indent: { left: 340 },
    border: { left: { style: BorderStyle.SINGLE, size: 12, color, space: 12 } },
  }),
];

const bullet = (children) => new Paragraph({
  children: Array.isArray(children) ? children : [children],
  numbering: { reference: 'dash', level: 0 },
  spacing: { before: 0, after: 110, line: 276 },
});

// ------------------------------------------------------------------ table ---
function table(cols, headers, rows, opts = {}) {
  const widths = cols;
  const cell = (runs, o = {}) => new TableCell({
    width: { size: o.w, type: WidthType.DXA },
    shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill } : undefined,
    margins: { top: 90, left: 130, bottom: 90, right: 130 },
    children: [new Paragraph({
      children: Array.isArray(runs) ? runs : [runs],
      spacing: { before: 0, after: 0, line: 250 },
    })],
  });

  const headRow = new TableRow({
    tableHeader: true,
    children: headers.map((hd, i) =>
      cell(t(hd, { size: 15, bold: true, color: INK3, caps: true, spacing: 24 }),
           { w: widths[i], fill: HEADFILL })),
  });

  const bodyRows = rows.map((r) => new TableRow({
    children: r.map((c, i) => cell(c, { w: widths[i] })),
  }));

  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    borders: {
      top:              { style: BorderStyle.SINGLE, size: 2, color: RULE },
      left:             { style: BorderStyle.SINGLE, size: 2, color: RULE },
      bottom:           { style: BorderStyle.SINGLE, size: 2, color: RULE },
      right:            { style: BorderStyle.SINGLE, size: 2, color: RULE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: RULE },
      insideVertical:   { style: BorderStyle.SINGLE, size: 2, color: RULE },
    },
    rows: [headRow, ...bodyRows],
  });
}

const spacer = (after = 200) => new Paragraph({ children: [t('')], spacing: { after } });

// finding heading: "F-01  Title"
const finding = (ref, title) => new Paragraph({
  children: [
    mono(ref + '   ', { size: 17, bold: true, color: RISK }),
    t(title, { size: 23, bold: true, color: INK, font: DISP }),
  ],
  heading: HeadingLevel.HEADING_2,
  spacing: { before: 280, after: 90 },
  keepNext: true,
});

// ================================================================= CONTENT ==
const children = [];

children.push(new Paragraph({
  children: [t('Forensic Recovery  ·  Companion Report', { size: 16, bold: true, color: INK3, caps: true, spacing: 40 })],
  spacing: { after: 100 },
}));
children.push(new Paragraph({
  children: [t('Merge Risk Assessment', { size: 52, bold: true, color: INK, font: DISP })],
  spacing: { after: 120 }, keepNext: true,
}));
children.push(new Paragraph({
  children: [t('What it would actually cost to land the three bodies of unmerged work — measured by test-merging each one, not estimated.', { size: 23, color: INK2 })],
  spacing: { after: 200 }, keepNext: true,
}));

children.push(table([2100, 7260],
  ['Field', 'Value'],
  [
    [t('Authority', { bold: true }), t('Mike Zachary — final authority. This assessment measures; it decides nothing and recommends nothing.')],
    [t('Assessed', { bold: true }),  t('2026-09-11')],
    [t('Targets', { bold: true }),   t('Dispatch/joe-portal · Hold/integration · DISPATCH_FINAL_BLUEPRINT_v1.md')],
    [t('Companion to', { bold: true }), t('“What Has Actually Been Built” — the findings report. This is a separate document and does not restate it.')],
    [t('Location', { bold: true }),  mono('jax1313-outlook/Dispatch · docs/inventory/MERGE_RISK_ASSESSMENT.md')],
  ]));
children.push(spacer(240));

children.push(new Paragraph({
  children: [t('METHOD   ', { size: 16, bold: true, color: INK3, spacing: 30 }),
             t('ASSESSMENT ONLY — every test merge ran in a throwaway worktree and was abandoned. Nothing was merged, committed to a target branch, or pushed.', { size: 21, bold: true, color: ACCENT })],
  spacing: { before: 0, after: 240 },
  shading: { type: ShadingType.CLEAR, fill: 'E7EFF6' },
  indent: { left: 150, right: 150 },
  border: { left: { style: BorderStyle.SINGLE, size: 14, color: ACCENT, space: 10 } },
}));

children.push(rule());

// ---- summary ----
children.push(eyebrow('Summary'));
children.push(h1('Three targets, three different decisions'));

children.push(table([2180, 1500, 1500, 1680, 2500],
  ['Target', 'Mechanical risk', 'Doctrinal risk', 'Verified state', 'Character'],
  [
    [mono('joe-portal', { size: 17 }),
     t('HIGH', { bold: true, color: ABSENT, size: 19 }),
     t('HIGH', { bold: true, color: ABSENT, size: 19 }),
     t('Not run', { size: 19, color: INK2 }),
     t('Not a merge. A reconciliation of two parallel architectures.', { size: 19, color: INK2 })],
    [mono('Hold/integration', { size: 17 }),
     t('NONE', { bold: true, color: PROVEN, size: 19 }),
     t('LOW', { bold: true, color: PROVEN, size: 19 }),
     t('469 passed, 0 failed', { bold: true, color: PROVEN, size: 19 }),
     t('Code is sound. The risk sits entirely outside git.', { size: 19, color: INK2 })],
    [mono('Final Blueprint', { size: 17 }),
     t('NONE', { bold: true, color: PROVEN, size: 19 }),
     t('HIGH', { bold: true, color: ABSENT, size: 19 }),
     t('n/a', { size: 19, color: INK2 }),
     t('A stale draft that contradicts settled doctrine.', { size: 19, color: INK2 })],
  ]));
children.push(new Paragraph({
  children: [t('These are not variations of one problem. They need three different decisions.', { size: 20, color: INK2, italics: true })],
  spacing: { before: 120, after: 200 },
}));

children.push(rule());

// ---- 1 ----
children.push(eyebrow('01 · Dispatch'));
children.push(h1('joe-portal — high risk, both mechanical and doctrinal'));

children.push(table([3400, 5960],
  ['Measure', 'Value'],
  [
    [t('Merge base'), [mono('62af426'), t('  —  '), t('2026-08-03 11:52', { bold: true })]],
    [t('main HEAD'), mono('3c03ab2  ·  2026-08-31')],
    [t('joe-portal HEAD'), mono('02b0e75  ·  2026-09-03')],
    [t('Commits ahead of main'), t('48', { bold: true })],
    [t('Commits BEHIND main'), t('188', { bold: true, color: ABSENT })],
    [t('Files changed on both sides'), t('9')],
    [t('Merge conflicts'), t('5  (2 × add/add, 3 × content)', { bold: true, color: ABSENT })],
    [t('Test files'), t('96 on branch vs 136 on main')],
    [t('Test files deleted by branch'), t('0', { color: PROVEN, bold: true })],
  ]));
children.push(spacer(160));

children.push(body('The framing in the inventory was incomplete, and the correction matters. joe-portal is not 48 commits of new work sitting on top of current main. It forked on 2026-08-03, one day after Dispatch’s first commit, and is 188 commits behind. Almost the entire freight platform — the Spine, IFTA, the connector boundary, the Driver Portal, authentication — was built on main after this branch left.'));

children.push(h2('The conflicts'));
children.push(ev([
  'CONFLICT (add/add)  dispatch/connectors/__init__.py',
  'CONFLICT (add/add)  dispatch/connectors/registry.py',
  'CONFLICT (content)  portal/models/publisher.py',
  'CONFLICT (content)  portal/routes/__init__.py',
  'CONFLICT (content)  portal/templates/base.html',
]));

children.push(h2('Why the connector conflict is not a normal conflict'));
children.push(body('Both sides independently built dispatch/connectors/ — hence add/add. They share no API surface whatsoever.'));

children.push(table([2000, 3680, 3680],
  ['', 'main', 'joe-portal'],
  [
    [t('Files', { bold: true }), t('14 — contract.py, boundary.py, audit.py, mock.py + 8 provider connectors'), t('3 — __init__, registry, outlook_mail')],
    [t('registry.py', { bold: true }), t('115 lines'), t('63 lines')],
    [t('API', { bold: true }), mono('get() · all_connectors() · status_board()'), mono('mail() · mail_status() · calendar_status() · status()')],
    [t('Audit trail', { bold: true }), t('audit.py — “one row for every attempt, including the refusals” (§6.8)'), t('none', { color: ABSENT, bold: true })],
    [t('Fixed contract', { bold: true }), t('contract.py + boundary.py'), t('none', { color: ABSENT, bold: true })],
    [t('Design', { bold: true }), t('registry of declared connectors, governed'), t('probe-on-demand, never caches a LIVE')],
  ]));
children.push(spacer(160));

children.push(body('Both honour the fixed truth vocabulary. Both are defensible designs. They are not compatible. Verified: neither side calls the other’s API — no occurrence of get / all_connectors / status_board anywhere on the branch, and none of mail / mail_status / calendar_status anywhere on main. So:'));
children.push(bullet([t('Keep main’s registry ', { bold: true }), t('→ four branch call sites break immediately (portal/cockpit.py:533, portal/routes/joe_api.py:423, portal/routes/joe_portal.py:545, and tests/test_outlook_connectors.py).')]));
children.push(bullet([t('Keep the branch’s registry ', { bold: true }), t('→ deletes contract.py, boundary.py, audit.py, mock.py and all 8 provider connectors. A direct violation of CLAUDE.md §5.4 (“a governed boundary with a fixed contract, an audit trail, and an honest status”) and §7 (never weaken).')]));
children.push(body('There is no correct side to take. The branch’s outlook_mail.py — the ecosystem’s only Dispatch-side Outlook implementation — would have to be rewritten against main’s connector contract.'));

children.push(h2('The second trap'));
children.push(body('The branch’s portal/routes/__init__.py registers pages, api, decisions, pipeline, dispatch_api, joe_bp and joe_api. It does not register auth_bp, driver_portal_bp or stakeholder_bp — because they did not exist when it forked.'));
children.push(body('Taking the branch side of that file would silently remove login/logout, the Driver Portal and the stakeholder view from the application. Under CLAUDE.md §7 that is weakening fail-closed authentication. It is easy to resolve correctly — keep main’s registrations, add joe’s two — and recorded here because it is exactly the kind of conflict a hurried resolution gets wrong, and the failure is silent.'));

children.push(h2('What is not at risk'));
children.push(bullet(t('The branch deletes no tests. The 59 main test files absent from it were added after the fork; a merge keeps them.')));
children.push(bullet(t('No Manager code on the branch — dispatch/manager/ is empty there.')));
children.push(bullet(t('dispatch/services.py, portal/models/sandbox.py, portal/routes/api.py and tests/test_booking.py auto-merged cleanly.')));

children.push(body('Unknown: whether the branch’s tests pass. They were not run — the two sides expect different connector APIs, so a meaningful run requires the reconciliation decision first.', { italics: true, color: INK2 }));

children.push(rule());

// ---- 2 ----
children.push(eyebrow('02 · Hold'));
children.push(h1('integration — zero mechanical risk, and the code is verified green'));

children.push(table([3400, 5960],
  ['Measure', 'Value'],
  [
    [t('Merge base'), [mono('484e40d'), t('  —  which is '), t('main HEAD itself', { bold: true })]],
    [t('Commits ahead'), t('75', { bold: true })],
    [t('Commits behind'), t('0', { bold: true, color: PROVEN })],
    [t('Files changed on both sides'), t('0', { bold: true, color: PROVEN })],
    [t('Merge conflicts'), t('0 — main is a direct ancestor. Fast-forward.', { bold: true, color: PROVEN })],
    [t('Change profile'), t('199 added · 7 modified · 14 renamed · 0 deleted')],
    [t('Diff'), t('220 files, +22,113 insertions, −59 deletions')],
  ]));
children.push(spacer(160));

children.push(body('The 7 modified files are all documentation and schemas — CONTRACT_REGISTER.md, evidence_record.schema.json, DECISION_LOG.md and four lane NOTES.md. Nothing is destroyed.'));

children.push(h2('Verified by running it'));
children.push(body('The integration branch was checked out and its suite executed:'));
children.push(ev(['469 passed in 7.16s']));
children.push(body('0 failed, 0 errors. This is the only test suite actually executed across this engagement, and it passes clean. The inventory’s static count of 428 test functions under-counted the real total of 469, because of parametrisation.'));

children.push(h2('Security check'));
children.push(bullet(t('No committed secrets. Scanned for sk-ant- patterns, api_key literals, .env, credential and .key files across the branch. Nothing found.')));
children.push(bullet(t('docs/lanes/C/NOTES.md records the practice explicitly: a real API key was supplied in-session, “never written to any file (not the sandbox config, not .env, nothing committed) — used only as a transient environment variable… then discarded.” The scan corroborates that.')));

children.push(h2('One correction to the findings report'));
children.push(body('The findings report states that only Joe-Assistant had capabilities proven against a live external service. That is not quite right. Hold/docs/lanes/C/NOTES.md Session 3 (2026-08-05) records the vision extractor being exercised live against the real Anthropic API, which found and fixed a real bug.'));
children.push(body('The precise limit matters: the image was synthesised with Pillow, because “no real scanned receipt existed in this build environment.” So it is live-API proof, not real-document proof. Hold’s OCR path has never seen an actual receipt.'));

children.push(h2('Character'));
children.push(body('The mechanical risk is zero and the code is verified green. The risk is entirely outside git, and it is governance rather than engineering:'));
children.push(bullet(t('Hold/README.md states the repository is “Sandbox configuration only, until Mike Zachary cuts over after merge 5,” and that it is not the system of record.')));
children.push(bullet(t('docs/governance/APPROVAL_REGISTER.md holds 14 approval items whose state this assessment did not evaluate.')));
children.push(bullet(t('Merging integration → Hold/main is a different act from promoting Hold’s code into Dispatch. The second is where the real architectural question sits — Hold’s src/dispatch/ tree is a separate implementation from Dispatch’s dispatch/ package, with its own IFTA engine alongside the one already in Dispatch.')));
children.push(body('Unknown: whether “merge 5” has occurred, and what the 14 approval items currently say. Neither is recorded anywhere this assessment could reach.', { italics: true, color: INK2 }));

children.push(rule());

// ---- 3 ----
children.push(eyebrow('03 · Claude-3 and three other repositories'));
children.push(h1('DISPATCH_FINAL_BLUEPRINT_v1.md — no mechanical risk, high doctrinal risk'));

children.push(table([3400, 5960],
  ['Measure', 'Value'],
  [
    [t('Size'), [t('1,133 lines, blob '), mono('ffb23f9')]],
    [t('Locations'), t('13, across 4 repositories — 0 default branches', { bold: true })],
    [t('Branch tip'), t('2026-08-11')],
    [t('Mechanical conflict'), t('None — a new file; nothing to collide with', { color: PROVEN })],
    [t('Would it break CI?'), t('No. tests/test_repository_doctrine.py scans *.py and portal/*.html only')],
  ]));
children.push(spacer(160));

children.push(h2('The actual risk'));
children.push(body('The Blueprint contains a full “5. Manager Blueprint” section — 45 Manager mentions, including §5.9 and mandates such as “Manager must never: approve on Mike’s behalf…”. It carries no disclaimer that Manager was never built.'));
children.push(...quote('There is no Manager component in the current architecture. Do not create, restore, reference, or infer a Manager component, Manager agent, or Manager authority.', 'Dispatch/CLAUDE.md §5.6', ABSENT));
children.push(body('Landing this document in Dispatch as-is introduces a governing artefact that mandates a component current doctrine forbids. It would not fail a test — which makes it more dangerous, not less, because nothing mechanical would catch it.'));

children.push(h2('It is also stale'));
children.push(body('Dated 2026-08-11, it predates at least these settled decisions in DECISION_LOG.md:'));
children.push(bullet(t('2026-08-21 — Build Matrix adopted; architectural adjudication (Spine ownership partitions, state models, load identity, Driver-First)')));
children.push(bullet(t('2026-08-21 — C3 status-change audit symmetry')));
children.push(bullet(t('2026-08-23 — W0-3 Portal adjudication; CF-04 (Opportunity advises; the Spine decides)')));
children.push(bullet(t('2026-08-25 — General Contractor Doctrine')));
children.push(body('Its own header calls it a “Final Blueprint Draft” and states it “does not authorize deployment.”'));

children.push(h2('Character'));
children.push(body('Not a merge problem — a doctrine-conflict problem. CLAUDE.md §7 already prescribes the handling: “If code conflicts with approved doctrine, report the conflict,” and “Do not edit old decisions to hide their history. Mark them SUPERSEDED and cite the ruling that replaced them.” This assessment reports it. What happens next is Mike’s call.'));
children.push(body('Note that three repositories — L2-intelligence-agent., Library and Publisher — were built while recording this document as “not found in any repo in scope.” Whatever is decided, those three were built without their stated governing blueprint.'));

children.push(rule());

// ---- limits ----
children.push(eyebrow('04 · Limits'));
children.push(h1('What this assessment did not do'));
children.push(bullet([t('Did not merge anything. ', { bold: true }), t('All test merges ran in throwaway worktrees and were abandoned; nothing was committed to a target branch or pushed.')]));
children.push(bullet([t('Did not run joe-portal’s tests. ', { bold: true }), t('A meaningful run requires the connector reconciliation decision first.')]));
children.push(bullet([t('Did not run Dispatch’s full suite. ', { bold: true }), t('Only tests/test_repository_doctrine.py — 44 passed — earlier in this engagement.')]));
children.push(bullet([t('Did not read the 14 approval items ', { bold: true }), t('in Hold/docs/governance/APPROVAL_REGISTER.md.')]));
children.push(bullet([t('Did not assess the remaining off-main population ', { bold: true }), t('beyond these three targets — 692 files exist outside default branches in total.')]));
children.push(bullet([t('Makes no recommendation. ', { bold: true }), t('Mike decides.')]));

children.push(rule());
children.push(new Paragraph({
  children: [
    mono('Source — docs/inventory/MERGE_RISK_ASSESSMENT.md', { size: 16, color: INK3 }),
    new TextRun({ break: 1 }),
    mono('Companion to “What Has Actually Been Built”. Kept as a separate report by instruction.', { size: 16, color: INK3 }),
    new TextRun({ break: 1 }),
    mono('Mike Zachary is final authority. This assessment measures; it decides nothing.', { size: 16, color: INK3 }),
  ],
  spacing: { before: 60, after: 0, line: 280 },
}));

const doc = new Document({
  creator: 'Level 1 Transport — Dispatch Recovery',
  title: 'Merge Risk Assessment',
  description: 'Measured merge risk for the three unmerged bodies of work.',
  numbering: { config: [{ reference: 'dash', levels: [{ level: 0, format: LevelFormat.BULLET, text: '–',
    alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 360, hanging: 220 } }, run: { color: INK3 } } }] }] },
  styles: { default: {
    document: { run: { font: BODY, size: 21, color: INK }, paragraph: { spacing: { line: 276 } } },
    heading1: { run: { font: DISP, size: 34, bold: true, color: INK }, paragraph: { spacing: { before: 360, after: 60 } } },
    heading2: { run: { font: DISP, size: 24, bold: true, color: INK }, paragraph: { spacing: { before: 260, after: 80 } } },
  } },
  sections: [{ properties: { page: {
    size: { width: 12240, height: 15840, orientation: PageOrientation.PORTRAIT },
    margin: { top: 1300, right: 1440, bottom: 1300, left: 1440 } } }, children }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(process.argv[2] || 'mergerisk.docx', buf);
  console.log('written:', process.argv[2] || 'mergerisk.docx', buf.length, 'bytes');
});
