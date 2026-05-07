import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";

import "./styles/tokens.css";
import "./styles/globals.css";
import "./styles/primitives.css";
import "./styles/layout.css";
import "./styles/source.css";
import "./styles/sync.css";
import "./styles/log.css";
import "./styles/wizard.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
