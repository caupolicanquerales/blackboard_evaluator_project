package com.blackboard.telemetry.eventlog.application;

import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import com.blackboard.telemetry.eventlog.domain.EventRevision;
import com.blackboard.telemetry.shared.events.TelemetryEvents.BackfilledSampleReindexed;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetryRevisionAppended;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidated;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidationFailed;
import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public class AppendTelemetryRecordService {

    private final TelemetryEventStore store;

    public AppendTelemetryRecordService(TelemetryEventStore store) {
        this.store = Objects.requireNonNull(store, "store must not be null");
    }

    public Mono<TelemetryRevisionAppended> append(TelemetrySampleValidationFailed sample) {
        Objects.requireNonNull(sample, "sample must not be null");
        return appendFirst(sample.deviceId(), sample.tDevice(), sample.tIngress(), sample.metric(), sample.value(), sample.status());
    }

    public Mono<TelemetryRevisionAppended> append(BackfilledSampleReindexed sample) {
        Objects.requireNonNull(sample, "sample must not be null");
        return Mono.defer(() -> store.history(sample.deviceId(), sample.tDevice()).collectList()).flatMap(history -> store.append(nextRevisionOf(history, sample))).map(saved -> new TelemetryRevisionAppended(saved.deviceId(), saved.tDevice(), saved.tIngress(), sample.metric(), sample.value(), saved.validationStatus(), saved.revision()));
    }

    public Flux<EventRevision> history(String deviceId, Instant tDevice) {
        return Flux.defer(() -> store.history(deviceId, tDevice)).sort(Comparator.comparingInt(EventRevision::revision));
    }

    private Mono<TelemetryRevisionAppended> appendFirst(String deviceId, Instant tDevice, Instant tIngress, String metric, double value, ValidationStatus status) {
        return Mono.defer(() -> store.append(EventRevision.first(deviceId, tDevice, tIngress, status, payloadOf(metric, value)))).map(saved -> new TelemetryRevisionAppended(saved.deviceId(), saved.tDevice(), saved.tIngress(), metric, value, saved.validationStatus(), saved.revision()));
    }

    private static EventRevision nextRevisionOf(List<EventRevision> history, BackfilledSampleReindexed sample) {
        String payload = payloadOf(sample.metric(), sample.value());
        return history.stream().max(Comparator.comparingInt(EventRevision::revision)).map(latest -> latest.nextRevision(sample.tIngress(), sample.status(), payload)).orElseGet(() -> EventRevision.first(sample.deviceId(), sample.tDevice(), sample.tIngress(), sample.status(), payload));
    }

    private static String payloadOf(String metric, double value) {
        return metric + "=" + value;
    }

    public Mono<TelemetryRevisionAppended> append(TelemetrySampleValidated sample) {
        Objects.requireNonNull(sample, "sample must not be null");
        return appendFirst(sample.deviceId(), sample.tDevice(), sample.tIngress(), sample.metric(), sample.value(), sample.status());
    }
}
