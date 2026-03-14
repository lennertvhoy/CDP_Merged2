import type { Metadata } from "next";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "CDP_Merged Private Preview",
  description:
    "Private preview access for the CDP_Merged chat experience.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${ibmPlexMono.variable} dark`}>
      <body
        className="bg-zinc-950 font-sans text-zinc-100 antialiased selection:bg-zinc-800"
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
