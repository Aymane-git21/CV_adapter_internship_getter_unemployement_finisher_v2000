import React, { useState, useEffect } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Save } from 'lucide-react';
import anime from 'animejs/lib/anime.es.js';

const JobForm = ({ onSubmit, user }) => {
    const [file, setFile] = useState(null);
    const [jobDescription, setJobDescription] = useState('');
    const [loading, setLoading] = useState(false);
    const [language, setLanguage] = useState('en');
    const [useSavedCV, setUseSavedCV] = useState(false);
    const [saveToProfile, setSaveToProfile] = useState(true);

    // New State for Input Method
    const [inputMethod, setInputMethod] = useState('upload'); // 'upload' or 'text'
    const [cvText, setCvText] = useState('');

    const handleFileChange = (e) => {
        if (e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!jobDescription) return;

        // Validation based on input method
        if (!useSavedCV) {
            if (inputMethod === 'upload' && !file) {
                alert("Please upload a CV PDF.");
                return;
            }
            if (inputMethod === 'text' && !cvText.trim()) {
                alert("Please paste your CV text.");
                return;
            }
        }

        setLoading(true);
        const formData = new FormData();
        formData.append('job_description', jobDescription);
        formData.append('language', language);

        if (useSavedCV) {
            // Backend uses saved CV logic
        } else {
            if (inputMethod === 'upload' && file) {
                formData.append('cv_file', file);
            } else if (inputMethod === 'text' && cvText) {
                formData.append('cv_text', cvText);
            }
            // Always send save preference if not using saved
            formData.append('save_cv', saveToProfile);
        }

        await onSubmit(formData);
        setLoading(false);
    };

    return (
        <div style={{ maxWidth: '800px', margin: '0 auto', padding: '2rem' }}>
            <h2 style={{ fontSize: '2rem', marginBottom: '2rem', textAlign: 'center' }}>Job Details</h2>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>

                {/* Language Toggle */}
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
                    <div style={{
                        background: 'var(--bg-secondary)', padding: '4px', borderRadius: '50px',
                        border: '1px solid var(--border-color)', display: 'flex'
                    }}>
                        <button
                            type="button"
                            onClick={() => setLanguage('en')}
                            style={{
                                padding: '8px 24px', borderRadius: '50px', fontWeight: 'bold',
                                background: language === 'en' ? 'var(--accent-color)' : 'transparent',
                                color: language === 'en' ? 'white' : 'var(--text-secondary)',
                                transition: 'all 0.2s'
                            }}
                        >
                            English
                        </button>
                        <button
                            type="button"
                            onClick={() => setLanguage('fr')}
                            style={{
                                padding: '8px 24px', borderRadius: '50px', fontWeight: 'bold',
                                background: language === 'fr' ? 'var(--accent-color)' : 'transparent',
                                color: language === 'fr' ? 'white' : 'var(--text-secondary)',
                                transition: 'all 0.2s'
                            }}
                        >
                            Français
                        </button>
                    </div>
                </div>

                {/* Job Description Input */}
                <div className="input-group" style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '12px' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
                        Job Description <span style={{ color: 'red' }}>*</span>
                    </label>
                    <textarea
                        style={{
                            width: '100%',
                            height: '200px',
                            background: 'var(--bg-secondary)',
                            border: '1px solid var(--border-color)',
                            borderRadius: '8px',
                            color: 'var(--text-primary)',
                            padding: '1rem',
                            resize: 'vertical',
                            fontSize: '1rem'
                        }}
                        placeholder="Paste the full job description here..."
                        value={jobDescription}
                        onChange={(e) => setJobDescription(e.target.value)}
                        required
                    />
                </div>

                {/* Saved CV Option */}
                {user && user.has_cv && (
                    <div style={{
                        background: 'rgba(16, 185, 129, 0.1)', border: '1px solid #10b981',
                        padding: '1rem', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '1rem'
                    }}>
                        <input
                            type="checkbox"
                            id="useSaved"
                            checked={useSavedCV}
                            onChange={(e) => setUseSavedCV(e.target.checked)}
                            style={{ width: '20px', height: '20px', accentColor: '#10b981' }}
                        />
                        <label htmlFor="useSaved" style={{ flex: 1, cursor: 'pointer', fontWeight: '600', color: '#10b981' }}>
                            Use my saved default CV
                        </label>
                        <CheckCircle size={20} color="#10b981" />
                    </div>
                )}

                {/* CV Input Section (Upload or Text) */}
                {!useSavedCV && (
                    <div className="input-group" style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '12px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                            <label style={{ color: 'var(--text-secondary)' }}>
                                Your CV <span style={{ color: 'red' }}>*</span>
                            </label>

                            {/* Input Method Toggle */}
                            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.9rem' }}>
                                <span
                                    onClick={() => setInputMethod('upload')}
                                    style={{
                                        cursor: 'pointer',
                                        color: inputMethod === 'upload' ? 'var(--accent-color)' : 'var(--text-secondary)',
                                        fontWeight: inputMethod === 'upload' ? 'bold' : 'normal',
                                        textDecoration: inputMethod === 'upload' ? 'underline' : 'none'
                                    }}
                                >
                                    Upload PDF
                                </span>
                                <span style={{ color: 'var(--border-color)' }}>|</span>
                                <span
                                    onClick={() => setInputMethod('text')}
                                    style={{
                                        cursor: 'pointer',
                                        color: inputMethod === 'text' ? 'var(--accent-color)' : 'var(--text-secondary)',
                                        fontWeight: inputMethod === 'text' ? 'bold' : 'normal',
                                        textDecoration: inputMethod === 'text' ? 'underline' : 'none'
                                    }}
                                >
                                    Paste Text
                                </span>
                            </div>
                        </div>

                        {/* CONDITIONAL RENDER: UPLOAD or TEXT */}
                        {inputMethod === 'upload' ? (
                            <div
                                style={{
                                    border: '2px dashed var(--border-color)',
                                    borderRadius: '8px',
                                    padding: '2rem',
                                    textAlign: 'center',
                                    cursor: 'pointer',
                                    transition: 'border-color 0.2s',
                                    background: 'var(--bg-secondary)'
                                }}
                                onClick={() => document.getElementById('cv-upload').click()}
                                onMouseEnter={(e) => e.target.style.borderColor = 'var(--accent-color)'}
                                onMouseLeave={(e) => e.target.style.borderColor = 'var(--border-color)'}
                            >
                                <input
                                    type="file"
                                    id="cv-upload"
                                    accept=".pdf"
                                    style={{ display: 'none' }}
                                    onChange={handleFileChange}
                                />
                                <Upload size={48} color="var(--text-secondary)" style={{ marginBottom: '1rem' }} />
                                <p style={{ color: 'var(--text-primary)' }}>
                                    {file ? file.name : "Click to upload or drag and drop"}
                                </p>
                                <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>PDF only, max 5MB</p>
                            </div>
                        ) : (
                            <textarea
                                style={{
                                    width: '100%',
                                    height: '200px',
                                    background: 'var(--bg-secondary)',
                                    border: '1px solid var(--border-color)',
                                    borderRadius: '8px',
                                    color: 'var(--text-primary)',
                                    padding: '1rem',
                                    resize: 'vertical',
                                    fontSize: '0.9rem',
                                    fontFamily: 'monospace'
                                }}
                                placeholder="Paste the text content of your CV here..."
                                value={cvText}
                                onChange={(e) => setCvText(e.target.value)}
                            />
                        )}

                        {/* Save to Profile Option - Only for logged-in users */}
                        {user && (
                            <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <input
                                    type="checkbox"
                                    id="saveProfile"
                                    checked={saveToProfile}
                                    onChange={(e) => setSaveToProfile(e.target.checked)}
                                    style={{ width: '16px', height: '16px', accentColor: 'var(--accent-color)' }}
                                />
                                <label htmlFor="saveProfile" style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', cursor: 'pointer' }}>
                                    Update my saved default CV with this content
                                </label>
                            </div>
                        )}
                    </div>
                )}

                <button
                    type="submit"
                    disabled={loading}
                    style={{
                        background: loading ? 'var(--bg-card)' : 'var(--accent-color)',
                        color: 'white',
                        padding: '1.2rem',
                        borderRadius: '8px',
                        fontSize: '1.1rem',
                        fontWeight: '600',
                        marginTop: '1rem',
                        cursor: loading ? 'not-allowed' : 'pointer'
                    }}
                >
                    {loading ? 'Processing...' : 'Generate Tailored CV'}
                </button>
            </form>
        </div>
    );
};

export default JobForm;
