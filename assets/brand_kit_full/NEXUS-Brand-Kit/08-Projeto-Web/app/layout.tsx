import type { Metadata } from "next";
import "./globals.css";

export const viewport = { themeColor: "#080b09" };

export const metadata: Metadata = {
  title: "NEXUS PlayTV — Seu entretenimento. Em outra dimensão.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "NEXUS" },
  description: "Esportes, filmes e séries. Conheça a ativação por foto, o Cartão VIP e escolha seu plano NEXUS PlayTV.",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
    apple: "/app-assets/icon-192.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="antialiased">{children}</body>
    </html>
  );
}
