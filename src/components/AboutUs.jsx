import React from 'react';
import { Mail, MessageSquare, Shield, Code, Cpu, Globe, Lock } from 'lucide-react';

const AboutUs = () => {
    return (
        <div className="animate-fade-in" style={{
            maxWidth: '900px',
            margin: '2rem auto',
            padding: '2rem',
            color: 'var(--text-primary)'
        }}>
            {/* Header Section */}
            <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
                <h1 style={{
                    fontSize: '3rem',
                    fontWeight: 'bold',
                    marginBottom: '1rem',
                    background: 'linear-gradient(135deg, var(--text-primary), var(--accent-color))',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent'
                }}>
                    About Us
                </h1>
                <p style={{ fontSize: '1.2rem', color: 'var(--text-secondary)' }}>
                    Building the future of career optimization
                </p>
            </div>

            {/* Credit Section */}
            <div style={{
                background: 'var(--bg-card)',
                borderRadius: '16px',
                padding: '2rem',
                marginBottom: '2rem',
                border: '1px solid var(--border-color)',
                textAlign: 'center'
            }}>
                <p style={{ fontSize: '1.3rem', fontWeight: '500' }}>
                    This website was brought to you by <span style={{ color: 'var(--accent-color)', fontWeight: 'bold' }}>Aymane Merbouh</span>
                </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem' }}>

                {/* Contact Section */}
                <div style={{
                    background: 'var(--bg-card)',
                    borderRadius: '16px',
                    padding: '2rem',
                    border: '1px solid var(--border-color)'
                }}>
                    <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.5rem', marginBottom: '1.5rem' }}>
                        <MessageSquare className="text-emerald-500" />
                        Contact Me
                    </h2>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
                            <Mail size={20} style={{ color: 'var(--text-secondary)' }} />
                            <div>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Email</div>
                                <div style={{ fontWeight: '500' }}>aymanemerbouh03@gmail.com</div>
                            </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
                            <MessageSquare size={20} style={{ color: 'var(--text-secondary)' }} />
                            <div>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Discord</div>
                                <div style={{ fontWeight: '500' }}>gentlereformed</div>
                            </div>
                        </div>

                        <a href="https://aymanemerbouh.com" target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none', color: 'inherit' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px', cursor: 'pointer', transition: 'background 0.2s' }}>
                                <Globe size={20} style={{ color: 'var(--accent-color)' }} />
                                <div>
                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Website</div>
                                    <div style={{ fontWeight: '500', color: 'var(--accent-color)' }}>aymanemerbouh.com</div>
                                </div>
                            </div>
                        </a>
                    </div>
                </div>

                {/* Technologies Section */}
                <div style={{
                    background: 'var(--bg-card)',
                    borderRadius: '16px',
                    padding: '2rem',
                    border: '1px solid var(--border-color)'
                }}>
                    <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.5rem', marginBottom: '1.5rem' }}>
                        <Cpu className="text-blue-500" />
                        Technologies Used
                    </h2>

                    <div style={{ display: 'grid', gap: '1rem' }}>
                        {[
                            { name: 'React', icon: Globe, desc: 'Frontend Framework' },
                            { name: 'Three.js / Vanta.js', icon: Code, desc: '3D Visuals' },
                            { name: 'Python / Flask', icon: Code, desc: 'Backend Processing' },
                            { name: 'AI Models', icon: Cpu, desc: 'CV Analysis & Generation' }
                        ].map((tech, i) => (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.8rem', borderBottom: i !== 3 ? '1px solid var(--border-color)' : 'none' }}>
                                <tech.icon size={16} />
                                <div>
                                    <div style={{ fontWeight: '500' }}>{tech.name}</div>
                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{tech.desc}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Protections Section */}
            <div style={{
                background: 'var(--bg-card)',
                borderRadius: '16px',
                padding: '2rem',
                marginTop: '2rem',
                border: '1px solid var(--border-color)'
            }}>
                <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.5rem', marginBottom: '1.5rem' }}>
                    <Shield className="text-purple-500" />
                    Security & Protections
                </h2>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                    {[
                        { title: 'Data Encryption', desc: 'All user data is encrypted in transit and at rest.' },
                        { title: 'GDPR Compliant', desc: 'Full transparency and control over your data.' },
                        { title: 'Secure Processing', desc: 'Isolated environments for document processing.' },
                        { title: 'No Data Sharing', desc: 'Your CVs are never shared with third parties.' }
                    ].map((item, i) => (
                        <div key={i} style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
                            <Lock size={20} style={{ marginBottom: '0.5rem', color: 'var(--accent-color)' }} />
                            <div style={{ fontWeight: '600', marginBottom: '0.5rem' }}>{item.title}</div>
                            <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{item.desc}</div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default AboutUs;
