import React from 'react';

const GDPRBanner = ({ onAccept }) => {
    return (
        <div style={{
            position: 'fixed',
            bottom: '20px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '90%',
            maxWidth: '600px',
            background: 'rgba(28, 28, 28, 0.95)',
            backdropFilter: 'blur(10px)',
            WebkitBackdropFilter: 'blur(10px)',
            border: '1px solid var(--border-color)',
            borderRadius: '16px',
            padding: '1.5rem',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
            boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
            animation: 'slideUp 0.5s ease-out forwards'
        }}>
            <div>
                <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem', fontWeight: 'bold' }}>We value your privacy</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                    We use cookies and local storage to enhance your experience and remember your preferences.
                    By continuing to visit this site you agree to our use of cookies and our Terms of Service.
                </p>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
                <button
                    onClick={onAccept}
                    style={{
                        background: 'var(--accent-color)',
                        color: 'white',
                        padding: '0.6rem 1.5rem',
                        borderRadius: '8px',
                        fontWeight: '600',
                        fontSize: '0.9rem',
                        transition: 'all 0.3s ease'
                    }}
                    onMouseOver={(e) => e.target.style.background = 'var(--accent-hover)'}
                    onMouseOut={(e) => e.target.style.background = 'var(--accent-color)'}
                >
                    Accept & Continue
                </button>
            </div>

            <style>{`
                @keyframes slideUp {
                    from { transform: translate(-50%, 100px); opacity: 0; }
                    to { transform: translate(-50%, 0); opacity: 1; }
                }
            `}</style>
        </div>
    );
};

export default GDPRBanner;
