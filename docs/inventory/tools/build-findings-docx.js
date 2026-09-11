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

// ---- masthead ----
children.push(new Paragraph({
  children: [t('Forensic Recovery  ·  Findings Report', { size: 16, bold: true, color: INK3, caps: true, spacing: 40 })],
  spacing: { after: 100 },
}));
children.push(new Paragraph({
  children: [t('What Has Actually Been Built', { size: 52, bold: true, color: INK, font: DISP })],
  spacing: { after: 120 }, keepNext: true,
}));
children.push(new Paragraph({
  children: [t('A measured inventory of all fourteen repositories in the Level 1 Transport ecosystem — and what the measurement found sitting outside them.', { size: 23, color: INK2 })],
  spacing: { after: 200 }, keepNext: true,
}));

children.push(table([2100, 7260],
  ['Field', 'Value'],
  [
    [t('Authority', { bold: true }),  t('Mike Zachary — final authority. This report records findings; it decides nothing.')],
    [t('Compiled', { bold: true }),   t('2026-09-05')],
    [t('Issued', { bold: true }),     t('2026-09-11')],
    [t('Scope', { bold: true }),      t('All 14 repositories in the jax1313-outlook account. None skipped, none combined.')],
    [t('Location', { bold: true }),   mono('jax1313-outlook/Dispatch · docs/inventory/')],
    [t('Branch', { bold: true }),     mono('claude/repository-inventory-recovery-r0eiji')],
  ]));
children.push(spacer(240));

// status banners
children.push(new Paragraph({
  children: [t('STATUS   ', { size: 16, bold: true, color: INK3, spacing: 30 }),
             t('Repository inventory — COMPLETE, 14 of 14', { size: 21, bold: true, color: PROVEN })],
  spacing: { before: 0, after: 60 },
  shading: { type: ShadingType.CLEAR, fill: 'E6F1EB' },
  indent: { left: 150, right: 150 },
  border: { left: { style: BorderStyle.SINGLE, size: 14, color: PROVEN, space: 10 } },
}));
children.push(new Paragraph({
  children: [t('STATUS   ', { size: 16, bold: true, color: INK3, spacing: 30 }),
             t('D:\\ forensic inventory — BLOCKED, not started', { size: 21, bold: true, color: ABSENT })],
  spacing: { before: 0, after: 240 },
  shading: { type: ShadingType.CLEAR, fill: 'F7E9E9' },
  indent: { left: 150, right: 150 },
  border: { left: { style: BorderStyle.SINGLE, size: 14, color: ABSENT, space: 10 } },
}));

children.push(rule());

// ---- 1. At a glance ----
children.push(eyebrow('01 · At a glance'));
children.push(h1('The measurement'));

children.push(table([2400, 6960],
  ['Figure', 'What it counts'],
  [
    [t('14', { bold: true, size: 26 }),     t('repositories inventoried — 12 with content, 2 entirely empty')],
    [t('1,218', { bold: true, size: 26 }),  t('files hashed by git blob ID and compared across all repositories')],
    [t('117', { bold: true, size: 26 }),    t('branches examined, file by file, against their own default branch')],
    [t('692', { bold: true, size: 26, color: RISK }), t('files that exist on NO default branch anywhere')],
    [t('~127,000', { bold: true, size: 26 }), t('lines of Python across the ecosystem')],
    [t('1', { bold: true, size: 26 }),      t('repository with capabilities proven against live external services')],
  ]));
children.push(spacer(200));

children.push(body('Every repository was cloned and read. Uniqueness was measured, not judged: every tracked file in the twelve non-empty repositories was hashed by its git blob ID and compared across all of them. Then every branch of every repository was compared file-by-file against its own default branch.'));
children.push(body('That second pass is where this report earns its keep. Reading default branches alone — which is what a person or a tool normally does — misses roughly a third of the work that exists.'));

children.push(rule());

// ---- 2. Headline ----
children.push(eyebrow('02 · Headline finding'));
children.push(h1('A third of the work is not on any main branch'));
children.push(body('692 distinct files exist only on unmerged branches. This is not stale scratch work. It includes a complete subsystem, the newest code in the entire ecosystem, and the single document that two whole repositories were created to produce.'));
children.push(spacer(120));

children.push(table([2760, 1900, 2100, 2600],
  ['Repository', 'On default branch', 'Only on branches', 'Share off-main'],
  [
    [mono('Dispatch'),               mono('459'), mono('245', { bold: true, color: RISK }), t('35%')],
    [mono('Hold'),                   mono('68'),  mono('224', { bold: true, color: RISK }), t('77%')],
    [mono('Claude-3'),               mono('29'),  mono('87',  { bold: true, color: RISK }), t('75%')],
    [mono('Jules'),                  mono('41'),  mono('70',  { bold: true, color: RISK }), t('63%')],
    [mono('Library'),                mono('40'),  mono('22',  { bold: true, color: RISK }), t('35%')],
    [mono('L2-intelligence-agent.'), mono('84'),  mono('21',  { bold: true, color: RISK }), t('20%')],
    [mono('Claude'),                 mono('23'),  mono('19',  { bold: true, color: RISK }), t('45%')],
    [mono('Claude-2'),               mono('17'),  mono('4',   { bold: true, color: RISK }), t('19%')],
  ]));
children.push(new Paragraph({
  children: [t('The four repositories not listed — Joe-Assistant, Dispatch-Old, Publisher and premium-logistics-platform- — have no branch-only files at all.', { size: 19, color: INK2 })],
  spacing: { before: 100, after: 200 },
}));

children.push(rule());

// ---- 3. Findings ----
children.push(eyebrow('03 · Principal findings'));
children.push(h1('What the branch pass turned up'));

children.push(finding('F-01', 'Hold’s main branch contains no code. Its integration branch contains a working system.'));
children.push(body('A builder reading Hold’s default branch would conclude it is an empty scaffold — 68 files, of which 17 are .gitkeep placeholders, and zero lines of Python. Its integration branch holds 267 files, 148 modules and 13,770 lines: receipt intake with OCR extraction, a full IFTA engine, an IFTA Clerk with review dashboard, prepare-this-quarter workflow and payment-recommendation engine, a Reports lane with a fidelity gate, a Manager queue and a Librarian spine.'));
children.push(body('It was built across 22 branches in roughly 26 hours on 2026-08-04 and 05, and never merged. Nothing in the repository records why.'));
children.push(ev([
  'main          68 files      0 python files        0 LOC',
  'integration  267 files    148 python files   13,770 LOC    428 test functions',
]));

children.push(finding('F-02', 'The newest work in the ecosystem sits unmerged, 48 commits ahead.'));
children.push(body('Dispatch’s joe-portal branch tips at 2026-09-03 — newer than main (2026-08-31) — and carries roughly 14,000 lines that are on no default branch: a Driver Cockpit (982 lines, with a 956-line test file), a JOE Portal and API, mission and scheduling engines, a booking board, arrival notices, and an Outlook mail connector.'));
children.push(body('That connector matters. Dispatch’s main branch has only the Outlook interface, with no provider behind it.'));
children.push(ev([
  'branch joe-portal  ·  48 commits ahead of main  ·  tip 2026-09-03',
  '59 files not on main  ·  19 test files',
]));

children.push(finding('F-03', 'The Final Blueprint exists — in thirteen places, on no default branch.'));
children.push(body('DISPATCH_FINAL_BLUEPRINT_v1.md is 1,133 lines and is the stated purpose of two entire repositories. It exists as an identical blob in thirteen locations across four repositories, and on no default branch anywhere.'));
children.push(body('The consequence is concrete, not theoretical. L2-intelligence-agent. records it in KNOWN_GAPS.md as “not found in any repo in scope,” and that repository, Library and Publisher were each built without it. Two further documents cited by name and section as governing authority by three repositories — DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md and LIBRARY_INGESTION_RULE.md — are in exactly the same condition.'));
children.push(ev([
  'blob ffb23f9  ·  1,133 lines',
  'Claude-3, Jules, Library (1 branch each) + Dispatch (10 stage* branches)',
  'default branches carrying it: 0',
]));

children.push(finding('F-04', 'Manager exists as running, tested code in three places.'));
children.push(body('Dispatch’s CLAUDE.md §5.6 states there is no Manager component, and that docs/MANAGER.md records a capability “named in planning and never built.” That statement is accurate about Dispatch’s main branch. It is not accurate about the ecosystem.'));
children.push(bullet([mono('Dispatch-Old/cin_lite/manager.py'), t(' — 101 lines, merged, tested. Issues MGR- tickets with human_decision_required defaulting to True.')]));
children.push(bullet([mono('Hold'), t(' — a Manager queue with its own JSON schema and conformance test, on the integration branch.')]));
children.push(bullet([mono('Dispatch/dispatch/manager/'), t(' — 7–8 modules, 767–866 lines, across five branches.')]));
children.push(body('Manager is additionally documented in nine repositories, has its only constitution in Hold, and its only independent architectural review in Claude. Recorded as fact; no recommendation is offered.'));

children.push(finding('F-05', 'Only one repository has been proven against anything real.'));
children.push(body('Joe-Assistant is the sole repository whose capabilities were measured by running the program against live external services. Its own truth matrix records the measurement date and method, and is equally plain about what failed.'));
children.push(ev([
  'PROVEN   launch in 4.6s · live Outlook COM read (21 write calls refused)',
  '         live M365 Copilot reasoning · MSAL+DPAPI auth verified byte-level',
  '         34-doc library retrieval · audible speech output',
  'PARTIAL  calendar & contact answers · multi-turn reasoning (non-deterministic)',
  'BLOCKED  voice input — no person has ever spoken to it',
  'ABSENT   audio-activity detection · the Dispatch connection itself',
]));
children.push(body('Against that, Dispatch’s own CLAUDE.md §8 states that nothing in it has ever run on Mike’s Windows laptop, and that every external system is UNCONFIGURED — no ELD, GPS, traffic, weather, load board, mapping, accounting, scanner or Outlook connection exists.'));

children.push(finding('F-06', 'Named everywhere, existing nowhere.'));
children.push(body('Four things are referenced by documents across the ecosystem and were not found on any branch of any repository:'));
children.push(bullet([mono('CONSTITUTION.md'), t(' — declared by Hold/README.md to be the Level 1 Transport master constitution and supreme law over all governed development work. It is in none of the fourteen repositories.')]));
children.push(bullet([mono('Jules-2'), t(', '), mono('Jules-3'), t(', '), mono('Test-Grounds'), t(' — named as working instances of the promotion pipeline. None exists in the account.')]));
children.push(bullet(t('Nine Publisher source artefacts named in Publisher/KNOWN_GAPS.md, including publisher_mvp.py and Visibility_SOP.docx.')));
children.push(bullet(t('A load-board sweep adapter — which Claude-3/CLONE_MAP.md calls “the biggest genuine build gap.”')));

children.push(finding('F-07', 'Two repositories are entirely empty.'));
children.push(body('Route-Risk and SAM were created 115 seconds apart on 2026-08-19 and contain zero commits, zero branches and zero files. Both capabilities are real and implemented — elsewhere. Route Risk lives in Dispatch (672 matching lines across a domain module, a connector, an events table and a scoring factor); SAM capability lives in Dispatch-Old/cin_lite/, Dispatch/cin_lite/ and three unmerged branches.'));
children.push(body('The emptiness is reported so it is a recorded finding rather than an assumption — and so no future reader mistakes the presence of a name for the presence of work.'));

children.push(rule());

// ---- 4. Ledger ----
children.push(eyebrow('04 · The ledger'));
children.push(h1('Fourteen repositories'));

const L = (name, py, br, off, status, statusColor, note) => [
  mono(name, { size: 17 }),
  mono(py, { size: 17 }),
  mono(br, { size: 17 }),
  mono(off, { size: 17, color: off !== '0' && off !== '—' ? RISK : INK2 }),
  [t(status + '  ', { size: 16, bold: true, color: statusColor, caps: true }), t(note, { size: 19, color: INK2 })],
];

children.push(table([2260, 1300, 780, 900, 4120],
  ['Repository', 'Python', 'Br.', 'Off-main', 'Standing'],
  [
    L('Dispatch', '82,699', '64', '245', 'Implemented', ACCENT, 'The freight platform. System of Record by its own doctrine. Never run on Mike’s laptop.'),
    L('Joe-Assistant', '34,000', '1', '0', 'Proven', PROVEN, 'JOE. The only live-service integration in the ecosystem.'),
    L('Hold', '0 / 13,770', '24', '224', 'On branch', RISK, 'Receipt/IFTA/Reports build. Zero code on main.'),
    L('Dispatch-Old', '3,906', '1', '0', 'Implemented', ACCENT, 'CIN-Lite predecessor. The only merged Manager and the only hosting config.'),
    L('L2-intelligence-agent.', '2,006', '3', '21', 'Implemented', ACCENT, 'Intelligence department. Integration-ready, unmerged since 2026-08-11.'),
    L('Library', '875', '3', '22', 'Implemented', ACCENT, 'Library department. Integration-ready, unmerged.'),
    L('Publisher', '872', '2', '0', 'Implemented', ACCENT, 'Publisher department. Integration-ready, unmerged.'),
    L('Claude-3', '0 / 1,482', '6', '87', 'On branch', RISK, 'Doctrine corpus and the prior recovery mission. No code on main.'),
    L('Jules', '717', '9', '70', 'Implemented', ACCENT, 'Four-portal presentation layer. The only public website.'),
    L('Claude', '252', '3', '19', 'Implemented', ACCENT, 'Spine prototype. No tests, no CI. Quiet since 2026-08-10.'),
    L('Claude-2', '0', '2', '4', 'Documented', INK3, 'Clean-room analysis. Lifespan: 3 h 39 min.'),
    L('premium-logistics-platform-', '0', '1', '0', 'Documented', INK3, 'The only brand and visual identity material anywhere. Lifespan: 13 min.'),
    L('Route-Risk', '—', '0', '—', 'Empty', ABSENT, 'Zero commits, branches, files.'),
    L('SAM', '—', '0', '—', 'Empty', ABSENT, 'Zero commits, branches, files.'),
  ]));
children.push(new Paragraph({
  children: [t('Where two Python figures are shown, the first is the default branch and the second is the largest branch. Each repository has its own dossier with identical sections; full detail lives in Dispatch/docs/inventory/.', { size: 19, color: INK2 })],
  spacing: { before: 120, after: 200 },
}));

children.push(rule());

// ---- 5. Blocked mission ----
children.push(eyebrow('05 · Blocked mission'));
children.push(h1('The D:\\ forensic inventory was not started'));
children.push(body('A second mission commissioned a complete forensic inventory of the D:\\ drive. It could not be executed. The session runs in an isolated Linux cloud container, and D:\\ is not reachable from it. This was verified, not assumed:'));
children.push(spacer(100));

children.push(table([2900, 6460],
  ['Check', 'Result'],
  [
    [t('Mounted filesystems'),   t('Only container-local virtual disks. No Windows volume.')],
    [t('Kernel FS support'),     [mono('cifs'), t(', '), mono('smb3'), t(', '), mono('nfs'), t(', '), mono('nfs4'), t(' — none available')]],
    [t('Remote-mount tooling'),  [mono('mount.cifs'), t(', '), mono('smbclient'), t(', '), mono('sshfs'), t(', '), mono('rclone'), t(', '), mono('net'), t(' — all absent')]],
    [t('Host-share transport'),  t('No 9p, no virtiofs')],
    [t('User-facing mounts'),    [mono('/mnt/attach'), t(' and '), mono('/mnt/user-data/working'), t(' — both empty')]],
  ]));
children.push(spacer(200));

children.push(...quote(
  'Not reachable, ever, from this session: the local path D:\\DISPATCH_AND_SAM_RECOVERY and everything under it… This is a hard environment boundary, not a permission that could be granted.',
  'Claude-3/RECOVERY_REPORT.md — the same boundary, hit by the prior mission'));

children.push(new Paragraph({
  children: [
    t('None of the four commissioned deliverables exist', { bold: true }),
    t(', and none should be represented as existing. Every Required Question is recorded as UNKNOWN. Producing those matrices from a container that cannot see the drive would mean inventing evidence — the one thing the mission expressly forbids.'),
  ],
  spacing: { before: 100, after: 200, line: 276 },
  shading: { type: ShadingType.CLEAR, fill: SOFTFILL },
  indent: { left: 170, right: 170 },
  border: {
    top:    { style: BorderStyle.SINGLE, size: 2, color: RULE, space: 10 },
    bottom: { style: BorderStyle.SINGLE, size: 2, color: RULE, space: 10 },
  },
}));

children.push(h2('Two routes to executing it'));
children.push(bullet([t('Run it where the drive is. ', { bold: true }), t('Claude Code runs natively on Windows. On the machine holding D:\\, re-issue the same mission prompt — that gives direct access to file contents, not just metadata, with no proxy and no upload step.')]));
children.push(bullet([t('Or collect and send. ', { bold: true }), t('A strictly read-only collector, Collect-DDriveForensics.ps1, now sits in Dispatch/docs/inventory/tools/. It produces a small metadata package (typically 1–20 MB) that can be analysed remotely.')]));

children.push(body('The collector hashes files with the git blob SHA-1 — the same identifier git itself uses. That is deliberate: it makes D:\\ evidence join directly against this inventory, which was built by hashing all 1,218 tracked files the same way. Duplicated, only-on-D:\\, newer-than-GitHub and older-than-GitHub stop being judgement calls and become mechanical comparisons. It captures tracked blobs across every ref, so an unpushed branch on a local clone reads as unpushed rather than as missing work — which, given F-01 through F-03, is the distinction that matters most.'));

children.push(new Paragraph({
  children: [
    t('Collector verification. ', { bold: true }),
    t('It parses clean under PowerShell 7.4.6; runs end-to-end over 14 git trees and 1,313 files, exporting 26,727 tracked blobs with zero errors; and independently reproduced the known five-way doctrine-set duplication across Claude, Claude-2, Claude-3, Library and Jules. One defect was found and fixed during testing — .git internals were 74% of rows and drowned the newest-file and duplicate analyses. '),
    t('It has not been run on Windows; that remains UNVERIFIED.', { bold: true }),
  ],
  spacing: { before: 100, after: 200, line: 276 },
  shading: { type: ShadingType.CLEAR, fill: SOFTFILL },
  indent: { left: 170, right: 170 },
  border: {
    top:    { style: BorderStyle.SINGLE, size: 2, color: RULE, space: 10 },
    bottom: { style: BorderStyle.SINGLE, size: 2, color: RULE, space: 10 },
  },
}));

children.push(rule());

// ---- 6. Limits ----
children.push(eyebrow('06 · Limits'));
children.push(h1('What this report does not establish'));

children.push(bullet([t('No test suite was run. ', { bold: true }), t('Every test count here — roughly 5,150 across the ecosystem — is a static count of test functions. It is evidence that tests exist, not that they pass. The one exception: tests/test_repository_doctrine.py was run against the inventory’s own additions and passed, 44 tests.')]));
children.push(bullet([t('Off-main code was enumerated, not read. ', { bold: true }), t('The branch pass established that 692 files exist outside default branches and identified the subsystems. It did not assess whether any of that work duplicates, supersedes or conflicts with what is on main.')]));
children.push(bullet([t('Nothing here is operational proof. ', { bold: true }), t('Dispatch’s own doctrine draws the line: the repository test suite is evidence of software behaviour only. Every Dispatch capability in this report is IMPLEMENTED and not OPERATIONALLY PROVEN.')]));
children.push(bullet([t('No recommendations are made. ', { bold: true }), t('This was commissioned as a recovery and inventory operation. It contains no design proposal, no refactor or cleanup proposal, no archive recommendation, and no ranking of repositories by importance. What to do about any finding is Mike’s call.')]));

children.push(spacer(120));
children.push(...quote(
  'The working system is spread across four places: Dispatch’s main branch, Dispatch’s unmerged branches, Hold’s integration branch, and Joe-Assistant. Reading any one of them alone understates the whole by a wide margin.',
  'MASTER_CAPABILITY_MATRIX.md', RISK));

children.push(rule());

// ---- sources ----
children.push(new Paragraph({
  children: [
    mono('Sources — 14 repository dossiers, MASTER_REPOSITORY_MATRIX.md, MASTER_CAPABILITY_MATRIX.md, D_DRIVE_FORENSIC_PROCEDURE.md', { size: 16, color: INK3 }),
    new TextRun({ break: 1 }),
    mono('Location — jax1313-outlook/Dispatch · docs/inventory/ · branch claude/repository-inventory-recovery-r0eiji', { size: 16, color: INK3 }),
    new TextRun({ break: 1 }),
    mono('Mike Zachary is final authority. This report records findings; it decides nothing.', { size: 16, color: INK3 }),
  ],
  spacing: { before: 60, after: 0, line: 280 },
}));

// ================================================================ DOCUMENT ==
const doc = new Document({
  creator: 'Level 1 Transport — Dispatch Recovery',
  title: 'What Has Actually Been Built',
  description: 'Forensic recovery findings across all fourteen repositories.',
  numbering: {
    config: [{
      reference: 'dash',
      levels: [{
        level: 0,
        format: LevelFormat.BULLET,
        text: '–',
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 360, hanging: 220 } },
                 run: { color: INK3 } },
      }],
    }],
  },
  styles: {
    default: {
      document: { run: { font: BODY, size: 21, color: INK }, paragraph: { spacing: { line: 276 } } },
      heading1: {
        run: { font: DISP, size: 34, bold: true, color: INK },
        paragraph: { spacing: { before: 360, after: 60 } },
      },
      heading2: {
        run: { font: DISP, size: 24, bold: true, color: INK },
        paragraph: { spacing: { before: 260, after: 80 } },
      },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840, orientation: PageOrientation.PORTRAIT },
        margin: { top: 1300, right: 1440, bottom: 1300, left: 1440 },
      },
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(process.argv[2] || 'report.docx', buf);
  console.log('written:', process.argv[2] || 'report.docx', buf.length, 'bytes');
});
