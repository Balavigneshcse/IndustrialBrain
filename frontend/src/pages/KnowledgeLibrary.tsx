import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { DocumentRecord } from '../types';
import { FileUploader } from '../components/FileUploader';
import { DocumentTable } from '../components/DocumentTable';

export const KnowledgeLibrary: React.FC = () => {
  const [docs, setDocs] = useState<DocumentRecord[]>([]);

  const fetchDocs = () => {
    api.getDocuments().then(setDocs).catch(console.error);
  };

  useEffect(() => {
    fetchDocs();
    const interval = setInterval(fetchDocs, 5000); // Status polling
    return () => clearInterval(interval);
  }, []);

  const handleUpload = async (file: File) => {
    try {
      // Processing continues in the background; the table polls until the status is ready or failed.
      await api.uploadDocument(file);
    } catch (err) {
      // e.g. duplicate file, unsupported type or too large: the server explains why
      alert(err instanceof Error ? err.message : 'Upload failed.');
    }
    fetchDocs();
  };

  const handleDelete = async (id: string) => {
    await api.deleteDocument(id);
    fetchDocs();
  };

  return (
    <div className="page-container animate-fade-in">
      <div className="hero-section">
        <h1 className="hero-title text-gradient">Build the evidence layer.</h1>
        <p className="hero-subtitle">Upload manuals, schematics, and logs. AI will process them into actionable knowledge.</p>
      </div>

      <FileUploader onUpload={handleUpload} />
      <DocumentTable documents={docs} onDelete={handleDelete} />
    </div>
  );
};
