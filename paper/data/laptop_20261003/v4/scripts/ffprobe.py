# Probe Firefox WebGPU through geckodriver (WebDriver HTTP API): about:support text (graphics/WebGPU part) and
# navigator.gpu adapter info on http://localhost. usage: ffprobe.py <out prefix> <webgpu pref: default|true>
import json, sys, time, subprocess, urllib.request, urllib.error, os
out, pref = sys.argv[1], sys.argv[2]
def req(m, p, body=None):
    r = urllib.request.Request('http://127.0.0.1:4455' + p, method=m, data=json.dumps(body).encode() if body is not None else None,
                               headers={'Content-Type': 'application/json'})
    try: return json.load(urllib.request.urlopen(r, timeout=120))
    except urllib.error.HTTPError as e: raise SystemExit(f'{m} {p}: {e.code} {e.read().decode()[:600]}')
gd = subprocess.Popen(['/snap/bin/geckodriver', '--port', '4455', '--allow-system-access'], stdout=open(out + '_geckodriver.log', 'w'), stderr=subprocess.STDOUT, start_new_session=True)
time.sleep(2)
prefs = {'dom.webgpu.enabled': True} if pref == 'true' else ({'dom.webgpu.enabled': True, 'gfx.webgpu.ignore-blocklist': True} if pref == 'true_ignoreblocklist' else {})
s = req('POST', '/session', {'capabilities': {'alwaysMatch': {'moz:firefoxOptions': {'prefs': prefs}}}})['value']
sid = s['sessionId']; caps = s['capabilities']
res = {'browserVersion': caps.get('browserVersion'), 'pref': pref}
try:
    req('POST', f'/session/{sid}/url', {'url': 'http://localhost:8099/'}); time.sleep(2)
    js = '''const done = arguments[arguments.length-1];
      (async () => { const r = {hasGpu: !!navigator.gpu, secure: isSecureContext};
        try { if (navigator.gpu) { const a = await navigator.gpu.requestAdapter({powerPreference: 'high-performance'});
          r.adapter = a ? {info: a.info ? {vendor: a.info.vendor, architecture: a.info.architecture, device: a.info.device, description: a.info.description} : null,
                           maxBufferSize: a.limits.maxBufferSize, maxStorageBufferBindingSize: a.limits.maxStorageBufferBindingSize} : null; } }
        catch (e) { r.error = String(e); } done(r); })();'''
    res['probe'] = req('POST', f'/session/{sid}/execute/async', {'script': js, 'args': []})['value']
finally:
    try: req('DELETE', f'/session/{sid}')
    except Exception: pass
    import signal
    os.killpg(gd.pid, signal.SIGTERM); time.sleep(2)
json.dump(res, open(out + '_probe.json', 'w'), indent=1); print(json.dumps(res))
