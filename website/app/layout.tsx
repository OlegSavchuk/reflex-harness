import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });

export const metadata: Metadata = {
  title: "Reflex — Stop Coding Agents From Looping",
  description: "A harness around a coding agent that notices when the agent is repeating a failed fix, and changes the agent's working context using measured evidence stored in MongoDB Atlas.",
  openGraph: {
    title: "Reflex — Stop Coding Agents From Looping",
    description: "Coding agents don't just fail — they fail in loops. Reflex notices. And changes the context before the next attempt.",
    type: "website",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={geist.variable}>
      <body className={geist.className}>{children}</body>
    </html>
  );
}
