import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import { MotionConfig } from "motion/react";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { Spotlight } from "./components/fx";
import "./styles.css";
import "./observatory.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <MotionConfig reducedMotion="user"><AuthProvider><Spotlight /><App /></AuthProvider></MotionConfig>
    </BrowserRouter>
  </React.StrictMode>,
);