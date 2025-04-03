// src/app/layout.tsx
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Sidebar from '@/components/sidebar';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Prequel - GitHub Repository and Workflow Analytics',
  description: 'Monitor your organization repositories and workflows with Prequel',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="flex h-screen bg-gray-900">
          <Sidebar />
          <main className="flex-1 overflow-auto p-4">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}