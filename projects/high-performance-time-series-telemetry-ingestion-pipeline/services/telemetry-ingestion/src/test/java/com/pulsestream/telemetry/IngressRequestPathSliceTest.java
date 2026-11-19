package com.pulsestream.telemetry.support;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.test.StepVerifier;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class IngressRequestPathSliceTest {

    private static final String DEVICE = "device-1";
    private static final String SECRET = "device-secret";
    private static final String T_DEVICE = "2026-01-01T00:00:00Z";

    @Autowired
    WebTestClient client;

    @Autowired
    DatabaseClient db;

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry registry) {
        SliceTestSupport.registerProperties(registry);
    }

    private Map<String, Object> packet(String deviceId, double value) {
        return Map.of("deviceId", deviceId, "metric", "temperature", "tDevice", T_DEVICE, "value", value);
    }

    private WebTestClient.ResponseSpec post(Map<String, Object> body, String auth) {
        WebTestClient.RequestBodySpec spec = client.post().uri("/telemetry/ingress")
                .contentType(MediaType.APPLICATION_JSON);
        if (auth != null) {
            spec.header(HttpHeaders.AUTHORIZATION, auth);
        }
        return spec.bodyValue(body).exchange();
    }

    private long count(String table) {
        return db.sql("SELECT COUNT(*) AS c FROM " + table).map(r -> r.get("c", Number.class).longValue())
                .one().block(Duration.ofSeconds(5));
    }

    @Test
    void basicAuthHeader_deviceAndSecret_returnsBasicBase64Credentials() {
        String expected = "Basic " + Base64.getEncoder()
                .encodeToString((DEVICE + ":" + SECRET).getBytes(StandardCharsets.UTF_8));

        assertThat(SliceTestSupport.basicAuthHeader(DEVICE, SECRET)).isEqualTo(expected);
    }

    @Test
    void ingress_validPacket_returns202AndPersistsRecordRevisionAndAudit() {
        post(packet(DEVICE, 21.5), SliceTestSupport.basicAuthHeader(DEVICE, SECRET)).expectStatus().isAccepted();

        assertThat(count("telemetry_records")).isEqualTo(1);
        assertThat(count("telemetry_revisions")).isEqualTo(1);
        assertThat(count("audit_trail")).isGreaterThanOrEqualTo(1);
    }

    @Test
    void ingress_samePacketResent_addsNoNewRow() {
        String auth = SliceTestSupport.basicAuthHeader(DEVICE, SECRET);
        post(packet(DEVICE, 22.0), auth).expectStatus().isAccepted();
        long records = count("telemetry_records");
        long revisions = count("telemetry_revisions");

        post(packet(DEVICE, 22.0), auth).expectStatus().isAccepted();

        assertThat(count("telemetry_records")).isEqualTo(records);
        assertThat(count("telemetry_revisions")).isEqualTo(revisions);
    }

    @Test
    void ingress_sameIdentityNewValue_appendsRevisionTwo() {
        String auth = SliceTestSupport.basicAuthHeader(DEVICE, SECRET);
        post(packet(DEVICE, 23.0), auth).expectStatus().isAccepted();

        post(packet(DEVICE, 24.0), auth).expectStatus().isAccepted();

        Long max = db.sql("SELECT MAX(revision_number) AS r FROM telemetry_revisions")
                .map(r -> r.get("r", Number.class).longValue()).one().block(Duration.ofSeconds(5));
        assertThat(max).isEqualTo(2L);
    }

    @Test
    void ingress_foreignDeviceId_returns403AndPersistsNothing() {
        long before = count("telemetry_records");

        post(packet("device-other", 25.0), SliceTestSupport.basicAuthHeader(DEVICE, SECRET))
                .expectStatus().isForbidden();

        assertThat(count("telemetry_records")).isEqualTo(before);
    }

    @Test
    void ingress_noCredential_returns401() {
        post(packet(DEVICE, 26.0), null).expectStatus().isUnauthorized();
    }

    @Test
    void stream_authorizedSubscriber_receivesPublishedWindow() {
        var windows = client.get().uri("/telemetry/stream")
                .accept(MediaType.TEXT_EVENT_STREAM)
                .header(HttpHeaders.AUTHORIZATION,
                        SliceTestSupport.basicAuthHeader("stream-consumer", "stream-secret"))
                .exchange().expectStatus().isOk()
                .returnResult(new ParameterizedTypeReference<Map<String, Object>>() { })
                .getResponseBody();
        post(packet(DEVICE, 27.0), SliceTestSupport.basicAuthHeader(DEVICE, SECRET)).expectStatus().isAccepted();

        StepVerifier.create(windows.take(1))
                .assertNext(window -> assertThat(window).containsKeys("windowStart", "windowEnd", "events"))
                .expectComplete()
                .verify(Duration.ofSeconds(10));
    }

    @Test
    void stream_unauthorizedSubscriber_isRefused() {
        client.get().uri("/telemetry/stream")
                .header(HttpHeaders.AUTHORIZATION, SliceTestSupport.basicAuthHeader(DEVICE, SECRET))
                .exchange().expectStatus().isForbidden();
    }
}
