# Vendored vis-network

- Package: `vis-network` 10.1.2, standalone browser build.
- Source: https://registry.npmjs.org/vis-network/-/vis-network-10.1.2.tgz
- JavaScript: `vis-network.min.js`
- SHA-256: `FC674CFA6CCEB27A3B40FF4EA75C204A2D8570FB39B9A627127CF7039E141AD4`
- License: MIT, included as `LICENSE-MIT`.
- License SHA-256: `1F65085E54C036645082257618DB2C7B787E68C3B02485E214ECD09E0834EE8F`

The application loads this local standalone bundle and makes no third-party browser requests. The bundle sizes and positions its canvas through inline style declarations, so the application's CSP allows inline styles while keeping scripts, connections, fonts, and other resources same-origin. The bundle does not receive server strings as markup; graph labels are passed as text to vis-network.
