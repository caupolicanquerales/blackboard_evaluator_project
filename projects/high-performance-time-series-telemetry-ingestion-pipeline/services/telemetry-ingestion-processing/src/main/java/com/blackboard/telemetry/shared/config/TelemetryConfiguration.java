package com.blackboard.telemetry.shared.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import java.time.Clock;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.r2dbc.core.DatabaseClient;
import com.blackboard.telemetry.shared.observability.TelemetryMeters;
import com.blackboard.telemetry.shared.audit.AuditTrail;
import com.blackboard.telemetry.shared.audit.R2dbcAuditTrail;
import com.blackboard.telemetry.ingestion.application.ValidatedSampleStream;
import com.blackboard.telemetry.ingestion.application.IngestPacketService;
import com.blackboard.telemetry.ingestion.infrastructure.InMemoryValidatedSampleStream;
import com.blackboard.telemetry.history.application.TelemetryHistoryRepository;
import com.blackboard.telemetry.history.application.HistoryEventPublisher;
import com.blackboard.telemetry.history.application.ReorderHistoryService;
import com.blackboard.telemetry.history.infrastructure.R2dbcTelemetryHistoryRepository;
import com.blackboard.telemetry.history.infrastructure.InMemoryHistoryEventPublisher;
import com.blackboard.telemetry.history.infrastructure.PipelineSubscriber;

@Configuration
@EnableConfigurationProperties(TelemetryProperties.class)
public class TelemetryConfiguration {

    @Bean
    public TelemetryMeters telemetryMeters(MeterRegistry registry) {
        return new TelemetryMeters(registry);
    }

    @Bean
    public AuditTrail auditTrail(DatabaseClient client) {
        return new R2dbcAuditTrail(client);
    }

    @Bean
    public ValidatedSampleStream validatedSampleStream(TelemetryProperties properties) {
        return new InMemoryValidatedSampleStream(properties);
    }

    @Bean
    public TelemetryHistoryRepository telemetryHistoryRepository(DatabaseClient client) {
        return new R2dbcTelemetryHistoryRepository(client);
    }

    @Bean
    public HistoryEventPublisher historyEventPublisher(TelemetryProperties properties) {
        return new InMemoryHistoryEventPublisher(properties);
    }

    @Bean
    public IngestPacketService ingestPacketService(TelemetryProperties properties, ValidatedSampleStream stream, AuditTrail auditTrail, TelemetryMeters meters, Clock clock) {
        return new IngestPacketService(properties, stream, auditTrail, meters, clock);
    }

    @Bean
    public ReorderHistoryService reorderHistoryService(TelemetryHistoryRepository repository, HistoryEventPublisher publisher, AuditTrail auditTrail, TelemetryMeters meters, TelemetryProperties properties, Clock clock) {
        return new ReorderHistoryService(repository, publisher, auditTrail, meters, properties, clock);
    }

    @Bean
    public PipelineSubscriber pipelineSubscriber(ValidatedSampleStream stream, ReorderHistoryService service) {
        return new PipelineSubscriber(stream, service);
    }

    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }
}
