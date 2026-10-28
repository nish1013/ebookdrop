import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { AccountPage } from "./identity/AccountPage";
import { SignInPage } from "./identity/SignInPage";
import { SignUpPage } from "./identity/SignUpPage";
import { LibraryPage } from "./library/LibraryPage";
import { ReaderPage } from "./reader/ReaderPage";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/sign-up" element={<SignUpPage />} />
        <Route path="/sign-in" element={<SignInPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/books/:bookId" element={<ReaderPage />} />
        <Route path="*" element={<Navigate to="/library" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
