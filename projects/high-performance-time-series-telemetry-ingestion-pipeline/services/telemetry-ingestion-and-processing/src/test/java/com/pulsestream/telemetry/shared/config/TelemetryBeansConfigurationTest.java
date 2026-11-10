package com.pulsestream.telemetry.shared.config;

import static org.assertj.core.api.Assertions.assertThat;

import com.pulsestream.telemetry.shared.events.BoundedEventChannel;
import java.lang.reflect.Method;
import java.time.Clock;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

class TelemetryBeansConfigurationTest {

    private static final Class<?> UNIT = TelemetryBeansConfiguration.class;

    private static Optional<Method> beanMethod(String name) {
        return Arrays.stream(UNIT.getDeclaredMethods())
                .filter(m -> m.isAnnotationPresent(Bean.class))
                .filter(m -> m.getName().equals(name))
                .findFirst();
    }

    @Test
    void configuration_class_isAnnotatedAsConfiguration() {
        assertThat(UNIT.isAnnotationPresent(Configuration.class)).isTrue();
    }

    @Test
    void configuration_class_enablesTelemetryProperties() {
        EnableConfigurationProperties enabled = UNIT.getAnnotation(EnableConfigurationProperties.class);

        assertThat(enabled).isNotNull();
        assertThat(enabled.value()).containsExactly(TelemetryProperties.class);
    }

    @Test
    void configuration_class_isNotASecondSpringBootApplication() {
        assertThat(UNIT.isAnnotationPresent(SpringBootApplication.class)).isFalse();
        assertThat(UNIT.isAnnotationPresent(SpringBootConfiguration.class)).isFalse();
    }

    @Test
    void clockBean_isDeclaredAndReturnsClock() {
        Optional<Method> method = beanMethod("clock");

        assertThat(method).isPresent();
        assertThat(method.get().getReturnType()).isEqualTo(Clock.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "validatedSamples", "sequencedSamples", "backfillDetections",
        "closedWindows", "revisionsAppended", "streamPublications"
    })
    void channelBean_isDeclaredAsBoundedEventChannelTakingProperties(String name) {
        Optional<Method> method = beanMethod(name);

        assertThat(method).isPresent();
        assertThat(method.get().getReturnType()).isEqualTo(BoundedEventChannel.class);
        assertThat(List.of(method.get().getParameterTypes())).contains(TelemetryProperties.class);
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "sensorMetricBoundaryPolicy", "reactorTelemetryStreamGateway",
        "ingestTelemetryService", "sequencingService", "recordTelemetryService",
        "ledgerQueryService", "broadcastingService"
    })
    void serviceBean_isDeclared(String name) {
        assertThat(beanMethod(name)).isPresent();
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "ingestTelemetryService", "sequencingService", "recordTelemetryService",
        "broadcastingService"
    })
    void serviceBean_injectsGenericChannelsByQualifier(String name) {
        Method method = beanMethod(name).orElseThrow();

        long channelParams = Arrays.stream(method.getParameters())
                .filter(p -> p.getType() == BoundedEventChannel.class)
                .count();
        long qualified = Arrays.stream(method.getParameters())
                .filter(p -> p.getType() == BoundedEventChannel.class)
                .filter(p -> p.isAnnotationPresent(
                        org.springframework.beans.factory.annotation.Qualifier.class))
                .count();

        assertThat(channelParams).isPositive();
        assertThat(qualified).isEqualTo(channelParams);
    }
}
