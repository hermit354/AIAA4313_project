import type { Metadata } from 'next';
import './shell.css';
export const metadata: Metadata = { title: 'HireLens — Hiring Agent Demo', description: 'Local AI-assisted resume review demonstration' };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
