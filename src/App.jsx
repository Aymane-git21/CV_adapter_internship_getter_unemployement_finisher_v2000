import React, { useState, useEffect, useRef } from 'react';
import { Home, LayoutDashboard, User, LogOut, History as HistoryIcon, Info } from 'lucide-react';
import { BrowserRouter as Router, Routes, Route, Link, NavLink, useNavigate, useLocation } from 'react-router-dom';
import Hero from './components/Hero';
import JobForm from './components/JobForm';
import Results from './components/Results';
import History from './components/History';
import AboutUs from './components/AboutUs';
import { AuthModal } from './components/Auth';
import NET from 'vanta/dist/vanta.net.min';
import * as THREE from 'three';

import darkLogo from './assets/darkmode_logo.webp';
import lightLogo from './assets/lightmode_logo.webp';

import GDPRBanner from './components/GDPRBanner';

function AppContent() {
    const [user, setUser] = useState(null);
    const [showAuth, setShowAuth] = useState(false);
    const [darkMode, setDarkMode] = useState(true);
    const [vantaEffect, setVantaEffect] = useState(null);
    const [showGDPR, setShowGDPR] = useState(false);
    const vantaRef = useRef(null);
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        const gdprAccepted = localStorage.getItem('gdpr_accepted');
        if (!gdprAccepted) {
            setShowGDPR(true);
        }
    }, []);

    const handleAcceptGDPR = () => {
        localStorage.setItem('gdpr_accepted', 'true');
        setShowGDPR(false);
    };

    // Vanta.js Effect
    useEffect(() => {
        // Only initialize in Dark Mode
        if (darkMode && !vantaEffect && vantaRef.current) {
            try {
                const effect = NET({
                    el: vantaRef.current,
                    THREE: THREE,
                    mouseControls: true,
                    touchControls: true,
                    gyroControls: false,
                    minHeight: 200.00,
                    minWidth: 200.00,
                    scale: 1.00,
                    scaleMobile: 1.00,
                    color: 0x10b981,
                    backgroundColor: 0x0a0a0a,
                    points: 10.00,
                    maxDistance: 20.00,
                    spacing: 15.00
                });
                setVantaEffect(effect);
            } catch (error) {
                console.error("Vanta.js initialization failed:", error);
            }
        }

        // Cleanup when switching modes or unmounting
        return () => {
            if (vantaEffect) {
                vantaEffect.destroy();
                setVantaEffect(null);
            }
        };
    }, [darkMode, vantaEffect]);

    // Check auth on load
    useEffect(() => {
        fetch('/api/user_status')
            .then(res => res.json())
            .then(data => {
                if (data.logged_in) setUser(data);
            });
    }, []);

    // Dark Mode
    useEffect(() => {
        if (vantaEffect) {
            vantaEffect.setOptions({
                color: 0x10b981,
                backgroundColor: darkMode ? 0x0a0a0a : 0xf3f4f6
            });
        }

        document.body.style.transition = 'background-color 0.8s ease-in-out, color 0.8s ease-in-out';

        if (darkMode) {
            document.body.style.backgroundColor = 'var(--bg-primary)';
            document.body.style.color = 'var(--text-primary)';
            document.documentElement.style.setProperty('--bg-primary', '#0a0a0a');
            document.documentElement.style.setProperty('--bg-secondary', '#141414');
            document.documentElement.style.setProperty('--bg-card', '#1c1c1c');
            document.documentElement.style.setProperty('--text-primary', '#ffffff');
            document.documentElement.style.setProperty('--text-secondary', '#a1a1aa');
        } else {
            document.body.style.backgroundColor = '#f3f4f6';
            document.body.style.color = '#1f2937';
            document.documentElement.style.setProperty('--bg-primary', '#f3f4f6');
            document.documentElement.style.setProperty('--bg-secondary', '#ffffff');
            document.documentElement.style.setProperty('--bg-card', '#ffffff');
            document.documentElement.style.setProperty('--text-primary', '#111827');
            document.documentElement.style.setProperty('--text-secondary', '#4b5563');
        }
    }, [darkMode, vantaEffect]);

    const handleStart = () => {
        navigate('/app');
    };

    const handleLogout = async () => {
        await fetch('/api/logout', { method: 'POST' });
        setUser(null);
        window.location.reload();
    };

    const isActive = (path) => location.pathname === path;

    return (
        <div className="min-h-screen flex flex-col" style={{ position: 'relative', overflow: 'hidden' }}>
            {/* Vanta Background */}
            <div ref={vantaRef} style={{
                position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
                zIndex: -2, pointerEvents: 'none'
            }}></div>

            {/* Glassy Overlay */}
            <div style={{
                position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
                zIndex: -1, pointerEvents: 'none',
                background: darkMode ? 'rgba(5, 5, 5, 0.4)' : 'rgba(255, 255, 255, 0.4)',
                backdropFilter: 'blur(6px)',
                WebkitBackdropFilter: 'blur(6px)',
                transition: 'background-color 0.8s ease-in-out',
                animation: 'fadeOverlay 3s ease-out forwards'
            }}></div>

            <nav style={{
                height: '70px', borderBottom: '1px solid var(--border-color)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '0 2rem', backgroundColor: darkMode ? 'rgba(10,10,10,0.8)' : 'rgba(255,255,255,0.8)',
                backdropFilter: 'blur(10px)', position: 'sticky', top: 0, zIndex: 100
            }}>
                <div
                    onClick={() => navigate('/')}
                    style={{ fontSize: '1.5rem', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}
                >
                    <img src={darkMode ? darkLogo : lightLogo} alt="CV Tailor" style={{ height: '40px', objectFit: 'contain' }} />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    {/* Nav Links */}
                    <Link to="/" style={{ background: 'none', color: isActive('/') ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                        <Home size={20} />
                    </Link>

                    <Link to="/about" style={{ background: 'none', color: isActive('/about') ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                        <Info size={20} />
                    </Link>

                    {user && (
                        <Link to="/history" style={{ background: 'none', color: isActive('/history') ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                            <HistoryIcon size={20} />
                        </Link>
                    )}

                    {user ? (
                        <>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem' }}>
                                <User size={16} /> <span className="hide-mobile">{user.email}</span>
                                <span style={{
                                    background: 'var(--bg-secondary)', padding: '2px 8px', borderRadius: '12px',
                                    fontSize: '0.75rem', border: '1px solid var(--border-color)'
                                }}>
                                    Credits: {user.credits}
                                </span>
                            </div>
                            <button onClick={handleLogout} title="Logout" style={{ color: 'var(--text-secondary)', background: 'none' }}>
                                <LogOut size={20} />
                            </button>
                        </>
                    ) : (
                        <button
                            onClick={() => setShowAuth(true)}
                            style={{
                                background: 'var(--text-primary)', color: 'var(--bg-primary)',
                                padding: '8px 20px', borderRadius: '50px', fontWeight: '600'
                            }}
                        >
                            Login
                        </button>
                    )}
                </div>
            </nav>

            <main style={{ flex: 1, position: 'relative' }}>
                <Routes>
                    <Route path="/" element={<Hero onStart={handleStart} />} />
                    <Route path="/about" element={<AboutUs />} />
                    <Route path="/app" element={<JobFormWrapper user={user} />} />
                    <Route path="/history" element={<History />} />
                    {/* Fallback route */}
                    <Route path="*" element={<Hero onStart={handleStart} />} />
                </Routes>
            </main>

            <AuthModal isOpen={showAuth} onClose={() => setShowAuth(false)} onLogin={(u) => { setUser(u); setShowAuth(false); }} />

            {showGDPR && <GDPRBanner onAccept={handleAcceptGDPR} />}
        </div>
    );
}

function JobFormWrapper({ user }) {
    const [view, setView] = useState('form'); // form, processing, results
    const [logs, setLogs] = useState([]);
    const [result, setResult] = useState(null);
    const [jobId, setJobId] = useState(null);

    const handleJobSubmit = async (formData) => {
        setView('processing');
        setLogs(['Uploading and analyzing...']);

        try {
            const res = await fetch('/start_job', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (data.error) {
                alert(data.error);
                setView('form');
                return;
            }

            setJobId(data.job_id);
            pollStatus(data.job_id);
        } catch (e) {
            alert('Error starting job');
            setView('form');
        }
    };

    const pollStatus = (id) => {
        const interval = setInterval(async () => {
            const res = await fetch(`/job_status/${id}`);
            const data = await res.json();

            setLogs(data.logs || []);

            if (data.status === 'completed') {
                clearInterval(interval);
                setResult(data.result);
                setView('results');
            } else if (data.status === 'failed') {
                clearInterval(interval);
                const errorMsg = data.error_details || 'Job failed';
                alert('Job failed: ' + errorMsg);
                console.error("Job Failed Details:", data); // For debugging
                setView('form');
            }
        }, 1000);
    };

    if (view === 'processing') {
        return (
            <div style={{
                height: '80vh', display: 'flex', flexDirection: 'column',
                justifyContent: 'center', alignItems: 'center', textAlign: 'center'
            }}>
                <div className="loader" style={{
                    width: '50px', height: '50px', border: '4px solid var(--bg-card)',
                    borderTop: '4px solid var(--accent-color)', borderRadius: '50%', marginBottom: '2rem',
                    animation: 'spin 1s linear infinite'
                }}></div>
                <h3 style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>Optimizing your application...</h3>
                <div style={{
                    background: 'var(--bg-card)', padding: '1rem', borderRadius: '8px',
                    width: '400px', maxWidth: '90%', maxHeight: '200px', overflowY: 'auto',
                    fontFamily: 'monospace', fontSize: '0.9rem', textAlign: 'left',
                    border: '1px solid var(--border-color)'
                }}>
                    {logs.map((log, i) => (
                        <div key={i} style={{ marginBottom: '4px', color: 'var(--text-secondary)' }}>&gt; {log}</div>
                    ))}
                </div>
                <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
            </div>
        );
    }

    if (view === 'results' && result) {
        return <Results result={result} jobData={result.analysis} onReset={() => setView('form')} />;
    }

    return <div className="animate-fade-in"><JobForm onSubmit={handleJobSubmit} user={user} /></div>;
}

export default function App() {
    return (
        <Router>
            <AppContent />
        </Router>
    );
}
