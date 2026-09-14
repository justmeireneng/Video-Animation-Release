import {Config} from '@remotion/cli/config';

// Serve project media in-place; fonts are bundled through TypeScript imports.
Config.setPublicDir('../projects');
Config.setOverwriteOutput(true);
Config.setVideoImageFormat('jpeg');
