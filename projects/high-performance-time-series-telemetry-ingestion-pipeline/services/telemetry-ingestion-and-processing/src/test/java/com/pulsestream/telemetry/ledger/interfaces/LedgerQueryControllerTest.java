package com.pulsestream.telemetry.ledger.interfaces;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.ledger.application.port.in.QueryTelemetryLedgerUseCase;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.reactive.server.WebTestClient;
import reactor.core.publisher.Flux;

@ExtendWith(MockitoExtension.class)
class LedgerQueryControllerTest {

    private static final String DEVICE = "dev-1";
    private static final Instant FROM = Instant.parse("2024-01-01T00:00:00Z");
    private static final Instant TO = Instant.parse("2024-01-02T00:00:00Z");
    private static final Instant T_DEVICE = Instant.parse("2024-01-01T10:15:30Z");

    @Mock
    private QueryTelemetryLedgerUseCase useCase;

    private WebTestClient client;

    @BeforeEach
    void setUp() {
        client = WebTestClient.bindToController(new LedgerQueryController(useCase)).build();
    }

    private static String recordsUri(String extra) {
        return "/api/v1/ledger/devices/" + DEVICE + "/records?from=" + FROM + "&to=" + TO + extra;
    }

    @Test
    void records_defaultLatestOnlyFalse_usesHistory() {
        when(useCase.history(DEVICE, FROM, TO)).thenReturn(Flux.empty());

        client.get().uri(recordsUri("")).exchange().expectStatus().isOk();

        verify(useCase).history(DEVICE, FROM, TO);
        verifyNoMoreInteractions(useCase);
    }

    @Test
    void records_latestOnlyFalse_usesHistory() {
        when(useCase.history(DEVICE, FROM, TO)).thenReturn(Flux.empty());

        client.get().uri(recordsUri("&latestOnly=false")).exchange().expectStatus().isOk();

        verify(useCase).history(DEVICE, FROM, TO);
        verify(useCase, never()).latestHistory(any(), any(), any());
    }

    @Test
    void records_latestOnlyTrue_usesLatestHistory() {
        when(useCase.latestHistory(DEVICE, FROM, TO)).thenReturn(Flux.empty());

        client.get().uri(recordsUri("&latestOnly=true")).exchange().expectStatus().isOk();

        verify(useCase).latestHistory(DEVICE, FROM, TO);
        verify(useCase, never()).history(any(), any(), any());
    }

    @Test
    void records_illegalArgument_returns400() {
        when(useCase.history(DEVICE, FROM, TO))
                .thenReturn(Flux.error(new IllegalArgumentException("bad range")));

        client.get().uri(recordsUri("")).exchange().expectStatus().isBadRequest();
    }

    @Test
    void records_illegalArgumentOnLatestOnly_returns400() {
        when(useCase.latestHistory(DEVICE, FROM, TO))
                .thenReturn(Flux.error(new IllegalArgumentException("bad range")));

        client.get().uri(recordsUri("&latestOnly=true")).exchange().expectStatus().isBadRequest();
    }

    @Test
    void records_malformedInstant_returns400() {
        client.get()
                .uri("/api/v1/ledger/devices/" + DEVICE + "/records?from=not-an-instant&to=" + TO)
                .exchange()
                .expectStatus().isBadRequest();
    }

    @Test
    void revisions_validRequest_usesRevisionChain() {
        when(useCase.revisionChain(DEVICE, "temp", T_DEVICE)).thenReturn(Flux.empty());

        client.get()
                .uri("/api/v1/ledger/devices/" + DEVICE + "/revisions?metric=temp&tDevice=" + T_DEVICE)
                .exchange()
                .expectStatus().isOk();

        verify(useCase).revisionChain(DEVICE, "temp", T_DEVICE);
        verifyNoMoreInteractions(useCase);
    }

    @Test
    void revisions_illegalArgument_returns400() {
        when(useCase.revisionChain(DEVICE, "temp", T_DEVICE))
                .thenReturn(Flux.error(new IllegalArgumentException("blank metric")));

        client.get()
                .uri("/api/v1/ledger/devices/" + DEVICE + "/revisions?metric=temp&tDevice=" + T_DEVICE)
                .exchange()
                .expectStatus().isBadRequest();
    }

    @Test
    void records_postMethod_isNotAllowed() {
        client.post().uri(recordsUri("")).exchange().expectStatus().isEqualTo(405);
    }

    @Test
    void records_putAndDelete_areNotAllowed() {
        client.put().uri(recordsUri("")).exchange().expectStatus().isEqualTo(405);
        client.delete().uri(recordsUri("")).exchange().expectStatus().isEqualTo(405);
    }

    @Test
    void revisions_postMethod_isNotAllowed() {
        client.post()
                .uri("/api/v1/ledger/devices/" + DEVICE + "/revisions?metric=temp&tDevice=" + T_DEVICE)
                .exchange()
                .expectStatus().isEqualTo(405);
    }
}
