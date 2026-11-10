package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import com.pulsestream.telemetry.intake.domain.ReorderWindow;
import java.time.Clock;
import java.time.Duration;
import java.time.ZoneOffset;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@ExtendWith(MockitoExtension.class)
class TelemetryConfigTest {

    private final TelemetryConfig config = new TelemetryConfig();

    @Mock
    private TelemetryProperties properties;

    @Test
    void clock_default_isSystemUtc() {
        Clock clock = config.clock();

        assertThat(clock.getZone()).isEqualTo(ZoneOffset.UTC);
    }

    @Test
    void reorderWindow_withProperties_returnsEmptyWindow() {
        when(properties.reorderWindow()).thenReturn(Duration.ofSeconds(2));

        ReorderWindow window = config.reorderWindow(properties);

        assertThat(window).isNotNull();
        assertThat(window.bufferedCount()).isZero();
    }

    @Test
    void class_declaration_isConfigurationEnablingTelemetryProperties() {
        assertThat(TelemetryConfig.class.isAnnotationPresent(Configuration.class)).isTrue();
        assertThat(TelemetryConfig.class.getAnnotation(EnableConfigurationProperties.class).value())
                .containsExactly(TelemetryProperties.class);
    }
}
