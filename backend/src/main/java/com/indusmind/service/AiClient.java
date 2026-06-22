package com.indusmind.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import java.nio.file.Path;
import java.util.*;

@Service
public class AiClient {
    private final RestClient client;
    public AiClient(@Value("${indusmind.ai-base-url}") String baseUrl) {
        this.client = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(new SimpleClientHttpRequestFactory())
                .build();
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> process(Path path, Long documentId, String originalName) {
        return client.post().uri("/ai/documents/process-path")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of(
                        "file_path", path.toAbsolutePath().normalize().toString(),
                        "document_id", documentId.toString(),
                        "original_name", originalName))
                .retrieve().body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> ask(String question, String assetTag) {
        return client.post().uri("/ai/answer")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("question", question, "asset_tag", assetTag == null ? "" : assetTag))
                .retrieve().body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> asset(String tag) {
        return client.get().uri("/ai/assets/{tag}", tag).retrieve().body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> rca(String tag) {
        return client.post().uri("/ai/rca")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("asset_tag", tag)).retrieve().body(Map.class);
    }

    public boolean healthy() {
        try { client.get().uri("/ai/health").retrieve().toBodilessEntity(); return true; }
        catch (Exception ex) { return false; }
    }
}
