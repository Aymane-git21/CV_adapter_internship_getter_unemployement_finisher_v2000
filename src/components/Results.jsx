import React from 'react';
import { Download, CheckCircle, FileText, Send } from 'lucide-react';

const Results = ({ result, jobData, onReset }) => {
    if (!result) return null;

    return (
        <div className="animate-fade-in" style={{ maxWidth: '900px', margin: '0 auto', padding: '2rem' }}>
            <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
                <div style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: '80px', height: '80px', borderRadius: '50%',
                    background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', marginBottom: '1rem'
                }}>
                    <CheckCircle size={40} />
                </div>
                <h2 style={{ fontSize: '2.5rem', fontWeight: 'bold' }}>Application Ready</h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '1.2rem' }}>
                    Tailored for <strong>{jobData.job_title}</strong> at <strong>{jobData.company}</strong>
                </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem' }}>
                {/* ATS Score Card */}
                {/* ATS Score Card */}
                <div style={{ background: 'var(--bg-card)', padding: '2rem', borderRadius: '16px', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        ATS Optimization
                    </h3>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1px 1fr', gap: '1rem', alignItems: 'center', marginBottom: '2rem' }}>
                        {/* Initial Score */}
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Before</div>
                            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--text-secondary)', opacity: 0.7 }}>
                                {result.initial_analysis ? result.initial_analysis.ats_score : 50}%
                            </div>
                        </div>

                        {/* Divider */}
                        <div style={{ width: '1px', height: '50px', background: 'var(--border-color)' }}></div>

                        {/* Final Score */}
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '0.9rem', color: 'var(--accent-color)', fontWeight: 'bold', marginBottom: '0.5rem' }}>After</div>
                            <div style={{ fontSize: '3rem', fontWeight: 'bold', color: '#10b981', textShadow: '0 0 20px rgba(16, 185, 129, 0.3)' }}>
                                {result.analysis.ats_score}%
                            </div>
                        </div>
                    </div>

                    <div style={{ marginBottom: '1rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Pending Keywords:</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {result.analysis.missing_keywords.map((kw, i) => (
                            <span key={i} style={{
                                background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444',
                                padding: '4px 12px', borderRadius: '20px', fontSize: '0.875rem'
                            }}>
                                {kw}
                            </span>
                        ))}
                        {result.analysis.missing_keywords.length === 0 && <span style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}><CheckCircle size={16} /> 100% Match!</span>}
                    </div>
                </div>

                {/* Downloads Card */}
                <div style={{ background: 'var(--bg-card)', padding: '2rem', borderRadius: '16px', border: '1px solid var(--border-color)' }}>
                    <h3 style={{ fontSize: '1.25rem', marginBottom: '1.5rem' }}>Your Documents</h3>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <a href={`/download/${result.cv_pdf}`}
                            style={{
                                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px',
                                border: '1px solid var(--border-color)', transition: 'border-color 0.2s'
                            }}
                            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent-color)'}
                            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-color)'}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                <FileText size={24} color="var(--accent-color)" />
                                <div>
                                    <div style={{ fontWeight: '600' }}>Tailored CV</div>
                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>PDF Document</div>
                                </div>
                            </div>
                            <Download size={20} />
                        </a>

                        <a href={`/download/${result.cl_pdf}`}
                            style={{
                                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                padding: '1rem', background: 'var(--bg-secondary)', borderRadius: '8px',
                                border: '1px solid var(--border-color)', transition: 'border-color 0.2s'
                            }}
                            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent-color)'}
                            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-color)'}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                <FileText size={24} color="var(--accent-color)" />
                                <div>
                                    <div style={{ fontWeight: '600' }}>Cover Letter</div>
                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>PDF Document</div>
                                </div>
                            </div>
                            <Download size={20} />
                        </a>
                    </div>
                </div>

                {/* Outreach Message Card */}
                <div style={{ background: 'var(--bg-card)', padding: '2rem', borderRadius: '16px', border: '1px solid var(--border-color)', gridColumn: '1 / -1' }}>
                    <h3 style={{ fontSize: '1.25rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Send size={20} color="var(--accent-color)" /> Outreach Message
                    </h3>
                    <div style={{
                        background: 'var(--bg-secondary)', padding: '1.5rem', borderRadius: '8px',
                        border: '1px solid var(--border-color)', fontFamily: 'monospace',
                        whiteSpace: 'pre-wrap', color: 'var(--text-secondary)'
                    }}>
                        {result.message_text}
                    </div>
                    <button
                        onClick={() => navigator.clipboard.writeText(result.message_text)}
                        style={{
                            marginTop: '1rem', background: 'transparent', color: 'var(--accent-color)',
                            fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px'
                        }}
                    >
                        Copy Message
                    </button>
                </div>
            </div>

            <div style={{ textAlign: 'center', marginTop: '3rem' }}>
                <button onClick={onReset} style={{
                    background: 'transparent', border: '1px solid var(--border-color)',
                    color: 'var(--text-secondary)', padding: '12px 24px', borderRadius: '50px'
                }}>
                    Start New Application
                </button>
            </div>
        </div>
    );
};

export default Results;
