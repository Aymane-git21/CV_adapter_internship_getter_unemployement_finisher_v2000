import React, { useEffect, useRef } from 'react';
import anime from 'animejs/lib/anime.es.js';

const Hero = ({ onStart }) => {
    const titleRef = useRef(null);
    const subtitleRef = useRef(null);
    const btnRef = useRef(null);

    useEffect(() => {
        // Title Animation
        anime({
            targets: titleRef.current,
            translateY: [20, 0],
            opacity: [0, 1],
            easing: 'easeOutExpo',
            duration: 1200,
            delay: 300
        });

        // Subtitle Animation
        anime({
            targets: subtitleRef.current,
            translateY: [20, 0],
            opacity: [0, 1],
            easing: 'easeOutExpo',
            duration: 1200,
            delay: 500
        });

        // Button Animation
        anime({
            targets: btnRef.current,
            translateY: [20, 0],
            opacity: [0, 1],
            easing: 'easeOutExpo',
            duration: 1200,
            delay: 700
        });
    }, []);

    return (
        <section style={{
            height: 'calc(100vh - 70px)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            textAlign: 'center',
            padding: '2rem',
            position: 'relative',
            overflow: 'hidden'
        }}>
            {/* Background Decor (Circles) */}
            <div style={{
                position: 'absolute',
                top: '20%',
                left: '10%',
                width: '300px',
                height: '300px',
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(59,130,246,0.1) 0%, rgba(0,0,0,0) 70%)',
                zIndex: -1
            }}></div>
            <div style={{
                position: 'absolute',
                bottom: '10%',
                right: '10%',
                width: '400px',
                height: '400px',
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(59,130,246,0.05) 0%, rgba(0,0,0,0) 70%)',
                zIndex: -1
            }}></div>

            <h1 ref={titleRef} style={{
                fontSize: '4rem',
                fontWeight: '700',
                marginBottom: '1rem',
                opacity: 0
            }}>
                Optimize Your CV for <span style={{ color: 'var(--accent-color)' }}>Success</span>
            </h1>

            <p ref={subtitleRef} style={{
                fontSize: '1.25rem',
                color: 'var(--text-secondary)',
                maxWidth: '600px',
                marginBottom: '2rem',
                opacity: 0
            }}>
                Beat the ATS with AI-powered tailoring. Upload your master CV, paste a job description, and get a perfectly targeted application in seconds.
            </p>

            <button
                ref={btnRef}
                onClick={onStart}
                style={{
                    background: 'var(--accent-color)',
                    color: 'white',
                    padding: '16px 32px',
                    borderRadius: '50px',
                    fontSize: '1.1rem',
                    fontWeight: '600',
                    boxShadow: '0 4px 20px rgba(59, 130, 246, 0.4)',
                    transition: 'transform 0.2s',
                    opacity: 0
                }}
                onMouseEnter={(e) => e.target.style.transform = 'scale(1.05)'}
                onMouseLeave={(e) => e.target.style.transform = 'scale(1)'}
            >
                Start Optimization
            </button>
        </section>
    );
};

export default Hero;
