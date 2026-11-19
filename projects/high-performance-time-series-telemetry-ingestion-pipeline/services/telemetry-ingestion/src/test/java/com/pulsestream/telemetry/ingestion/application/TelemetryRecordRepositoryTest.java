package com.pulsestream.telemetry.ingestion.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.ingestion.domain.TelemetryRevision;
import com.pulsestream.telemetry.ingestion.domain.TelemetrySample;
import com.pulsestream.telemetry.ingestion.domain.ValidationStatus;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class TelemetryRecordRepositoryTest {

    private static final Instant T_DEVICE = Instant.parse("2026-01-01T00:00:00Z");

    private static TelemetrySample sample() {
        return new TelemetrySample("dev-1", "heart_rate", T_DEVICE, T_DEVICE.plusSeconds(1), 60.0,
                ValidationStatus.VALIDATED, "{}");
    }

    private static final class InMemoryRepository implements TelemetryRecordRepository {
        private final Map<String, TelemetryRevision> latest = new HashMap<>();

        private static String key(String deviceId, String metric, Instant tDevice) {
            return deviceId + "|" + metric + "|" + tDevice;
        }

        @Override
        public Mono<Boolean> appendRecord(TelemetrySample s) {
            String k = key(s.deviceId(), s.metric(), s.tDevice());
            if (latest.containsKey(k)) {
                return Mono.just(false);
            }
            latest.put(k, new TelemetryRevision(s.deviceId(), s.metric(), s.tDevice(), 1, s.value(), "initial"));
            return Mono.just(true);
        }

        @Override
        public Mono<Void> appendRevision(TelemetryRevision r) {
            latest.put(key(r.deviceId(), r.metric(), r.tDevice()), r);
            return Mono.empty();
        }

        @Override
        public Mono<TelemetryRevision> findLatestRevision(String deviceId, String metric, Instant tDevice) {
            return Mono.justOrEmpty(latest.get(key(deviceId, metric, tDevice)));
        }
    }

    @Test
    void appendRecord_newIdentity_emitsTrueAndWritesRevisionOne() {
        InMemoryRepository repository = new InMemoryRepository();

        StepVerifier.create(repository.appendRecord(sample())).expectNext(true).verifyComplete();

        StepVerifier.create(repository.findLatestRevision("dev-1", "heart_rate", T_DEVICE))
                .assertNext(r -> assertThat(r.revisionNumber()).isEqualTo(1))
                .verifyComplete();
    }

    @Test
    void appendRecord_existingIdentity_emitsFalse() {
        InMemoryRepository repository = new InMemoryRepository();
        repository.appendRecord(sample()).block();

        StepVerifier.create(repository.appendRecord(sample())).expectNext(false).verifyComplete();
    }

    @Test
    void findLatestRevision_unknownIdentity_isEmpty() {
        InMemoryRepository repository = new InMemoryRepository();

        StepVerifier.create(repository.findLatestRevision("dev-1", "heart_rate", T_DEVICE)).verifyComplete();
    }

    @Test
    void appendRevision_afterRecord_makesNewRevisionLatest() {
        InMemoryRepository repository = new InMemoryRepository();
        repository.appendRecord(sample()).block();
        TelemetryRevision second = new TelemetryRevision("dev-1", "heart_rate", T_DEVICE, 2, 61.0, "correction");

        StepVerifier.create(repository.appendRevision(second)).verifyComplete();

        StepVerifier.create(repository.findLatestRevision("dev-1", "heart_rate", T_DEVICE))
                .expectNext(second)
                .verifyComplete();
    }
}
