import type { CapacitorConfig } from '@capacitor/cli'

/**
 * Capacitor configuration.
 *
 * The Android app loads the bundled web build (frontend/dist) from the device,
 * so it never depends on a development server. All API traffic goes to the
 * backend URL chosen at runtime in the app settings screen, or to the build
 * time default from VITE_DEFAULT_API_BASE_URL. No server secret is bundled.
 */
const config: CapacitorConfig = {
  appId: 'ai.biolearn.app',
  appName: 'BioLearn AI',
  webDir: 'dist',
  android: {
    // Localhost is the packaged asset origin, never a backend address.
    allowMixedContent: false,
    backgroundColor: '#071a1a',
  },
  server: {
    androidScheme: 'https',
  },
}

export default config
