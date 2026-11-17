package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

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
import com.pulsestream.telemetry.validation.domain.TelemetrySample;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import io.r2dbc.spi.ConnectionFactories;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.r2dbc.core.DatabaseClient;
import reactor.core.Disposable;

class PipelineConfigurationTest {

    private static final Instant T_DEVICE = Instant.parse("2025-01-01T10:00:00Z");

    @Configuration
    static class InfraConfig {
        @Bean
        DatabaseClient databaseClient() {
            String db = "pipe" + UUID.randomUUID().toString().replace("-", "");
            Flyway.configure()
                    .dataSource("jdbc:h2:mem:" + db + ";DB_CLOSE_DELAY=-1", "sa", "")
                    .locations("filesystem:db/migrations")
                    .load()
                    .migrate();
            return DatabaseClient.create(
                    ConnectionFactories.get("r2dbc:h2:mem:///" + db + ";DB_CLOSE_DELAY=-1;USER=sa;PASSWORD="));
        }

        @Bean
        MeterRegistry meterRegistry() {
            return new SimpleMeterRegistry();
        }
    }

    private static ApplicationContextRunner runner() {
        return new ApplicationContextRunner()
                .withUserConfiguration(InfraConfig.class, PipelineConfiguration.class)
                .withPropertyValues(
                        "telemetry.reorder-window-seconds=1",
                        "telemetry.buffer-capacity=64",
                        "telemetry.heart-rate-min=30",
                        "telemetry.heart-rate-max=240",
                        "telemetry.power-min=0",
                        "telemetry.power-max=2500",
                        "telemetry.cadence-min=0",
                        "telemetry.cadence-max=220",
                        "telemetry.swim-pace-min-exclusive=45");
    }

    @Test
    void context_loaded_exposesEachWiredBeanExactlyOnce() {
        runner().run(ctx -> {
            assertThat(ctx).hasNotFailed();
            for (Class<?> type : List.of(StepLog.class, ValidationService.class,
                    ReorderingService.class, R2dbcAuditTrail.class, R2dbcEventLogRepository.class,
                    SinkEventBroadcast.class, EventLogService.class, IntakeService.class,
                    CorrelationWebFilter.class, TelemetryIngestController.class,
                    TelemetryProperties.class)) {
                assertThat(ctx.getBeansOfType(type)).as(type.getSimpleName()).hasSize(1);
            }
            assertThat(ctx.getBeansOfType(AuditTrail.class)).hasSize(1);
            assertThat(ctx.getBeansOfType(EventLogRepository.class)).hasSize(1);
            assertThat(ctx.getBeansOfType(EventBroadcast.class)).hasSize(1);
        });
    }

    @Test
    void telemetryPipeline_windowFlushedSample_reachesEventLog() {
        runner().run(ctx -> {
            IntakeService intake = ctx.getBean(IntakeService.class);
            EventLogRepository repository = ctx.getBean(EventLogRepository.class);
            TelemetrySample sample = new TelemetrySample("dev-1", "heart_rate", T_DEVICE,
                    Instant.EPOCH, 80.0, "PENDING", "corr-1");

            intake.receive(List.of(sample)).block(Duration.ofSeconds(5));

            await().atMost(Duration.ofSeconds(10)).untilAsserted(() ->
                    assertThat(repository.findLatest("dev-1", "heart_rate", T_DEVICE)
                            .block(Duration.ofSeconds(2))).isNotNull());
        });
    }

    @Test
    void telemetryPipeline_contextClosed_isDisposed() {
        Disposable[] holder = new Disposable[1];
        runner().run(ctx -> {
            holder[0] = ctx.getBean("telemetryPipeline", Disposable.class);
            assertThat(holder[0].isDisposed()).isFalse();
        });

        assertThat(holder[0].isDisposed()).isTrue();
    }
}
