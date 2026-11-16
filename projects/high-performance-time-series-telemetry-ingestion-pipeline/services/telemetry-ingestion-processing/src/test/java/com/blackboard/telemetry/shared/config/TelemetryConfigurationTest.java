package com.blackboard.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;

import com.blackboard.telemetry.history.application.HistoryEventPublisher;
import com.blackboard.telemetry.history.application.ReorderHistoryService;
import com.blackboard.telemetry.history.application.TelemetryHistoryRepository;
import com.blackboard.telemetry.history.infrastructure.InMemoryHistoryEventPublisher;
import com.blackboard.telemetry.history.infrastructure.PipelineSubscriber;
import com.blackboard.telemetry.history.infrastructure.R2dbcTelemetryHistoryRepository;
import com.blackboard.telemetry.ingestion.application.IngestPacketService;
import com.blackboard.telemetry.ingestion.application.ValidatedSampleStream;
import com.blackboard.telemetry.ingestion.infrastructure.InMemoryValidatedSampleStream;
import com.blackboard.telemetry.shared.audit.AuditTrail;
import com.blackboard.telemetry.shared.audit.R2dbcAuditTrail;
import com.blackboard.telemetry.shared.observability.TelemetryMeters;
import java.time.Clock;
import java.time.ZoneOffset;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class TelemetryConfigurationTest {

    @Autowired
    private ApplicationContext context;

    private <T> T single(Class<T> type) {
        assertThat(context.getBeansOfType(type)).hasSize(1);
        return context.getBean(type);
    }

    @Test
    void clock_resolvedOnce_isUtcSystemClock() {
        assertThat(single(Clock.class).getZone()).isEqualTo(ZoneOffset.UTC);
    }

    @Test
    void telemetryProperties_resolvedOnce_boundFromYml() {
        TelemetryProperties props = single(TelemetryProperties.class);

        assertThat(props.boundaries()).hasSize(7);
    }

    @Test
    void telemetryMeters_resolvedOnce() {
        assertThat(single(TelemetryMeters.class)).isNotNull();
    }

    @Test
    void auditTrail_resolvedOnce_isR2dbcAuditTrail() {
        assertThat(single(AuditTrail.class)).isInstanceOf(R2dbcAuditTrail.class);
    }

    @Test
    void validatedSampleStream_resolvedOnce_isInMemory() {
        assertThat(single(ValidatedSampleStream.class)).isInstanceOf(InMemoryValidatedSampleStream.class);
    }

    @Test
    void telemetryHistoryRepository_resolvedOnce_isR2dbc() {
        assertThat(single(TelemetryHistoryRepository.class))
                .isInstanceOf(R2dbcTelemetryHistoryRepository.class);
    }

    @Test
    void historyEventPublisher_resolvedOnce_isInMemory() {
        assertThat(single(HistoryEventPublisher.class)).isInstanceOf(InMemoryHistoryEventPublisher.class);
    }

    @Test
    void ingestPacketService_resolvedOnce() {
        assertThat(single(IngestPacketService.class)).isNotNull();
    }

    @Test
    void reorderHistoryService_resolvedOnce() {
        assertThat(single(ReorderHistoryService.class)).isNotNull();
    }

    @Test
    void pipelineSubscriber_resolvedOnce_isRunning() {
        assertThat(single(PipelineSubscriber.class).isRunning()).isTrue();
    }
}
