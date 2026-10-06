import numpy as np, glob, os, sys
L=sys.argv[1]; D=sys.argv[2]
for f in sorted(glob.glob(os.path.join(L,'*.npy'))):
    k=os.path.basename(f); g=os.path.join(D,k)
    if not os.path.exists(g): print(k,'NO DESKTOP REF'); continue
    a=np.load(f); b=np.load(g)
    if a.shape!=b.shape: print(k,'SHAPE',a.shape,b.shape); continue
    d=int((a!=b).sum())
    cnt=lambda x:{int(l):int((x==l).sum()) for l in np.unique(x) if l}
    ca,cb=cnt(a),cnt(b)
    print(f"{k:34s} diff={d:6d}  lap={ca}  desk={cb}" if d else f"{k:34s} diff=0  {ca}")
