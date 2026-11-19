package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import com.pulsestream.telemetry.distribution.api.ValidatedEventConsumer;
import com.pulsestream.telemetry.distribution.application.BroadcastService;
import com.pulsestream.telemetry.distribution.infrastructure.BroadcastLifecycle;
import com.pulsestream.telemetry.distribution.infrastructure.InProcessEventBus;
import com.pulsestream.telemetry.ingestion.application.BackfillReorderer;
import com.pulsestream.telemetry.ingestion.application.IngestPacketUseCase;
import com.pulsestream.telemetry.ingestion.domain.SensorMetricBoundary;
import com.pulsestream.telemetry.ingestion.infrastructure.R2dbcAuditTrail;
import com.pulsestream.telemetry.ingestion.infrastructure.R2dbcTelemetryRecordRepository;
import com.pulsestream.telemetry.ingestion.infrastructure.Sha256RedactionAdapter;
import com.pulsestream.telemetry.shared.observability.TelemetryMetrics;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.time.Clock;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.core.userdetails.MapReactiveUserDetailsService;
import org.springframework.security.crypto.password.PasswordEncoder;

class TelemetryConfigurationTest {

    @Configuration
    @EnableConfigurationProperties(TelemetryProperties.class)
    static class PropertiesSlice {
    }

    private ApplicationContextRunner runner(String... extra) {
        var base = new String[] {
            "telemetry.reorder-window=PT1S", "telemetry.reorder-buffer-capacity=16",
            "telemetry.window-duration=PT1S", "telemetry.window-max-events=10",
            "telemetry.bus-capacity=16", "telemetry.broadcast-capacity=16",
            "telemetry.publisher-id=ingest-1"
        };
        return new ApplicationContextRunner()
                .withUserConfiguration(PropertiesSlice.class, TelemetryConfiguration.class)
                .withBean(MeterRegistry.class, SimpleMeterRegistry::new)
                .withBean(R2dbcTelemetryRecordRepository.class, () -> mock(R2dbcTelemetryRecordRepository.class))
                .withBean(R2dbcAuditTrail.class, () -> mock(R2dbcAuditTrail.class))
                .withBean(SensorMetricBoundary.class, SensorMetricBoundary::new)
                .withBean(Sha256RedactionAdapter.class, Sha256RedactionAdapter::new)
                .withBean(ValidatedEventConsumer.class, () -> mock(ValidatedEventConsumer.class))
                .withBean(BackfillReorderer.class, () -> mock(BackfillReorderer.class))
                .withPropertyValues(base)
                .withPropertyValues(extra);
    }

    @Test
    void context_testProfile_resolvesEveryNamedBeanOnce() {
        runner("spring.profiles.active=test", "telemetry.data-key=").run(ctx -> {
            assertThat(ctx).hasNotFailed();
            assertThat(ctx).hasSingleBean(Clock.class);
            assertThat(ctx).hasSingleBean(PasswordEncoder.class);
            assertThat(ctx).hasSingleBean(MapReactiveUserDetailsService.class);
            assertThat(ctx).hasSingleBean(TelemetryMetrics.class);
            assertThat(ctx).hasSingleBean(InProcessEventBus.class);
            assertThat(ctx).hasSingleBean(IngestPacketUseCase.class);
            assertThat(ctx).hasSingleBean(BroadcastService.class);
            assertThat(ctx).hasSingleBean(BroadcastLifecycle.class);
        });
    }

    @Test
    void context_testProfile_ingestPublisherAndBroadcastSourceAreSameBus() {
        runner("spring.profiles.active=test", "telemetry.data-key=").run(ctx -> {
            var bus = ctx.getBean(InProcessEventBus.class);

            assertThat(ctx.getBean(IngestPacketUseCase.class)).extracting("publisher").isSameAs(bus);
            assertThat(ctx.getBean(BroadcastService.class)).extracting("source").isSameAs(bus);
        });
    }

    @Test
    void context_blankDataKeyOutsideTestProfile_failsToStart() {
        runner("telemetry.data-key=").run(ctx -> assertThat(ctx).hasFailed());
    }
}
