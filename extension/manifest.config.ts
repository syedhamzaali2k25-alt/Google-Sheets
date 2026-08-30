import { defineManifest } from "@crxjs/vite-plugin";
import pkg from "./package.json" with { type: "json" };

export default defineManifest({
  manifest_version: 3,
  name: "Google Sheet Insights",
  description: "Surfaces insights for Google Sheets directly in the browser.",
  version: pkg.version,
  icons: {
    16: "public/icons/icon16.png",
    48: "public/icons/icon48.png",
    128: "public/icons/icon128.png",
  },
  action: {
    default_popup: "src/popup/index.html",
    default_icon: {
      16: "public/icons/icon16.png",
      48: "public/icons/icon48.png",
      128: "public/icons/icon128.png",
    },
  },
  content_scripts: [
    {
      matches: ["https://docs.google.com/spreadsheets/*", "https://sheets.google.com/*"],
      js: ["src/content/content-script.ts"],
      run_at: "document_idle",
    },
  ],
  permissions: ["storage", "activeTab", "identity"],
  host_permissions: ["https://docs.google.com/*", "https://sheets.google.com/*"],
  oauth2: {
    // Replace with a "Chrome Extension" OAuth client id from Google Cloud
    // Console (APIs & Services > Credentials), registered against this
    // extension's id. See README.md for setup steps.
    client_id: "319140573974-mkcdhjnb5pq0th975sbrqc58523a91mn.apps.googleusercontent.com",
    scopes: [
      // Full read-write, not spreadsheets.readonly: the "Highlight
      // duplicates in Sheet" feature writes cell background formatting
      // back to the user's sheet. This scope is a superset of
      // spreadsheets.readonly for the Sheets resource, so readonly is
      // intentionally removed rather than kept alongside it.
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/drive.metadata.readonly",
      "https://www.googleapis.com/auth/drive.activity.readonly",
      // Lets the backend identify who a health report belongs to (for the
      // persistence layer's users/reports tables) — no other profile data.
      "https://www.googleapis.com/auth/userinfo.email",
    ],
  },
});
