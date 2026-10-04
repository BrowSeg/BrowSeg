#!/bin/bash
# Firefox on the T1200: unsplit, then gpuchunk=4 (ircad01, 3 tasks, reps=3).
T=~/Documents/MyGithubProject2/BrowSeg_tools
$T/run_ff_v4.sh lap_firefox_nv_chunk0 'cases=ircad01&tasks=total:liver;liver_segments:-;liver_vessels:-&reps=3' 60
$T/run_ff_v4.sh lap_firefox_nv_chunk4 'cases=ircad01&tasks=total:liver;liver_segments:-;liver_vessels:-&reps=3&gpuchunk=4' 60
