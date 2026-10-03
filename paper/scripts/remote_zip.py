"""List / extract single members of the TotalSegmentator dataset zip on Zenodo with HTTP range requests
(the zip is 37 GB; we only need a few CTs).

usage: python remote_zip.py list  [pattern]
       python remote_zip.py get   <member> <out_file>
"""
import sys, struct, zlib, urllib.request, re, shutil
URL = "https://zenodo.org/api/records/22688904/files/Totalsegmentator_dataset_v300.zip/content"
UA = {"User-Agent": "Mozilla/5.0 (research; mailto:your-address@example.org)"}

def rng(a, b):
    req = urllib.request.Request(URL, headers={**UA, "Range": f"bytes={a}-{b}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        assert r.status == 206, r.status
        return r.read()

def size():
    req = urllib.request.Request(URL, headers={**UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Range"].split("/")[1])

def central_directory():
    n = size()
    tail = rng(n - 65536 - 22, n - 1)
    i = tail.rfind(b"PK\x05\x06")
    cd_size, cd_off = struct.unpack("<II", tail[i + 12:i + 20])
    j = tail.rfind(b"PK\x06\x06")  # zip64 end record
    if j >= 0:
        cd_size, cd_off = struct.unpack("<QQ", tail[j + 40:j + 56])
    cd = rng(cd_off, cd_off + cd_size - 1)
    out, p = [], 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        method, = struct.unpack("<H", cd[p + 10:p + 12])
        csize, usize = struct.unpack("<II", cd[p + 20:p + 28])
        nl, el, cl = struct.unpack("<HHH", cd[p + 28:p + 34])
        off, = struct.unpack("<I", cd[p + 42:p + 46])
        name = cd[p + 46:p + 46 + nl].decode("utf-8", "replace")
        extra = cd[p + 46 + nl:p + 46 + nl + el]
        q = 0
        while q + 4 <= len(extra):  # zip64 extended information
            hid, hl = struct.unpack("<HH", extra[q:q + 4])
            if hid == 1:
                vals, r = [], q + 4
                if usize == 0xFFFFFFFF: usize, = struct.unpack("<Q", extra[r:r + 8]); r += 8
                if csize == 0xFFFFFFFF: csize, = struct.unpack("<Q", extra[r:r + 8]); r += 8
                if off == 0xFFFFFFFF: off, = struct.unpack("<Q", extra[r:r + 8]); r += 8
            q += 4 + hl
        out.append((name, method, csize, usize, off))
        p += 46 + nl + el + cl
    return out

def get(member, out_file):
    ent = [e for e in central_directory() if e[0] == member]
    if not ent: sys.exit("not found: " + member)
    name, method, csize, usize, off = ent[0]
    h = rng(off, off + 29)
    nl, el = struct.unpack("<HH", h[26:30])
    data = rng(off + 30 + nl + el, off + 30 + nl + el + csize - 1)
    if method == 8: data = zlib.decompress(data, -15)
    elif method != 0: sys.exit(f"unsupported method {method}")
    assert len(data) == usize
    open(out_file, "wb").write(data)
    print(f"{member}: {csize/1e6:.1f} MB -> {out_file}")

if __name__ == "__main__":
    if sys.argv[1] == "list":
        pat = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None
        for n, m, c, u, o in central_directory():
            if pat is None or pat.search(n): print(f"{c:>12} {n}")
    else:
        get(sys.argv[2], sys.argv[3])
