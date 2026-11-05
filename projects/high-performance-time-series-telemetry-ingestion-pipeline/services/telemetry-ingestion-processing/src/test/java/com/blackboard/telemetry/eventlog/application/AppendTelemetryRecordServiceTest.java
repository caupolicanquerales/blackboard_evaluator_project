package com.blackboard.telemetry.eventlog.application;
import com.blackboard.telemetry.shared.events.TelemetryEvents;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Arrays;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import com.blackboard.telemetry.eventlog.domain.EventRevision;
import com.blackboard.telemetry.shared.events.TelemetryEvents.BackfilledSampleReindexed;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetryRevisionAppended;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidated;
import com.blackboard.telemetry.shared.events.TelemetryEvents.TelemetrySampleValidationFailed;
import com.blackboard.telemetry.shared.events.TelemetryEvents.ValidationStatus;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

@ExtendWith(MockitoExtension.class)
class AppendTelemetryRecordServiceTest {

    private static final String DEVICE = "device-1";
    private static final Instant T_DEVICE = Instant.parse("2026-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2026-01-01T10:00:05Z");

    @Mock
    private TelemetryEventStore store;

    @InjectMocks
    private AppendTelemetryRecordService service;

    private static TelemetrySampleValidated validated() {
        return new TelemetrySampleValidated(DEVICE, T_DEVICE, T_INGRESS, "heart_rate", 150.0,
                ValidationStatus.VALID);
    }

    private static TelemetrySampleValidationFailed failed() {
        return new TelemetrySampleValidationFailed(DEVICE, T_DEVICE, T_INGRESS, "heart_rate", 400.0,
                ValidationStatus.VALIDATION_FAILED);
    }

    private static BackfilledSampleReindexed reindexed() {
        return new BackfilledSampleReindexed(DEVICE, T_DEVICE, T_INGRESS, "heart_rate", 151.0,
                ValidationStatus.VALID);
    }

    private static EventRevision firstRevision() {
        return EventRevision.first(DEVICE, T_DEVICE, T_INGRESS, ValidationStatus.VALID, "heart_rate=150.0");
    }

    private void stubAppendEchoes() {
        when(store.append(any(EventRevision.class)))
                .thenAnswer(inv -> Mono.just(inv.<EventRevision>getArgument(0)));
    }

    private EventRevision capturedAppend() {
        ArgumentCaptor<EventRevision> captor = ArgumentCaptor.forClass(EventRevision.class);
        verify(store).append(captor.capture());
        return captor.getValue();
    }

    @Test
    void append_validatedSample_appendsRevisionZeroAndEmitsEvent() {
        stubAppendEchoes();

        StepVerifier.create(service.append(validated()))
                .assertNext(event -> {
                    assertThat(event.deviceId()).isEqualTo(DEVICE);
                    assertThat(event.tDevice()).isEqualTo(T_DEVICE);
                    assertThat(event.revision()).isEqualTo(0);
                })
                .verifyComplete();

        EventRevision saved = capturedAppend();
        assertThat(saved.revision()).isEqualTo(0);
        assertThat(saved.validationStatus()).isEqualTo(ValidationStatus.VALID);
    }

    @Test
    void append_validatedSample_keepsKeyAndIngressTime() {
        stubAppendEchoes();

        StepVerifier.create(service.append(validated())).expectNextCount(1).verifyComplete();

        EventRevision saved = capturedAppend();
        assertThat(saved.deviceId()).isEqualTo(DEVICE);
        assertThat(saved.tDevice()).isEqualTo(T_DEVICE);
        assertThat(saved.tIngress()).isEqualTo(T_INGRESS);
    }

    @Test
    void append_validationFailedSample_isKeptAsRawRecordWithFailedStatus() {
        stubAppendEchoes();

        StepVerifier.create(service.append(failed()))
                .assertNext(event -> assertThat(event.revision()).isEqualTo(0))
                .verifyComplete();

        EventRevision saved = capturedAppend();
        assertThat(saved.validationStatus()).isEqualTo(ValidationStatus.VALIDATION_FAILED);
        assertThat(saved.payload()).contains("400.0");
    }

    @Test
    void append_backfilledSample_appendsNextRevisionAndEmitsEvent() {
        when(store.history(DEVICE, T_DEVICE)).thenReturn(Flux.just(firstRevision()));
        stubAppendEchoes();

        StepVerifier.create(service.append(reindexed()))
                .assertNext(event -> assertThat(event.revision()).isEqualTo(1))
                .verifyComplete();

        assertThat(capturedAppend().revision()).isEqualTo(1);
    }

    @Test
    void append_backfilledSample_doesNotTouchOriginalRevision() {
        EventRevision original = firstRevision();
        when(store.history(DEVICE, T_DEVICE)).thenReturn(Flux.just(original));
        stubAppendEchoes();

        StepVerifier.create(service.append(reindexed())).expectNextCount(1).verifyComplete();

        assertThat(original).isEqualTo(firstRevision());
        assertThat(capturedAppend()).isNotEqualTo(original);
    }

    @Test
    void append_storeFails_propagatesErrorWithoutEmittingEvent() {
        when(store.append(any(EventRevision.class))).thenReturn(Mono.error(new IllegalStateException("db down")));

        StepVerifier.create(service.append(validated()))
                .expectErrorSatisfies(e -> assertThat(e)
                        .isInstanceOf(IllegalStateException.class)
                        .hasMessage("db down"))
                .verify();
    }

    @Test
    void append_duplicateKeyRejected_propagatesErrorWithoutEmittingEvent() {
        when(store.append(any(EventRevision.class)))
                .thenReturn(Mono.error(new IllegalStateException("duplicate key")));

        StepVerifier.create(service.append(failed()))
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void append_backfilledStoreFails_propagatesError() {
        when(store.history(DEVICE, T_DEVICE)).thenReturn(Flux.just(firstRevision()));
        when(store.append(any(EventRevision.class))).thenReturn(Mono.error(new IllegalStateException("boom")));

        StepVerifier.create(service.append(reindexed()))
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void append_historyReadFails_doesNotAppend() {
        when(store.history(DEVICE, T_DEVICE)).thenReturn(Flux.error(new IllegalStateException("read failed")));

        StepVerifier.create(service.append(reindexed()))
                .expectError(IllegalStateException.class)
                .verify();

        verify(store, never()).append(any(EventRevision.class));
    }

    @Test
    void append_validatedSample_isLazyUntilSubscribed() {
        Mono<TelemetryRevisionAppended> result = service.append(validated());

        verifyNoMoreInteractions(store);
        stubAppendEchoes();
        StepVerifier.create(result).expectNextCount(1).verifyComplete();
    }

    @Test
    void history_existingRevisions_returnsOrderedByRevision() {
        EventRevision r0 = firstRevision();
        EventRevision r1 = r0.correctedBy(T_INGRESS.plusSeconds(10), ValidationStatus.VALID, "heart_rate=151.0");
        EventRevision r2 = r1.correctedBy(T_INGRESS.plusSeconds(20), ValidationStatus.VALID, "heart_rate=152.0");
        when(store.history(DEVICE, T_DEVICE)).thenReturn(Flux.just(r2, r0, r1));

        StepVerifier.create(service.history(DEVICE, T_DEVICE).map(EventRevision::revision))
                .expectNext(0L, 1L, 2L)
                .verifyComplete();
    }

    @Test
    void history_unknownKey_returnsEmpty() {
        when(store.history(DEVICE, T_DEVICE)).thenReturn(Flux.empty());

        StepVerifier.create(service.history(DEVICE, T_DEVICE)).verifyComplete();
    }

    @Test
    void history_storeFails_propagatesError() {
        when(store.history(DEVICE, T_DEVICE)).thenReturn(Flux.error(new IllegalStateException("read failed")));

        StepVerifier.create(service.history(DEVICE, T_DEVICE))
                .expectError(IllegalStateException.class)
                .verify();
    }

    @Test
    void storePort_declaredOperations_areOnlyAppendAndReads() {
        List<String> names = Arrays.stream(TelemetryEventStore.class.getMethods())
                .map(java.lang.reflect.Method::getName)
                .distinct()
                .toList();

        assertThat(names).containsExactlyInAnyOrder("append", "history", "range");
    }
}
