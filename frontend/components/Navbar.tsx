"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavbarProps {
  isConnected: boolean;
}

const navLinks = [
  { href: "/trader-desk", label: "Trader Desk" },
  { href: "/", label: "Dashboard" },
  { href: "/console", label: "Console" },
  { href: "/admin", label: "Admin" },
];

export default function Navbar({ isConnected }: NavbarProps) {
  const pathname = usePathname();

  return (
    <nav className="border-b border-navy-700 bg-navy-900/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2">
            <span className="text-lg font-bold tracking-tight">
              Trade<span className="text-accent-blue">Pulse</span>
            </span>
          </Link>

          {/* Nav Links */}
          <div className="flex items-center gap-1">
            {navLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-navy-700 text-white"
                      : "text-gray-400 hover:text-white hover:bg-navy-800"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>

          {/* Connection Status */}
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected ? "bg-accent-green" : "bg-accent-red"
              }`}
            />
            {isConnected ? "Connected" : "Disconnected"}
          </div>
        </div>
      </div>
    </nav>
  );
}
