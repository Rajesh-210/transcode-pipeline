import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api/v1';

export default function TranscodeDashboard() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [pollingInterval, setPollingInterval] = useState(null);

  const uploadVideo = async () => {
    if (!file) return alert('Please select a file');

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const { data } = await axios.post(`${API_BASE}/videos/upload`, formData);
      setJobs(prev => [{ ...data, status: 'queued', progress: 0 }, ...prev]);
      alert('Upload successful! Video is now in queue.');
    } catch (err) {
      alert('Upload failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUploading(false);
    }
  };

  const pollStatus = async (videoId) => {
    try {
      const { data } = await axios.get(`${API_BASE}/videos/${videoId}/status`);
      setJobs(prev => prev.map(job =>
        job.video_id === videoId ? { ...job, ...data } : job
      ));

      if (data.status !== 'completed' && data.status !== 'failed') {
        return true; // Keep polling
      }
    } catch (err) {
      console.error('Polling error for ' + videoId, err);
    }
    return false;
  };

  useEffect(() => {
    const interval = setInterval(async () => {
      const activeJobs = jobs.filter(j => j.status !== 'completed' && j.status !== 'failed');
      for (const job of activeJobs) {
        await pollStatus(job.video_id);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [jobs]);

  return (
    <div style={{
      fontFamily: 'system-ui, sans-serif',
      maxWidth: '800px',
      margin: '40px auto',
      padding: '20px',
      backgroundColor: '#f9f9f9',
      minHeight: '100vh'
    }}>
      <header style={{ textAlign: 'center', marginBottom: '40px' }}>
        <h1 style={{ color: '#333' }}>🎥 Media Transcoding Pipeline</h1>
        <p style={{ color: '#666' }}>DevOps Demonstration: Event-Driven HLS Transcoding</p>
      </header>

      <div style={{
        backgroundColor: 'white',
        padding: '30px',
        borderRadius: '12px',
        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
        marginBottom: '30px',
        textAlign: 'center'
      }}>
        <input
          type="file"
          onChange={(e) => setFile(e.target.files[0])}
          style={{ marginBottom: '20px', display: 'block', margin: '0 auto' }}
        />
        <button
          onClick={uploadVideo}
          disabled={uploading}
          style={{
            backgroundColor: '#0070f3',
            color: 'white',
            border: 'none',
            padding: '10px 20px',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '16px',
            fontWeight: '600'
          }}
        >
          {uploading ? 'Uploading...' : 'Upload & Transcode'}
        </button>
      </div>

      <div style={{ display: 'grid', gap: '20px' }}>
        {jobs.map(job => (
          <div key={job.video_id} style={{
            backgroundColor: 'white',
            padding: '20px',
            borderRadius: '12px',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: '18px' }}>{job.filename}</strong>
              <span style={{
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: 'bold',
                backgroundColor: job.status === 'completed' ? '#dcfce7' : job.status === 'failed' ? '#fee2e2' : '#fef9c3',
                color: job.status === 'completed' ? '#166534' : job.status === 'failed' ? '#991b1b' : '#854d0e'
              }}>
                {job.status.toUpperCase()}
              </span>
            </div>

            <div style={{ width: '100%', backgroundColor: '#eee', height: '8px', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{
                width: `${job.progress}%`,
                backgroundColor: '#0070f3',
                height: '100%',
                transition: 'width 0.3s ease'
              }} />
            </div>

            {job.status === 'completed' && (
              <div style={{ marginTop: '10px', display: 'flex', gap: '10px', alignItems: 'center' }}>
                <img
                  src={job.thumbnail_url}
                  alt="Thumbnail"
                  style={{ width: '120px', height: '68px', objectFit: 'cover', borderRadius: '4px', border: '1px solid #ddd' }}
                />
                <div>
                  <p style={{ margin: '0', fontSize: '14px', color: '#666' }}>Streaming ready!</p>
                  <a
                    href={job.hls_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#0070f3', fontSize: '14px', fontWeight: '600', textDecoration: 'none' }}
                  >
                    Open HLS Master Playlist →
                  </a>
                </div>
              </div>
            )}

            {job.status === 'failed' && (
              <p style={{ color: '#dc2626', fontSize: '14px' }}>{job.error}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}