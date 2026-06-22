package com.indusmind.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;

@Service
public class JwtService {
    private final byte[] secret;
    private final Base64.Encoder encoder = Base64.getUrlEncoder().withoutPadding();
    private final Base64.Decoder decoder = Base64.getUrlDecoder();

    public JwtService(@Value("${indusmind.jwt-secret}") String secret) {
        this.secret = secret.getBytes(StandardCharsets.UTF_8);
    }

    public String create(String username, String role) {
        String header = encoder.encodeToString("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
        long expires = Instant.now().plusSeconds(8 * 3600).getEpochSecond();
        String payloadJson = "{\"sub\":\"" + safe(username) + "\",\"role\":\"" + safe(role) + "\",\"exp\":" + expires + "}";
        String payload = encoder.encodeToString(payloadJson.getBytes(StandardCharsets.UTF_8));
        String unsigned = header + "." + payload;
        return unsigned + "." + sign(unsigned);
    }

    public Claims verify(String token) {
        String[] parts = token.split("\\.");
        if (parts.length != 3 || !constantTime(parts[2], sign(parts[0] + "." + parts[1]))) {
            throw new IllegalArgumentException("Invalid token");
        }
        String json = new String(decoder.decode(parts[1]), StandardCharsets.UTF_8);
        String username = value(json, "sub");
        String role = value(json, "role");
        long expiry = Long.parseLong(numberValue(json, "exp"));
        if (Instant.now().getEpochSecond() >= expiry) throw new IllegalArgumentException("Token expired");
        return new Claims(username, role);
    }

    private String sign(String value) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret, "HmacSHA256"));
            return encoder.encodeToString(mac.doFinal(value.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }

    private boolean constantTime(String a, String b) {
        return java.security.MessageDigest.isEqual(a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8));
    }
    private String safe(String value) { return value.replace("\\", "").replace("\"", ""); }
    private String value(String json, String key) {
        String marker = "\"" + key + "\":\"";
        int start = json.indexOf(marker) + marker.length();
        int end = json.indexOf('"', start);
        return json.substring(start, end);
    }
    private String numberValue(String json, String key) {
        String marker = "\"" + key + "\":";
        int start = json.indexOf(marker) + marker.length();
        int end = json.indexOf('}', start);
        return json.substring(start, end);
    }
    public record Claims(String username, String role) {}
}

