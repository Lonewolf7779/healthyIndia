import type { Metadata } from "next";
import React from "react";
import "./globals.css";
import { Header } from "../components/Header";
import { Footer } from "../components/Footer";

export const metadata: Metadata = {
  title: "healthyIndia | Understand Packaged Food Labels",
  description:
    "Helping Indian consumers understand nutrition labels and ingredients on packaged food products transparently.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Header />
        <main className="main-content" id="main-content">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
