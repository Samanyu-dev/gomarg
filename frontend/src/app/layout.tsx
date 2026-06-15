import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { Toaster } from "react-hot-toast";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "GoMarg | Sales Automation",
  description: "AI-powered sales automation and lead generation platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <AuthProvider>
          {children}
          <Toaster 
            position="bottom-right" 
            toastOptions={{
              style: {
                background: '#18181b',
                color: '#fafafa',
                border: '1px solid rgba(255,255,255,0.1)'
              }
            }}
          />
        </AuthProvider>
      </body>
    </html>
  );
}
