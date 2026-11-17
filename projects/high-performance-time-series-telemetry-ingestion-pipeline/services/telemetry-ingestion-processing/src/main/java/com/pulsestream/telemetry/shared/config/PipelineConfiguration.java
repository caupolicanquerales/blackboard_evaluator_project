package com.pulsestream.telemetry.shared.config;

import com.pulsestream.telemetry.eventlog.application.EventBroadcast;
import com.pulsestream.telemetry.eventlog.application.EventLogRepository;
import com.pulsestream.telemetry.eventlog.application.EventLogService;
import com.pulsestream.telemetry.eventlog.infrastructure.R2dbcAuditTrail;
import com.pulsestream.telemetry.eventlog.infrastructure.R2dbcEventLogRepository;
import com.pulsestream.telemetry.eventlog.infrastructure.SinkEventBroadcast;
import com.pulsestream.telemetry.intake.api.CorrelationWebFilter;
import com.pulsestream.telemetry.intake.api.TelemetryIngestController;
import com.pulsestream.telemetry.intake.application.IntakeService;
import com.pulsestream.telemetry.reordering.application.ReorderingService;
import com.pulsestream.telemetry.shared.observability.AuditTrail;
import com.pulsestream.telemetry.shared.observability.StepLog;
import com.pulsestream.telemetry.validation.application.ValidationService;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.Duration;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.core.Disposable;
import reactor.core.publisher.Mono;

@Configuration
@EnableConfigurationProperties(TelemetryProperties.class)
public class PipelineConfiguration {

    @Bean
    public StepLog stepLog() {
        return new StepLog();
    }

    @Bean
    public ValidationService validationService(TelemetryProperties properties, StepLog stepLog, MeterRegistry meterRegistry) {
        return new ValidationService(properties, stepLog, meterRegistry);
    }

    @Bean
    public ReorderingService reorderingService(TelemetryProperties properties, StepLog stepLog, MeterRegistry meterRegistry) {
        return new ReorderingService(properties, stepLog, meterRegistry);
    }

    @Bean
    public R2dbcAuditTrail auditTrail(DatabaseClient databaseClient, MeterRegistry meterRegistry) {
        return new R2dbcAuditTrail(databaseClient, meterRegistry);
    }

    @Bean
    public R2dbcEventLogRepository eventLogRepository(DatabaseClient databaseClient) {
        return new R2dbcEventLogRepository(databaseClient);
    }

    @Bean
    public SinkEventBroadcast eventBroadcast(TelemetryProperties properties) {
        return new SinkEventBroadcast(properties);
    }

    @Bean
    public EventLogService eventLogService(EventLogRepository repository, EventBroadcast broadcast, AuditTrail auditTrail, StepLog stepLog, MeterRegistry meterRegistry) {
        return new EventLogService(repository, broadcast, auditTrail, stepLog, meterRegistry);
    }

    @Bean
    public IntakeService intakeService(TelemetryProperties properties, AuditTrail auditTrail, StepLog stepLog, MeterRegistry meterRegistry) {
        return new IntakeService(properties, auditTrail, stepLog, meterRegistry);
    }

    @Bean
    public CorrelationWebFilter correlationWebFilter() {
        return new CorrelationWebFilter();
    }

    @Bean
    public TelemetryIngestController telemetryIngestController(IntakeService intakeService) {
        return new TelemetryIngestController(intakeService);
    }

    @Bean(destroyMethod = "dispose")
    public Disposable telemetryPipeline(TelemetryProperties properties, IntakeService intakeService, ValidationService validationService, ReorderingService reorderingService, EventLogService eventLogService) {
        return intakeService.stream().map(validationService::validate).buffer(Duration.ofSeconds(properties.reorderWindowSeconds())).map(reorderingService::reorderWindow).flatMapIterable(window -> window).concatMap(record -> eventLogService.append(record).onErrorResume(error -> Mono.empty())).subscribe(record -> {
        }, error -> {
        });
    }
}
