import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import "./session-styles.css";
import "./styles.css";
import "./playful.css";
import "./pocket.css";
import "./back-link.css";

// A data router so the live screen can block navigation while a lecture is being recorded (useBlocker).
const router = createBrowserRouter([{ path: "*", element: <App /> }]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
