package com.pulsestream.telemetry.ledger.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.TelemetrySample;
import com.pulsestream.telemetry.ledger.api.LedgerController.RevisionResponse;
import com.pulsestream.telemetry.ledger.application.TelemetryHistoryQueryService;
import com.pulsestream.telemetry.ledger.domain.EventRevision;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@ExtendWith(MockitoExtension.class)
class LedgerControllerTest {

    private static final String DEVICE = "device-1";
    private static final Instant T_DEVICE = Instant.parse("2024-01-01T10:00:00Z");
    private static final Instant T_INGRESS = Instant.parse("2024-01-01T10:00:05Z");
    private static final Instant RECORDED_AT = Instant.parse("2024-01-01T10:00:10Z");

    @Mock
    private TelemetryHistoryQueryService service;

    @InjectMocks
    private LedgerController controller;

    private static TelemetrySample sample(double value) {
        UUID id = TelemetrySample.recordIdFor(DEVICE, TelemetrySample.MetricType.HEART_RATE, T_DEVICE);
        return new TelemetrySample(id, DEVICE, TelemetrySample.MetricType.HEART_RATE, value,
                T_DEVICE, T_INGRESS, TelemetrySample.ValidationStatus.VALID);
    }

    private static EventRevision original() {
        return EventRevision.original(sample(120.0), RECORDED_AT);
    }

    private static EventRevision correction(EventRevision previous) {
        return previous.next(sample(125.0), EventRevision.RevisionReason.CORRECTION, RECORDED_AT.plusSeconds(60));
    }

    @Test
    void from_revision_mapsAllFields() {
        EventRevision revision = original();

        RevisionResponse response = RevisionResponse.from(revision);

        assertThat(response).isEqualTo(new RevisionResponse(
                revision.recordId(), 1, "ORIGINAL", DEVICE, "HEART_RATE", 120.0,
                T_DEVICE, T_INGRESS, "VALID", RECORDED_AT));
    }

    @Test
    void revisions_existingRecord_returnsResponsesInRevisionOrder() {
        EventRevision first = original();
        EventRevision second = correction(first);
        when(service.revisions(first.recordId())).thenReturn(Flux.just(first, second));

        List<RevisionResponse> result = controller.revisions(first.recordId()).collectList().block();

        assertThat(result).extracting(RevisionResponse::revisionNumber).containsExactly(1, 2);
    }

    @Test
    void revisions_unknownRecord_returnsEmpty() {
        UUID id = UUID.fromString("00000000-0000-0000-0000-000000000001");
        when(service.revisions(id)).thenReturn(Flux.empty());

        assertThat(controller.revisions(id).collectList().block()).isEmpty();
    }

    @Test
    void latest_existingRecord_returnsLatestRevision() {
        EventRevision second = correction(original());
        when(service.latest(second.recordId())).thenReturn(Mono.just(second));

        RevisionResponse result = controller.latest(second.recordId()).block();

        assertThat(result).isEqualTo(RevisionResponse.from(second));
    }

    @Test
    void latest_absentRecord_failsWithNotFound() {
        UUID id = UUID.fromString("00000000-0000-0000-0000-000000000002");
        when(service.latest(id)).thenReturn(Mono.empty());

        assertThatThrownBy(() -> controller.latest(id).block())
                .isInstanceOf(ResponseStatusException.class)
                .extracting(e -> ((ResponseStatusException) e).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void history_matchingRange_returnsResponsesInServiceOrder() {
        EventRevision first = original();
        EventRevision second = correction(first);
        Instant from = T_DEVICE.minusSeconds(60);
        Instant to = T_DEVICE.plusSeconds(60);
        when(service.history(DEVICE, TelemetrySample.MetricType.HEART_RATE, from, to))
                .thenReturn(Flux.just(first, second));

        List<RevisionResponse> result = controller
                .history(DEVICE, TelemetrySample.MetricType.HEART_RATE, from, to).collectList().block();

        assertThat(result).containsExactly(RevisionResponse.from(first), RevisionResponse.from(second));
    }

    @Test
    void history_invalidRange_propagatesIllegalArgument() {
        Instant from = T_DEVICE.plusSeconds(60);
        Instant to = T_DEVICE.minusSeconds(60);
        when(service.history(DEVICE, TelemetrySample.MetricType.POWER, from, to))
                .thenReturn(Flux.error(new IllegalArgumentException("from after to")));

        assertThatThrownBy(() -> controller
                .history(DEVICE, TelemetrySample.MetricType.POWER, from, to).collectList().block())
                .isInstanceOf(IllegalArgumentException.class);
    }
}
