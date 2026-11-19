package com.pulsestream.telemetry.support;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.DynamicPropertyRegistry;

public class SliceTestSupport {

    public static void registerProperties(DynamicPropertyRegistry registry) {
        PasswordEncoder encoder = PasswordEncoderFactories.createDelegatingPasswordEncoder();
        byte[] key = new byte[32];
        new SecureRandom().nextBytes(key);
        registry.add("telemetry.data-key", () -> Base64.getEncoder().encodeToString(key));
        registry.add("telemetry.devices[0].id", () -> "device-1");
        registry.add("telemetry.devices[0].secret-hash", () -> encoder.encode("device-secret"));
        registry.add("telemetry.devices[0].scope", () -> "telemetry:ingest");
        registry.add("telemetry.consumers[0].id", () -> "stream-consumer");
        registry.add("telemetry.consumers[0].secret-hash", () -> encoder.encode("stream-secret"));
        registry.add("telemetry.consumers[0].scope", () -> "telemetry:subscribe");
    }

    public static String basicAuthHeader(String deviceId, String secret) {
        String token = Base64.getEncoder().encodeToString((deviceId + ":" + secret).getBytes(StandardCharsets.UTF_8));
        return "Basic " + token;
    }
}
