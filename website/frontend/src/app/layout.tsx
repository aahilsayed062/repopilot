import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "RepoPilot AI - Repository-Grounded Coding Assistant",
  description: "Ask questions about any codebase and get answers grounded in the actual code with citations.",
  keywords: ["AI", "coding assistant", "code analysis", "repository", "developer tools"],
  authors: [{ name: "RepoPilot" }],
  openGraph: {
    title: "RepoPilot AI",
    description: "Repository-grounded AI coding assistant with citations",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable}`}>
        {children}
      </body>
    </html>
  );
}
