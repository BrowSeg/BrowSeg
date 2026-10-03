// Runs web/bench.html configurations one after another in real browser windows (Chrome / Firefox) and waits for
// each to finish (status.txt = DONE or ERROR). The server must already run:
//   node serve.mjs 8090 --bench <cases> --out <out>   (another port: BENCH_PORT=<port> for this script)
// usage: node bench_run.mjs <out dir> <plan.json>
//   plan.json: [{ "browser": "chrome"|"edge"|"firefox", "tag": "...", "query": "tasks=...&reps=3&cases=...", "timeoutMin": 120 }, ...]
import { spawn, execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import os from 'os';

const [outDir, planFile] = process.argv.slice(2);
const plan = JSON.parse(fs.readFileSync(planFile, 'utf8'));
const EXE = { chrome: 'C:/Program Files/Google/Chrome/Application/chrome.exe', firefox: 'C:/Program Files/Mozilla Firefox/firefox.exe',
              edge: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' };
const profRoot = path.join(os.tmpdir(), 'browseg_bench_profiles');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function firefoxProfile() {
  const p = path.join(profRoot, 'firefox');
  fs.mkdirSync(p, { recursive: true });
  fs.writeFileSync(path.join(p, 'user.js'), [
    'browser.aboutwelcome.enabled", false', 'trailhead.firstrun.didSeeAboutWelcome", true',
    'datareporting.policy.dataSubmissionPolicyBypassNotification", true', 'browser.startup.homepage_override.mstone", "ignore"',
    'browser.shell.checkDefaultBrowser", false', 'toolkit.telemetry.reportingpolicy.firstRun", false',
    'browser.sessionstore.resume_from_crash", false'].map((l) => `user_pref("${l});`).join('\n'));
  return p;
}

// closes only the browser processes started with the benchmark profiles (never the user's own windows)
function closeBenchBrowsers() {
  const ps = "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*browseg_bench_profiles*' } | " +
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }";
  try { execSync(`powershell -NoProfile -Command "${ps}"`, { stdio: 'ignore' }); } catch (e) { /* none */ }
}

for (const run of plan) {
  const url = `http://localhost:${process.env.BENCH_PORT || 8090}/web/bench.html?tag=${encodeURIComponent(run.tag)}&${run.query}`;
  const statusFile = path.join(outDir, run.tag, 'status.txt');
  if (fs.existsSync(statusFile) && /DONE/.test(fs.readFileSync(statusFile, 'utf8'))) { console.log(`skip ${run.tag} (done)`); continue; }
  const args = run.browser !== 'firefox'  // chrome / edge (both Chromium)
    ? [`--user-data-dir=${path.join(profRoot, run.browser)}`, '--no-first-run', '--no-default-browser-check',
       '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
       '--new-window', url]
    : ['-no-remote', '-profile', firefoxProfile(), url];
  console.log(`${new Date().toISOString()} start ${run.tag} (${run.browser})`);
  const p = spawn(EXE[run.browser], args, { detached: true, stdio: 'ignore' });
  p.unref();
  const t0 = Date.now();
  let last = '';
  for (;;) {
    await sleep(5000);
    const st = fs.existsSync(statusFile) ? fs.readFileSync(statusFile, 'utf8') : '';
    if (st !== last) { last = st; }
    if (/DONE|ERROR/.test(st)) { console.log(`${new Date().toISOString()} ${run.tag}: ${st}`); break; }
    if (Date.now() - t0 > (run.timeoutMin || 120) * 60000) { console.log(`${run.tag}: TIMEOUT (${st})`); break; }
  }
  closeBenchBrowsers();
  await sleep(3000);
}
console.log('ALL DONE');
