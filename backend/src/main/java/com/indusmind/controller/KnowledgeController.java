package com.indusmind.controller;

import com.indusmind.domain.QueryLog;
import com.indusmind.repository.DocumentRepository;
import com.indusmind.repository.QueryLogRepository;
import com.indusmind.service.AiClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController
@RequestMapping("/api")
public class KnowledgeController {
    private final AiClient ai;
    private final DocumentRepository documents;
    private final QueryLogRepository queries;
    public KnowledgeController(AiClient ai, DocumentRepository documents, QueryLogRepository queries) {
        this.ai = ai; this.documents = documents; this.queries = queries;
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        return Map.of("status", "UP", "service", "spring-api", "aiService", ai.healthy() ? "UP" : "DOWN");
    }

    @GetMapping("/dashboard")
    public Map<String, Object> dashboard() {
        Set<String> assets = new TreeSet<>();
        documents.findAll().forEach(d -> {
            if (d.getAssetTags() != null) Arrays.stream(d.getAssetTags().split(",")).map(String::trim)
                    .filter(s -> !s.isBlank()).forEach(assets::add);
        });
        return Map.of(
                "documents", documents.count(),
                "readyDocuments", documents.countByStatus("READY"),
                "assets", assets.size(),
                "queries", queries.count(),
                "assetTags", assets,
                "recentQueries", queries.findTop5ByOrderByCreatedAtDesc(),
                "aiOnline", ai.healthy());
    }

    @PostMapping("/chat/query")
    public ResponseEntity<?> ask(@RequestBody ChatRequest request) {
        if (request.question() == null || request.question().isBlank())
            return ResponseEntity.badRequest().body(Map.of("message", "Question is required"));
        try {
            Map<String, Object> result = ai.ask(request.question(), request.assetTag());
            QueryLog log = new QueryLog();
            log.setQuestion(request.question());
            log.setAnswer(String.valueOf(result.getOrDefault("answer", "")));
            log.setMode(String.valueOf(result.getOrDefault("mode", "offline")));
            Object confidence = result.getOrDefault("confidence", 0.0);
            log.setConfidence(confidence instanceof Number n ? n.doubleValue() : 0.0);
            queries.save(log);
            return ResponseEntity.ok(result);
        } catch (Exception ex) {
            return ResponseEntity.status(503).body(Map.of("message", "AI service is unavailable", "detail", ex.getMessage()));
        }
    }

    @GetMapping("/assets/{tag}")
    public ResponseEntity<?> asset(@PathVariable String tag) {
        try { return ResponseEntity.ok(ai.asset(tag)); }
        catch (Exception ex) { return ResponseEntity.status(503).body(Map.of("message", "AI service unavailable")); }
    }

    @PostMapping("/assets/{tag}/rca")
    public ResponseEntity<?> rca(@PathVariable String tag) {
        try { return ResponseEntity.ok(ai.rca(tag)); }
        catch (Exception ex) { return ResponseEntity.status(503).body(Map.of("message", "AI service unavailable")); }
    }

    public record ChatRequest(String question, String assetTag) {}
}

