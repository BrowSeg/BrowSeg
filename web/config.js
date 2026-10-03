// Runtime configuration (read by worker.js). Paths are relative to web/ or absolute URLs.
// The published BrowSeg build points weightsBase at the GitHub release that holds the .tsw files.
self.TSC_CONFIG = { weightsBase: '../weights/', weightsBaseFp16: '../weights_fp16/', lang: 'en' };  // lang: 'en' | 'en' (?lang= overrides)
