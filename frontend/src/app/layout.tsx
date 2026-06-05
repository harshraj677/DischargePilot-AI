import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "DischargePilot AI",
    template: "%s | DischargePilot AI",
  },
  description: "Clinical discharge summary generation powered by AI",
  keywords: ["discharge summary", "clinical AI", "healthcare", "EHR"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-slate-50 text-slate-900 antialiased">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="ml-60 flex-1 min-w-0">
            <div className="min-h-screen px-6 py-6">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
