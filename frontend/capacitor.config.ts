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
    // The bundle is served over https://localhost, so an HTTP LAN backend is
    // mixed content. It is required for on-premise testing (no TLS on a home
    // LAN); a production deployment must use HTTPS, where this flag has no
    // effect because both origins are secure.
    allowMixedContent: true,
    backgroundColor: '#071a1a',
  },
  server: {
    androidScheme: 'https',
  },
}

export default config
