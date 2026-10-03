import nibabel as nib, numpy as np
a='ref/case1_cpu/'; b='ref/case1_gpu/'
for f in ['298_in.nii.gz','291_in.nii.gz','298_seg.nii.gz','291_seg.nii.gz','crop_mask.nii.gz','final_liver.nii.gz']:
    x=np.asarray(nib.load(a+f).dataobj); y=np.asarray(nib.load(b+f).dataobj)
    print(f, x.shape, x.dtype, 'diff voxels', int((x!=y).sum()), 'of', x.size)
x=np.asarray(nib.load(a+'final_liver.nii.gz').dataobj); y=np.asarray(nib.load(b+'final_liver.nii.gz').dataobj)
print('liver voxels cpu', int((x==5).sum()), 'gpu', int((y==5).sum()), 'dice', 2*((x==5)&(y==5)).sum()/((x==5).sum()+(y==5).sum()))
for f in ['298_logits.npy','291_logits.npy','291_pre.npy']:
    x=np.load(a+f).astype(np.float32); y=np.load(b+f).astype(np.float32); print(f, x.shape, np.load(a+f).dtype, 'max abs diff', np.abs(x-y).max())
