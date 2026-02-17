"use client";

import React, { type JSX } from 'react';
import './StarBorder.css';

interface StarBorderProps {
    as?: keyof JSX.IntrinsicElements;
    className?: string;
    color?: string;
    speed?: string;
    thickness?: number;
    children: React.ReactNode;
    [key: string]: unknown;
}

const StarBorder = ({
    as: Component = 'button',
    className = '',
    color = 'rgb(16, 185, 129)', // emerald-500
    speed = '6s',
    children,
    ...rest
}: StarBorderProps) => {
    return React.createElement(
        Component,
        { className: `star-border-container ${className}`, ...rest },
        <div
            className="border-gradient-bottom"
            style={{
                background: `radial-gradient(circle, ${color}, transparent 10%)`,
                animationDuration: speed
            }}
        />,
        <div
            className="border-gradient-top"
            style={{
                background: `radial-gradient(circle, ${color}, transparent 10%)`,
                animationDuration: speed
            }}
        />,
        <div className="inner-content">{children}</div>
    );
};

export default StarBorder;
