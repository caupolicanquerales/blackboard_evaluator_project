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
        String dataKey = Base64.getEncoder().encodeToString(key);
        String deviceHash = encoder.encode("device-secret");
        String consumerHash = encoder.encode("stream-secret");
        registry.add("TELEMETRY_DATA_KEY", () -> dataKey);
        registry.add("TELEMETRY_DEVICE_SECRET_HASH", () -> deviceHash);
        registry.add("TELEMETRY_CONSUMER_SECRET_HASH", () -> consumerHash);
        registry.add("telemetry.data-key", () -> dataKey);
        registry.add("telemetry.devices[0].id", () -> "device-1");
        registry.add("telemetry.devices[0].secret-hash", () -> deviceHash);
        registry.add("telemetry.devices[0].scope", () -> "telemetry:ingest");
        registry.add("telemetry.consumers[0].id", () -> "stream-consumer");
        registry.add("telemetry.consumers[0].secret-hash", () -> consumerHash);
        registry.add("telemetry.consumers[0].scope", () -> "telemetry:subscribe");
    }

    public static String basicAuthHeader(String deviceId, String secret) {
        String token = Base64.getEncoder().encodeToString((deviceId + ":" + secret).getBytes(StandardCharsets.UTF_8));
        return "Basic " + token;
    }
}
