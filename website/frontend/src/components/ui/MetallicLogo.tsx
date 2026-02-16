"use client";

import { useEffect, useState } from 'react';
import MetallicPaint from './MetallicPaint';

function generateLogoImageData(text: string) {
    if (typeof document === 'undefined') return null;
    const canvas = document.createElement('canvas');
    const size = 500;
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');

    if (!ctx) return null;

    // Fill with white background
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, size, size);

    // Draw text in black
    ctx.fillStyle = 'black';
    ctx.font = 'bold 280px Inter, Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, size / 2, size / 2);

    return ctx.getImageData(0, 0, size, size);
}

interface MetallicLogoProps {
    text?: string;
    size?: number;
}

const MetallicLogo = ({ text = 'RP', size = 48 }: MetallicLogoProps) => {
    const [imageData, setImageData] = useState<ImageData | null>(null);

    useEffect(() => {
        const data = generateLogoImageData(text);
        setImageData(data);
    }, [text]);

    if (!imageData) {
        // Fallback while loading
        return (
            <div
                className="relative inline-flex items-center justify-center bg-gradient-to-br from-gray-800 via-gray-900 to-black border border-white/10 rounded-xl"
                style={{ width: size, height: size }}
            >
                <span className="font-bold text-white" style={{ fontSize: size * 0.45 }}>{text}</span>
            </div>
        );
    }

    return (
        <div
            className="relative inline-block rounded-xl overflow-hidden"
            style={{ width: size, height: size }}
        >
            <MetallicPaint
                imageData={imageData}
                params={{
                    patternScale: 2,
                    refraction: 0.015,
                    edge: 1,
                    patternBlur: 0.005,
                    liquid: 0.07,
                    speed: 0.3
                }}
            />
        </div>
    );
};

export default MetallicLogo;
