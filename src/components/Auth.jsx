import React, { useState } from 'react';
import { User, Lock, Mail, ArrowRight } from 'lucide-react';

export const AuthModal = ({ isOpen, onClose, onLogin, mode = 'login' }) => {
    const [isLogin, setIsLogin] = useState(mode === 'login');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        const endpoint = isLogin ? '/api/login' : '/api/register';

        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await res.json();

            if (res.ok) {
                onLogin(data);
                onClose();
            } else {
                setError(data.error || 'Something went wrong');
            }
        } catch (err) {
            setError('Network error');
        }
    };

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(5px)',
            display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000
        }} onClick={onClose}>
            <div style={{
                background: 'var(--bg-card)', padding: '2rem', borderRadius: '16px',
                width: '400px', maxWidth: '90%', border: '1px solid var(--border-color)',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
            }} onClick={e => e.stopPropagation()}>

                <h2 style={{ fontSize: '1.5rem', marginBottom: '1.5rem', textAlign: 'center' }}>
                    {isLogin ? 'Welcome Back' : 'Create Account'}
                </h2>

                {error && <div style={{ color: '#ef4444', marginBottom: '1rem', textAlign: 'center' }}>{error}</div>}

                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div className="input-with-icon" style={{ position: 'relative' }}>
                        <Mail size={18} style={{ position: 'absolute', top: '50%', left: '12px', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        <input
                            type="email" placeholder="Email" required
                            value={email} onChange={e => setEmail(e.target.value)}
                            style={{
                                width: '100%', padding: '12px 12px 12px 40px',
                                background: 'var(--bg-secondary)', border: '1px solid var(--border-color)',
                                borderRadius: '8px', color: 'white'
                            }}
                        />
                    </div>

                    <div className="input-with-icon" style={{ position: 'relative' }}>
                        <Lock size={18} style={{ position: 'absolute', top: '50%', left: '12px', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        <input
                            type="password" placeholder="Password" required
                            value={password} onChange={e => setPassword(e.target.value)}
                            style={{
                                width: '100%', padding: '12px 12px 12px 40px',
                                background: 'var(--bg-secondary)', border: '1px solid var(--border-color)',
                                borderRadius: '8px', color: 'white'
                            }}
                        />
                    </div>

                    <button type="submit" style={{
                        background: 'var(--accent-color)', color: 'white', padding: '12px',
                        borderRadius: '8px', fontWeight: 'bold', marginTop: '0.5rem',
                        display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px'
                    }}>
                        {isLogin ? 'Login' : 'Using Email'} <ArrowRight size={18} />
                    </button>
                </form>

                <p style={{ marginTop: '1.5rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    {isLogin ? "Don't have an account? " : "Already have an account? "}
                    <button
                        onClick={() => setIsLogin(!isLogin)}
                        style={{ color: 'var(--accent-color)', background: 'none', padding: 0, fontWeight: '600' }}
                    >
                        {isLogin ? 'Sign up' : 'Login'}
                    </button>
                </p>
            </div>
        </div>
    );
};
