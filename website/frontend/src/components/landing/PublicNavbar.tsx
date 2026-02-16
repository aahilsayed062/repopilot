"use client";

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import MetallicLogo from '../ui/MetallicLogo';

const PublicNavbar = () => {
    return (
        <nav className="fixed top-0 left-0 right-0 z-50 hidden md:flex items-center justify-center px-8 py-6">
            <div className="flex items-center justify-between w-full max-w-3xl px-6 py-3 rounded-full bg-black/40 backdrop-blur-xl border border-white/10 shadow-2xl shadow-black/20">
                {/* Logo */}
                <Link href="/" className="flex items-center gap-2 group">
                    <MetallicLogo text="RP" size={32} />
                    <span className="text-lg font-bold tracking-tight text-white group-hover:text-emerald-400 transition-colors">RepoPilot</span>
                </Link>

                {/* Nav Links */}
                <div className="hidden md:flex items-center gap-8">
                    <NavLink href="#features">Features</NavLink>
                    <NavLink href="#framework">Framework</NavLink>
                    <NavLink href="#about">About</NavLink>
                </div>

                {/* CTA Button */}
                <Link
                    href="/dashboard"
                    className="px-5 py-2 rounded-full bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-semibold transition-all hover:scale-105 active:scale-95 flex items-center gap-1"
                >
                    Log In <ArrowRight size={14} />
                </Link>
            </div>
        </nav>
    );
};

interface NavLinkProps {
    href: string;
    children: React.ReactNode;
}

const NavLink = ({ href, children }: NavLinkProps) => (
    <a
        href={href}
        className="relative text-sm font-medium transition-colors duration-300 group text-gray-300 hover:text-white"
    >
        {children}
        <span className="absolute left-0 bottom-[-4px] w-0 h-[2px] bg-white transition-all duration-300 group-hover:w-full" />
    </a>
);

export default PublicNavbar;
