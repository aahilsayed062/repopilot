"use client";

import { motion } from 'framer-motion';
import { ArrowRight, CheckCircle2, Cpu, Play } from 'lucide-react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import Shuffle from '../ui/Shuffle';

// Dynamically import Silk to avoid SSR issues with Three.js
const Silk = dynamic(() => import('../ui/Silk'), { ssr: false });

const LandingHero = () => {
    return (
        <div className="relative min-h-screen text-white overflow-hidden selection:bg-emerald-500/30">
            {/* Silk Background - Fixed Full Screen */}
            <div className="fixed inset-0 z-0">
                <Silk
                    color="#7B7481"
                    speed={3}
                    scale={1.2}
                    noiseIntensity={1.2}
                    rotation={0}
                />
            </div>

            <main className="relative z-10 max-w-7xl mx-auto px-8 pt-32 pb-20 flex flex-col lg:flex-row items-center justify-center gap-16 min-h-screen">
                {/* Left Content */}
                <div className="flex-1 space-y-8">
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
                        className="text-5xl md:text-7xl font-bold tracking-tight leading-[1.05] space-y-2"
                    >
                        <div className="flex flex-wrap gap-x-4">
                            <Shuffle
                                text="Repository"
                                shuffleTimes={3}
                                shuffleDirection="right"
                                scrambleCharset="!@#$%^&*()"
                                duration={0.8}
                                className="text-white"
                            />
                            <Shuffle
                                text="Grounded"
                                shuffleTimes={3}
                                shuffleDirection="right"
                                scrambleCharset="!@#$%^&*()"
                                duration={0.9}
                                className="text-emerald-400"
                            />
                        </div>
                        <div>
                            <Shuffle
                                text="Intelligence."
                                shuffleTimes={3}
                                shuffleDirection="right"
                                scrambleCharset="!@#$%^&*()"
                                duration={1.1}
                                className="text-white"
                            />
                        </div>
                    </motion.div>

                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                        className="text-lg text-gray-400 max-w-xl leading-relaxed"
                    >
                        Stop guessing. Our RAG-powered engine analyzes your entire repository, understands code relationships, and generates grounded answers with citations in milliseconds. Transparency first.
                    </motion.p>

                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="flex flex-col sm:flex-row gap-4 pt-4"
                    >
                        <Link
                            href="/dashboard"
                            className="px-8 py-3 rounded-full bg-emerald-500 hover:bg-emerald-600 text-white font-semibold transition-all shadow-lg shadow-emerald-900/30 flex items-center justify-center gap-2 group"
                        >
                            Get Started Now
                            <ArrowRight className="group-hover:translate-x-1 transition-transform" />
                        </Link>
                    </motion.div>

                    <div className="flex items-center gap-6 pt-4 text-sm text-gray-500">
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
                    className="flex-1 w-full relative"
                >
                    <div className="relative rounded-2xl p-[1px] bg-gradient-to-br from-emerald-500/40 via-teal-500/10 to-transparent">
                        <div className="bg-[#0B0F19] rounded-2xl overflow-hidden shadow-2xl shadow-emerald-900/10 aspect-video relative group cursor-pointer">
                            {/* Fake UI Header */}
                            <div className="h-10 border-b border-white/5 bg-black/20 flex items-center px-4 gap-2">
                                <div className="w-3 h-3 rounded-full bg-red-500/30" />
                                <div className="w-3 h-3 rounded-full bg-yellow-500/30" />
                                <div className="w-3 h-3 rounded-full bg-green-500/30" />
                            </div>
                            {/* Content Area - Video Player */}
                            <div className="absolute inset-0 bg-[#0B0F19]">
                                <video
                                    className="w-full h-full object-cover"
                                    autoPlay
                                    loop
                                    muted
                                    playsInline
                                >
                                    <source src="/demo.mp4" type="video/mp4" />
                                </video>

                                {/* Fallback overlay if no video */}
                                <div className="absolute inset-0 flex items-center justify-center bg-[#0B0F19]/80">
                                    <div className="text-center space-y-4">
                                        <div className="w-16 h-16 rounded-full bg-white/10 flex items-center justify-center mx-auto group-hover:scale-110 transition-transform">
                                            <Play className="fill-white text-white ml-1" size={24} />
                                        </div>
                                        <p className="text-gray-500 text-sm">RepoPilot Demo</p>
                                    </div>
                                </div>

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
