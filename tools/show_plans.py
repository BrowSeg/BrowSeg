import json, os
R = os.path.expanduser(r'~/.totalsegmentator/nnunet/results')
for p in ['Dataset291_TotalSegmentator_part1_organs_1559subj/nnUNetTrainerNoMirroring__nnUNetPlans__3d_fullres',
          'Dataset298_TotalSegmentator_total_6mm_1559subj/nnUNetTrainer_4000epochs_NoMirroring__nnUNetPlans__3d_fullres']:
    p = os.path.join(R, p)
    pl = json.load(open(p + '/plans.json'))
    c = pl['configurations']['3d_fullres']
    print(pl['dataset_name'], pl.get('image_reader_writer'), pl['transpose_forward'], pl['transpose_backward'])
    print(json.dumps(c, indent=1))
    print(pl['foreground_intensity_properties_per_channel'])
    d = json.load(open(p + '/dataset.json')); print(d)
