package com.indusmind.controller;

import com.indusmind.domain.DocumentRecord;
import com.indusmind.repository.DocumentRepository;
import com.indusmind.service.AiClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.nio.file.*;
import java.util.*;

@RestController
@RequestMapping("/api/documents")
public class DocumentController {
    private final DocumentRepository documents;
    private final AiClient ai;
    private final Path uploadDir;
    public DocumentController(DocumentRepository documents, AiClient ai, @Value("${indusmind.upload-dir}") String dir) {
        this.documents = documents; this.ai = ai; this.uploadDir = Path.of(dir).toAbsolutePath().normalize();
    }

    @GetMapping
    public List<DocumentRecord> list() { return documents.findAllByOrderByUploadedAtDesc(); }

    @PostMapping
    public ResponseEntity<?> upload(@RequestParam("file") MultipartFile file) {
        if (file.isEmpty()) return ResponseEntity.badRequest().body(Map.of("message", "Choose a non-empty file"));
        String original = Objects.requireNonNullElse(file.getOriginalFilename(), "document");
        String extension = original.contains(".") ? original.substring(original.lastIndexOf('.')).toLowerCase() : "";
        if (!Set.of(".pdf", ".txt", ".csv", ".docx").contains(extension)) {
            return ResponseEntity.badRequest().body(Map.of("message", "Supported formats: PDF, TXT, CSV, DOCX"));
        }
        DocumentRecord record = new DocumentRecord();
        record.setOriginalName(original);
        record.setStoredName(UUID.randomUUID() + extension);
        record.setContentType(file.getContentType());
        record.setSizeBytes(file.getSize());
        record.setStatus("PROCESSING");
        record = documents.save(record);
        try {
            Files.createDirectories(uploadDir);
            Path destination = uploadDir.resolve(record.getStoredName());
            file.transferTo(destination);
            Map<String, Object> result = ai.process(destination, record.getId(), original);
            record.setStatus("READY");
            record.setDocumentType(String.valueOf(result.getOrDefault("document_type", "Industrial Document")));
            record.setSummary(String.valueOf(result.getOrDefault("summary", "Document indexed successfully.")));
            Object tags = result.get("asset_tags");
            record.setAssetTags(tags instanceof Collection<?> c ? String.join(", ", c.stream().map(String::valueOf).toList()) : "");
            return ResponseEntity.ok(documents.save(record));
        } catch (Exception ex) {
            record.setStatus("FAILED");
            record.setErrorMessage("AI service unavailable or processing failed: " + ex.getMessage());
            documents.save(record);
            return ResponseEntity.status(503).body(Map.of(
                    "message", "Document saved, but processing failed. Start the AI service and retry.",
                    "documentId", record.getId()));
        }
    }
}

