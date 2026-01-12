import React, { useEffect, useState } from 'react';
import { Clock, Briefcase, FileText } from 'lucide-react';

const History = () => {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch('/api/history')
            .then(res => res.json())
            .then(data => {
                setHistory(data);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading history...</div>;

    return (
        <div className="animate-fade-in" style={{ maxWidth: '800px', margin: '0 auto', padding: '2rem' }}>
            <h2 style={{ fontSize: '2rem', marginBottom: '2rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <Clock color="var(--accent-color)" /> Application History
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {history.length === 0 ? (
                    <p style={{ color: 'var(--text-secondary)' }}>No applications found.</p>
                ) : (
                    history.map(app => (
                        <div key={app.id} style={{
                            background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '12px',
                            border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                        }}>
                            <div>
                                <h3 style={{ fontSize: '1.2rem', fontWeight: '600' }}>{app.job}</h3>
                                <p style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Briefcase size={14} /> {app.company}
                                    <span style={{ margin: '0 8px' }}>•</span>
                                    {app.date}
                                </p>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--accent-color)' }}>
                                    {app.score}%
                                </div>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>ATS Score</div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default History;
