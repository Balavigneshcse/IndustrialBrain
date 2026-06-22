package com.indusmind.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "query_logs")
public class QueryLog {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(nullable = false, length = 1000)
    private String question;
    @Column(length = 5000)
    private String answer;
    private String mode;
    private double confidence;
    private Instant createdAt = Instant.now();

    public Long getId() { return id; }
    public String getQuestion() { return question; }
    public void setQuestion(String question) { this.question = question; }
    public String getAnswer() { return answer; }
    public void setAnswer(String answer) { this.answer = answer; }
    public String getMode() { return mode; }
    public void setMode(String mode) { this.mode = mode; }
    public double getConfidence() { return confidence; }
    public void setConfidence(double confidence) { this.confidence = confidence; }
    public Instant getCreatedAt() { return createdAt; }
}

