"use client";

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, CheckCircle2, Cpu } from 'lucide-react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { Playfair_Display } from 'next/font/google';

// Dynamically import Silk to avoid SSR issues with Three.js
const Silk = dynamic(() => import('../ui/Silk'), { ssr: false });
const playfair = Playfair_Display({
    subsets: ['latin'],
    weight: ['500', '600', '700'],
    display: 'swap',
});

const LandingHero = () => {
    const [mounted, setMounted] = useState(false);
    const [videoError, setVideoError] = useState(false);
    const [videoAspect, setVideoAspect] = useState<number>(16 / 9);
    useEffect(() => { setMounted(true); }, []);

    return (
        <div className="relative h-[100svh] text-white overflow-hidden selection:bg-emerald-500/30">
            {/* Silk Background - Fixed Full Screen */}
            <div className="fixed inset-0 z-0" suppressHydrationWarning>
                {mounted && (
                    <Silk
                        color="#7B7481"
                        speed={3}
                        scale={1.2}
                        noiseIntensity={1.2}
                        rotation={0}
                    />
                )}
            </div>

            <main className="relative z-10 max-w-7xl mx-auto px-8 pt-20 lg:pt-24 pb-5 lg:pb-6 flex flex-col lg:flex-row items-center justify-center gap-8 lg:gap-10 h-full">
                {/* Left Content */}
                <div className="flex-1 space-y-4 lg:space-y-5">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="inline-block px-4 py-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-xs font-medium tracking-wide"
                    >
                        RepoPilot AI — Code Intelligence
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                        className={`${playfair.className} text-4xl sm:text-5xl lg:text-6xl xl:text-[68px] font-semibold tracking-tight leading-[1.04] space-y-1.5`}
                    >
                        <div className="flex flex-wrap gap-x-4">
                            <span className="text-white">Repository</span>
                            <span className="text-emerald-400">Grounded</span>
                        </div>
                        <div>
                            <span className="text-white">Intelligence.</span>
                        </div>
                    </motion.div>

                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="text-base lg:text-[1.05rem] text-gray-400 max-w-xl leading-relaxed"
                    >
                        Stop guessing. Our RAG-powered engine analyzes your entire repository, understands code relationships, and generates grounded answers with citations in milliseconds. Transparency first.
                    </motion.p>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="flex flex-col sm:flex-row gap-4 pt-1"
                    >
                        <Link
                            href="/analyze"
                            className="px-8 py-3 rounded-full bg-emerald-500 hover:bg-emerald-600 text-white font-semibold transition-all shadow-lg shadow-emerald-900/30 flex items-center justify-center gap-2 group"
                        >
                            Get Started Now
                            <ArrowRight className="group-hover:translate-x-1 transition-transform" />
                        </Link>
                    </motion.div>

                    <div className="flex items-center gap-6 pt-0.5 text-sm text-gray-500">
                        <div className="flex items-center gap-2">
                            <CheckCircle2 size={16} className="text-emerald-500" />
                            <span>Open Source</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Cpu size={16} className="text-emerald-500" />
                            <span>AI + RAG Powered</span>
                        </div>
                    </div>
                </div>

                {/* Right Content - App Preview */}
                <motion.div
                    initial={{ opacity: 0, x: 50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.4 }}
                    className="flex-1 w-full max-w-3xl relative lg:-translate-y-2"
                >
                    <div className="relative rounded-2xl p-[1px] bg-gradient-to-br from-emerald-500/40 via-teal-500/10 to-transparent">
                        <div
                            className="bg-[#0B0F19] rounded-2xl overflow-hidden shadow-2xl shadow-emerald-900/10 relative group cursor-pointer"
                            style={{ aspectRatio: `${videoAspect}` }}
                        >
                            {/* Fake UI Header */}
                            <div className="h-10 border-b border-white/5 bg-black/20 flex items-center px-4 gap-2">
                                <div className="w-3 h-3 rounded-full bg-red-500/30" />
                                <div className="w-3 h-3 rounded-full bg-yellow-500/30" />
                                <div className="w-3 h-3 rounded-full bg-green-500/30" />
                            </div>
                            {/* Content Area - Video Player */}
                            <div className="absolute inset-0 bg-[#0B0F19]">
                                <video
                                    className="w-full h-full object-contain object-center"
                                    autoPlay
                                    loop
                                    muted
                                    playsInline
                                    preload="auto"
                                    onError={() => setVideoError(true)}
                                    onLoadedMetadata={(e) => {
                                        const v = e.currentTarget;
                                        if (v.videoWidth > 0 && v.videoHeight > 0) {
                                            setVideoAspect(v.videoWidth / v.videoHeight);
                                        }
                                    }}
                                >
                                    <source src="/video/demo.mp4" type="video/mp4" />
                                    <source src="/demo.mp4" type="video/mp4" />
                                </video>

                                {videoError && (
                                    <div className="absolute inset-0 flex items-center justify-center bg-[#0B0F19]/80 text-gray-400 text-sm">
                                        Video unavailable
                                    </div>
                                )}

                                {/* Overlay Gradient */}
                                <div className="absolute inset-0 bg-gradient-to-t from-[#0B0F19] via-transparent to-transparent opacity-60 pointer-events-none" />
                            </div>

                        </div>
                    </div>
                </motion.div>
            </main>
        </div>
    );
};

export default LandingHero;
