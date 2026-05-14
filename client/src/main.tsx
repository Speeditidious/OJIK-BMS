import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import { initializeClientI18n } from "./lib/i18n/client";
import { DEFAULT_LANGUAGE } from "./lib/i18n/languages";

import "./styles/tokens.css";
import "./styles/globals.css";
import "./styles/primitives.css";
import "./styles/layout.css";
import "./styles/source.css";
import "./styles/sync.css";
import "./styles/log.css";
import "./styles/wizard.css";

initializeClientI18n(DEFAULT_LANGUAGE);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
