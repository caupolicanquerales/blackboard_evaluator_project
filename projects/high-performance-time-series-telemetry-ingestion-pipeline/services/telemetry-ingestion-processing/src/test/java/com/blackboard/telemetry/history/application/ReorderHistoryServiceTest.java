package com.blackboard.telemetry.history.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.blackboard.telemetry.history.domain.HistoryEvent;
import com.blackboard.telemetry.history.domain.HistoryEventType;
import com.blackboard.telemetry.history.domain.RevisionReason;
import com.blackboard.telemetry.ingestion.domain.MetricKind;
import com.blackboard.telemetry.ingestion.domain.TelemetrySample;
import com.blackboard.telemetry.ingestion.domain.ValidatedSampleEvent;
import com.blackboard.telemetry.ingestion.domain.ValidationStatus;
import com.blackboard.telemetry.shared.audit.AuditEntry;
import com.blackboard.telemetry.shared.audit.AuditTrail;
import com.blackboard.telemetry.shared.config.TelemetryProperties;
import com.blackboard.telemetry.shared.observability.TelemetryMeters;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.slf4j.LoggerFactory;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class ReorderHistoryServiceTest {

    private static final Instant NOW = Instant.parse("2025-01-01T00:00:10Z");
    private static final Instant T_DEVICE = Instant.parse("2025-01-01T00:00:00Z");
    private static final Duration REORDER_WINDOW = Duration.ofSeconds(5);
    private static final MetricKind METRIC = MetricKind.values()[0];

    private final TelemetryHistoryRepository repository = mock(TelemetryHistoryRepository.class);
    private final HistoryEventPublisher publisher = mock(HistoryEventPublisher.class);
    private final AuditTrail auditTrail = mock(AuditTrail.class);
    private final SimpleMeterRegistry registry = new SimpleMeterRegistry();
    private final Clock clock = Clock.fixed(NOW, ZoneOffset.UTC);
    private final ListAppender<ILoggingEvent> logs = new ListAppender<>();
    private ReorderHistoryService service;

    @BeforeEach
    void setUp() {
        TelemetryProperties properties = new TelemetryProperties(REORDER_WINDOW, 10, 4, 4,
                Duration.ofSeconds(1), List.of());
        service = new ReorderHistoryService(repository, publisher, auditTrail,
                new TelemetryMeters(registry), properties, clock);
        when(publisher.publish(any())).thenReturn(Mono.empty());
        when(auditTrail.record(any())).thenReturn(Mono.empty());
        when(repository.findLatestTDevice(anyString(), any())).thenReturn(Mono.empty());
        when(repository.findWindow(anyString(), any(), any(), any(), anyInt())).thenReturn(Flux.empty());
        logs.start();
        ((Logger) LoggerFactory.getLogger(ReorderHistoryService.class)).addAppender(logs);
    }

    @AfterEach
    void tearDown() {
        ((Logger) LoggerFactory.getLogger(ReorderHistoryService.class)).detachAppender(logs);
    }

    private static TelemetrySample sample(Instant tIngress) {
        return new TelemetrySample("dev-1", METRIC, T_DEVICE, tIngress, 21.5, ValidationStatus.VALID);
    }

    private static ValidatedSampleEvent event(TelemetrySample sample) {
        return new ValidatedSampleEvent(sample, "corr-1");
    }

    private List<HistoryEvent> published() {
        ArgumentCaptor<HistoryEvent> captor = ArgumentCaptor.forClass(HistoryEvent.class);
        verify(publisher, org.mockito.Mockito.atLeast(0)).publish(captor.capture());
        return captor.getAllValues();
    }

    private List<AuditEntry> audited() {
        ArgumentCaptor<AuditEntry> captor = ArgumentCaptor.forClass(AuditEntry.class);
        verify(auditTrail, org.mockito.Mockito.atLeast(0)).record(captor.capture());
        return captor.getAllValues();
    }

    private List<String> logTemplates() {
        return logs.list.stream().map(ILoggingEvent::getMessage).toList();
    }

    private void stubWindow(int rows) {
        TelemetrySample s = sample(T_DEVICE.plusSeconds(1));
        when(repository.findWindow("dev-1", METRIC, T_DEVICE.minus(REORDER_WINDOW), T_DEVICE, 10))
                .thenReturn(Flux.just(s).repeat(rows - 1L));
    }

    @Test
    void handle_inOrderSample_publishesOnlyWindowBuffered() {
        TelemetrySample sample = sample(T_DEVICE.plusSeconds(1));
        when(repository.appendSample(sample)).thenReturn(Mono.just(1L));
        stubWindow(2);

        StepVerifier.create(service.handle(event(sample))).verifyComplete();

        assertThat(published()).extracting(HistoryEvent::type).containsExactly(HistoryEventType.WINDOW_BUFFERED);
        assertThat(published().get(0).windowSize()).isEqualTo(2);
        assertThat(published().get(0).correlationId()).isEqualTo("corr-1");
        verify(repository, never()).appendRevision(anyLong(), any(), anyDouble(), any());
    }

    @Test
    void handle_inOrderSample_auditsBroadcastWindowSuccessWithActorAndClock() {
        TelemetrySample sample = sample(T_DEVICE.plusSeconds(1));
        when(repository.appendSample(sample)).thenReturn(Mono.just(1L));
        stubWindow(1);

        StepVerifier.create(service.handle(event(sample))).verifyComplete();

        assertThat(audited()).hasSize(1);
        AuditEntry entry = audited().get(0);
        assertThat(entry.actor()).isEqualTo("history-service");
        assertThat(entry.action().toString()).isEqualTo("BROADCAST_WINDOW");
        assertThat(entry.outcome().toString()).isEqualTo("SUCCESS");
        assertThat(entry.correlationId()).isEqualTo("corr-1");
        assertThat(entry.timestamp()).isEqualTo(NOW);
    }

    @Test
    void handle_inOrderSample_recordsHistoryLatencyAndWindowLog() {
        TelemetrySample sample = sample(T_DEVICE.plusSeconds(1));
        when(repository.appendSample(sample)).thenReturn(Mono.just(1L));
        stubWindow(1);

        StepVerifier.create(service.handle(event(sample))).verifyComplete();

        assertThat(registry.get("telemetry.pipeline.latency").tag("stage", "history").timer().count())
                .isEqualTo(1L);
        assertThat(logTemplates()).containsExactly("window buffered");
    }

    @Test
    void handle_outOfOrderWithinWindow_publishesBackfilledThenWindowAndCountsReorder() {
        TelemetrySample sample = sample(T_DEVICE.plusSeconds(1));
        when(repository.appendSample(sample)).thenReturn(Mono.just(1L));
        when(repository.findLatestTDevice("dev-1", METRIC)).thenReturn(Mono.just(T_DEVICE.plusSeconds(3)));
        stubWindow(3);

        StepVerifier.create(service.handle(event(sample))).verifyComplete();

        assertThat(published()).extracting(HistoryEvent::type)
                .containsExactly(HistoryEventType.SAMPLE_BACKFILLED, HistoryEventType.WINDOW_BUFFERED);
        assertThat(published().get(0).revisionNo()).isZero();
        assertThat(published().get(1).windowSize()).isEqualTo(3);
        assertThat(registry.get("telemetry.samples.reordered").tag("metric", METRIC.name()).counter().count())
                .isEqualTo(1.0);
        assertThat(logTemplates()).containsExactly("sample reordered within backfill window", "window buffered");
        verify(repository, never()).appendRevision(anyLong(), any(), anyDouble(), any());
    }

    @Test
    void handle_lateBeyondWindow_appendsBackfillRevisionAndPublishesRevisionAppended() {
        TelemetrySample sample = sample(T_DEVICE.plusSeconds(6));
        when(repository.appendSample(sample)).thenReturn(Mono.just(9L));
        when(repository.appendRevision(9L, RevisionReason.BACKFILL, 21.5, sample.tIngress()))
                .thenReturn(Mono.just(1));
        stubWindow(1);

        StepVerifier.create(service.handle(event(sample))).verifyComplete();

        assertThat(published()).extracting(HistoryEvent::type)
                .containsExactly(HistoryEventType.REVISION_APPENDED, HistoryEventType.WINDOW_BUFFERED);
        assertThat(published().get(0).revisionNo()).isEqualTo(1);
        assertThat(registry.get("telemetry.revisions.appended").tag("reason", "BACKFILL").counter().count())
                .isEqualTo(1.0);
        assertThat(logTemplates()).containsExactly("revision appended", "window buffered");
    }

    @Test
    void handle_lateBeyondWindow_auditsAppendRevisionThenBroadcastWindow() {
        TelemetrySample sample = sample(T_DEVICE.plusSeconds(6));
        when(repository.appendSample(sample)).thenReturn(Mono.just(9L));
        when(repository.appendRevision(9L, RevisionReason.BACKFILL, 21.5, sample.tIngress()))
                .thenReturn(Mono.just(1));
        stubWindow(1);

        StepVerifier.create(service.handle(event(sample))).verifyComplete();

        assertThat(audited()).extracting(e -> e.action().toString())
                .containsExactly("APPEND_REVISION", "BROADCAST_WINDOW");
        assertThat(audited()).extracting(e -> e.outcome().toString()).containsOnly("SUCCESS");
    }

    @Test
    void handle_latenessEqualToWindow_isNotLateAndAppendsNoRevision() {
        TelemetrySample sample = sample(T_DEVICE.plus(REORDER_WINDOW));
        when(repository.appendSample(sample)).thenReturn(Mono.just(1L));
        stubWindow(1);

        StepVerifier.create(service.handle(event(sample))).verifyComplete();

        verify(repository, never()).appendRevision(anyLong(), any(), anyDouble(), any());
        assertThat(published()).extracting(HistoryEvent::type).containsExactly(HistoryEventType.WINDOW_BUFFERED);
    }

    @Test
    void handle_duplicateSample_doesNothingMore() {
        TelemetrySample sample = sample(T_DEVICE.plusSeconds(6));
        when(repository.appendSample(sample)).thenReturn(Mono.empty());

        StepVerifier.create(service.handle(event(sample))).verifyComplete();

        verify(repository, never()).appendRevision(anyLong(), any(), anyDouble(), any());
        verify(repository, never()).findWindow(anyString(), any(), any(), any(), anyInt());
        verify(publisher, never()).publish(any());
        verify(auditTrail, never()).record(any());
    }

    @Test
    void handle_windowReadFails_auditsFailureAndPropagatesError() {
        TelemetrySample sample = sample(T_DEVICE.plusSeconds(1));
        when(repository.appendSample(sample)).thenReturn(Mono.just(1L));
        when(repository.findWindow(anyString(), any(), any(), any(), anyInt()))
                .thenReturn(Flux.error(new IllegalStateException("db down")));

        StepVerifier.create(service.handle(event(sample)))
                .expectErrorMatches(e -> e instanceof IllegalStateException && "db down".equals(e.getMessage()))
                .verify();

        AuditEntry entry = audited().get(audited().size() - 1);
        assertThat(entry.action().toString()).isEqualTo("BROADCAST_WINDOW");
        assertThat(entry.outcome().toString()).isEqualTo("FAILURE");
        assertThat(entry.correlationId()).isEqualTo("corr-1");
    }

    @Test
    void handle_appendRevisionFails_auditsAppendRevisionFailureAndPropagatesError() {
        TelemetrySample sample = sample(T_DEVICE.plusSeconds(6));
        when(repository.appendSample(sample)).thenReturn(Mono.just(9L));
        when(repository.appendRevision(anyLong(), any(), anyDouble(), any()))
                .thenReturn(Mono.error(new IllegalStateException("boom")));

        StepVerifier.create(service.handle(event(sample))).expectError(IllegalStateException.class).verify();

        AuditEntry entry = audited().get(audited().size() - 1);
        assertThat(entry.action().toString()).isEqualTo("APPEND_REVISION");
        assertThat(entry.outcome().toString()).isEqualTo("FAILURE");
    }
}
